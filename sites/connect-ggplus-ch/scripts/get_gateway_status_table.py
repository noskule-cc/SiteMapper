"""Fetch the full gateway fleet and assign each gateway an action bucket.

This replaces the DOM scrape of /adminbereich/gateway-monitoring. It reproduces
exactly what the page's own "CSV Export" button produces (that button is a
client-side Blob, not an API call — there is no CSV endpoint), plus the decision
tree from gateway_online_status.drawio.

    Version >= threshold ?   no  -> connect Status online ? (nodes 2-6)
      (or no version at all)         yes -> FLASH_ONLINE   (box 3/4, reachable — remote candidate)
                                     no  -> FLASH_OFFLINE  (box 5/6, guaranteed site visit)
                                   (same action "Vor Ort: Flash", but TWO lists; reason kept)
    MDM (Headwind) green ?   no  -> LTE_CHECK       -> Swisscom branch (nodes 12-19)
    connect Status online ?  yes -> OK              (box 9)
                             no  -> ANALYZE_LOGS    (box 10 Headwind logs -> box 11 Summary)

The two lower branches ask different questions on purpose:

  MDM red   -> the management channel is dead, so no remote fix is possible (you
               cannot push a reset through the channel that is red). Ask the NETWORK
               whether the device is even alive (Swisscom). The outcome, assigned during
               the Swisscom drive, is one of:
                   LTE traffic present            -> VOR_ORT_SIGNAL_FLASH (box 18/19)
                   no traffic, SIM active         -> VOR_ORT_RESET_FLASH  (box 16/17)
                   no traffic, SIM deactivated    -> reactivate & re-check (node 14):
                                                       recovered -> OK (box 9, no visit)
                                                       still dead -> VOR_ORT_RESET_FLASH
                   serial not in the account      -> SIM_NICHT_IM_ACCOUNT (box 15, no visit)
  MDM green -> we CAN reach the device, so ask IT why it will not talk to connect
               (Headwind logs). No Swisscom lookup needed: a green MDM already proves
               the device is reachable.

Usage:
    python get_gateway_status_table.py                  # summary table
    python get_gateway_status_table.py --json           # full JSON to stdout
    python get_gateway_status_table.py --bucket LTE_CHECK
    python get_gateway_status_table.py --csv out.csv    # same columns as the UI export

    # assemble the deliverable AFTER the Swisscom step — always against the saved
    # snapshot, never a re-fetch (a fresh sweep is a different fleet state):
    python get_gateway_status_table.py --triage run/triage.json \
        --lte-results run/lte-results.json --out run/
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from ggplus_api import (
    CONNECTION_STATE_LABEL,
    displayed_version,
    get_all_gateways,
    get_connection_states,
    get_partners,
    version_at_least,
)
from ggplus_auth import get_bearer, session

# The Windows console defaults to cp1252, which cannot encode ≥ / ↑ / ↓ — printing the
# worklist would raise UnicodeEncodeError. Files are written as UTF-8 regardless.
if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

VERSION_THRESHOLD = "1.15.1.2"
EXCLUDED_PARTNER_IDS = {1000, 10000, 3086769}  # internal / test / demo

BUCKETS = ["OK", "FLASH_ONLINE", "FLASH_OFFLINE", "ANALYZE_LOGS", "LTE_CHECK"]


def bucket_of(gw: dict, threshold: str) -> tuple[str, str]:
    """The decision tree (gateway_online_status.drawio). Exactly one bucket per
    gateway. Returns (bucket, reason) — the reason keeps the *why* visible where
    two different paths land on the same action.

        Version >= threshold ?    no  -> connect Status online ?
        (no version reported too)      yes -> FLASH_ONLINE  (reachable — a remote push
                                              might avoid the trip)
                                       no  -> FLASH_OFFLINE (unreachable — site visit)
                                       Same action either way; two lists. `reason`
                                       keeps VERSION_BELOW_THRESHOLD vs NO_VERSION_REPORTED.
        MDM (Headwind) green ?    no  -> LTE_CHECK: the management channel is dead, so
                                         there is no remote lever left — ask the NETWORK
                                         whether the device is even alive. Every outcome
                                         is a site visit; the LTE result only decides
                                         WHAT the technician does. (This is why there is
                                         no "MDM connect Reset": you cannot push a reset
                                         through the very channel that is red.)
        connect Status online ?  yes  -> OK
                                  no  -> ANALYZE_LOGS: MDM is green, so we CAN reach the
                                         device — ask it why it will not talk to connect.
    """
    ok = version_at_least(gw["version"], threshold)
    if ok is None or not ok:
        # Version low (or unreported) -> split by connect Status (nodes 2-6). Same
        # action either way (Vor Ort: Flash), but online == reachable (candidate for a
        # remote push) and offline == a guaranteed site visit, so they are two lists.
        reason = "NO_VERSION_REPORTED" if ok is None else "VERSION_BELOW_THRESHOLD"
        return ("FLASH_ONLINE" if gw["status"] == "Connected" else "FLASH_OFFLINE"), reason
    if (gw["mdm"] or "").lower() != "green":
        return "LTE_CHECK", "MDM_NOT_GREEN"
    if gw["status"] == "Connected":
        return "OK", "ONLINE"
    return "ANALYZE_LOGS", "CONNECT_OFFLINE_MDM_GREEN"


# Outcomes of the MDM-red / Swisscom branch (nodes 9-16), assigned during the Swisscom
# drive (see the workflow). WiFi gateways never reach node 9 at all — they have no SIM,
# so the question is undefined rather than false, and are handled via VOR_ORT_ANALYSE.
LTE_OUTCOMES = {
    "VOR_ORT_SIGNAL_FLASH":  "LTE traffic present but connect offline (node 9 true, box 15) "
                             "— the device is alive on cellular but cannot reach connect "
                             "(handshake/DNS): analyse logs + on-site Signalstärke-Test, Flash",
    "VOR_ORT_RESET_FLASH":   "no LTE traffic; SIM active, or reactivation did not recover it "
                             "(box 13) — on-site Reset (Flash)",
    "SIM_NICHT_IM_ACCOUNT":  "serial not found on the Swisscom account (box 12) — a SIM-"
                             "inventory problem, not a gateway fault; a site visit cannot fix it",
    "PENDING_SIM_ACTIVATION": "SIM is deactivated (node 11) — reactivation is operator-gated "
                              "and was not confirmed; do NOT reactivate autonomously",
    # A deactivated SIM that reactivation brought back maps to the shared OK action (box 6).
}

# --------------------------------------------------------------------------
# The worklist: one action per gateway, grouped by what someone has to DO.
# Ordered by "who has to act, and how urgently" — site visits first (they cost a
# technician's day), then desk work, then nothing. `Vor Ort: Flash Gateway` is
# reached from two different branches; they share the action but keep their reason.
# --------------------------------------------------------------------------
ACTIONS = [
    ("VOR_ORT_SIGNAL_FLASH",   "Vor Ort: Signalstärke-Test, Flash Gateway"),
    ("VOR_ORT_RESET_FLASH",    "Vor Ort: Reset (Flash) Gateway"),
    # Version low is one action (Vor Ort: Flash) but TWO lists — offline is a guaranteed
    # site visit, online is reachable (can potentially be pushed remotely). Kept separate.
    ("VOR_ORT_FLASH_OFFLINE",  "Vor Ort: Flash Gateway (Version low, offline)"),
    ("VOR_ORT_FLASH_ONLINE",   "Vor Ort: Flash Gateway (Version low, online)"),
    ("VOR_ORT_ANALYSE",        "Vor Ort: Analyse (WiFi — kein SIM)"),
    ("ANALYZE_LOGS",           "Analyse Logs from Headwind"),
    ("SIM_NICHT_IM_ACCOUNT",   "SIM nicht im Account (Inventar, kein Einsatz)"),
    ("PENDING_SIM_ACTIVATION", "Pending: SIM-Reaktivierung (operator-gated)"),
    ("PENDING_LTE",            "Pending: Swisscom LTE lookup"),
    ("OK",                     "OK — nichts zu tun"),
]
# Outcomes that are NOT a technician's trip — cannot be fixed on site, still pending, or
# resolved remotely. VOR_ORT_ANALYSE (WiFi on-site diagnosis) IS a visit, so it is absent.
NON_VISIT = {"ANALYZE_LOGS", "SIM_NICHT_IM_ACCOUNT", "PENDING_SIM_ACTIVATION", "PENDING_LTE", "OK"}
ACTION_LABEL = dict(ACTIONS)
ACTION_ORDER = [k for k, _ in ACTIONS]


def final_action(gw: dict, lte: dict | None = None) -> str:
    """The action for one gateway, folding in the Swisscom result when we have it.

    `lte` is the per-serial result of the LTE branch, e.g.
        {"outcome": "VOR_ORT_RESET_FLASH", ...}  or  {"outcome": "SIM_NICHT_IM_ACCOUNT"}
    Pass None for gateways that never reach the Swisscom step.
    """
    b = gw["bucket"]
    if b == "OK":
        return "OK"
    if b == "FLASH_ONLINE":
        return "VOR_ORT_FLASH_ONLINE"   # box 3/4 — version low, reachable in connect
    if b == "FLASH_OFFLINE":
        return "VOR_ORT_FLASH_OFFLINE"  # box 5/6 — version low, offline
    if b == "ANALYZE_LOGS":
        return "ANALYZE_LOGS"
    # LTE_CHECK (nodes 9-16)
    if gw.get("internetConnectionType") == "Wifi":
        return "VOR_ORT_ANALYSE"        # no SIM — never reaches node 9
    if lte and lte.get("outcome"):
        return lte["outcome"]           # VOR_ORT_SIGNAL_FLASH | VOR_ORT_RESET_FLASH |
                                        # SIM_NICHT_IM_ACCOUNT | OK | PENDING_SIM_ACTIVATION
    return "PENDING_LTE"                # Swisscom lookup not done yet


def build_worklist(data: dict, lte_results: dict[str, dict] | None = None) -> dict:
    """Group the fleet by action — the "what do we have to do" view.

    lte_results: serial -> LTE branch result (from the Swisscom step). Optional;
    without it the LTE_CHECK gateways show up under PENDING_LTE.
    """
    lte_results = lte_results or {}
    groups: dict[str, list[dict]] = {a: [] for a in ACTION_ORDER}
    for g in data["gateways"]:
        lte = lte_results.get(g["serialNumber"])
        g = dict(g, action=final_action(g, lte), lte=lte)
        groups[g["action"]].append(g)

    for rows in groups.values():                       # stable, scannable order
        rows.sort(key=lambda r: (r["partnerName"] or "", r["serialNumber"]))

    return {
        "generated_from": {"fleet_kept": data["fleet_kept"],
                           "version_threshold": data["version_threshold"]},
        "counts": {a: len(groups[a]) for a in ACTION_ORDER},
        "site_visits": sum(len(rows) for a, rows in groups.items() if a not in NON_VISIT),
        "groups": groups,
    }


def load_table(path: str | Path) -> dict:
    """Read a triage.json written by an earlier run instead of re-fetching.

    build_table() re-opens the SignalR hub, and the server refuses a second
    connection within a session (`Handshake status 404`). It also returns a
    DIFFERENT snapshot — the fleet flaps between passes — so a worklist built from
    a fresh sweep would not match the Swisscom outcomes gathered against the old
    one. Reusing the saved snapshot keeps every artifact of a run consistent.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"{path}: no such file — pass the triage.json of an earlier run")
    except json.JSONDecodeError as e:
        raise SystemExit(f"{path}: not valid JSON ({e})")
    missing = {"gateways", "fleet_total", "fleet_kept", "version_threshold"} - data.keys()
    if missing:
        raise SystemExit(f"{path}: not a triage.json — missing {', '.join(sorted(missing))}")
    return data


def _warn_if_states_missing(data: dict) -> None:
    """Shout on stderr when the SignalR sweep came back short.

    The connect Status decides nodes 2 and 8 of the tree, so a partial hub answer
    mis-buckets the fleet while still emitting perfectly valid JSON. Anything above
    a couple of percent means the run should be repeated, not reported.
    """
    missing = len(data.get("no_state_received") or [])
    if not missing:
        return
    kept = data.get("fleet_kept") or 1
    pct = 100.0 * missing / kept
    print(f"WARNING: no connect Status received for {missing}/{kept} gateways "
          f"({pct:.1f}%) — they are bucketed as if offline.", file=sys.stderr)
    if pct > 5.0:
        print("  This sweep is NOT trustworthy: the connect Status drives nodes 2 and 8 "
              "of the tree. Re-run the sweep before building a worklist from it.",
          file=sys.stderr)


def build_table(env: str = "prod", threshold: str = VERSION_THRESHOLD) -> dict:
    s = session(env)
    bearer = s.headers["Authorization"].removeprefix("Bearer ")

    raw = get_all_gateways(s, env)
    try:
        partners = get_partners(s, env)
    except Exception:
        partners = {}  # partner names are cosmetic — never fail the run over them

    # The one field REST will not give us. See ggplus_api.get_connection_states.
    states = get_connection_states(raw, bearer, env)

    rows = []
    for g in raw:
        pid = g.get("partnerId")
        rows.append(
            {
                "id": g.get("id"),
                "serialNumber": g.get("serialNumber"),
                "partnerId": pid,
                "partnerName": partners.get(pid, ""),
                "internalName": g.get("internalName") or "",
                # NO fallback to g["connectionState"] — that field is a placeholder
                # ("Unconfigured" for every gateway). Falling back to it turned a hub
                # that answered for 4 of 360 devices into a full-looking triage with
                # no_state_received: 0 (2026-08-03). A missing state must stay None so
                # it is reported instead of silently bucketed as offline.
                "status": states.get(g.get("id")),
                "mdm": g.get("hmdmState"),
                "version": displayed_version(g),
                "firmwareVersion": g.get("firmwareVersion"),
                "hmdmConnectVersionInstalled": g.get("hmdmConnectVersionInstalled"),
                "internetConnectionType": g.get("internetConnectionType"),
                "lastConnection": g.get("lastConnection"),
            }
        )

    kept = [r for r in rows if r["partnerId"] not in EXCLUDED_PARTNER_IDS]
    for r in kept:
        r["bucket"], r["reason"] = bucket_of(r, threshold)
        r["statusLabel"] = CONNECTION_STATE_LABEL.get(r["status"], r["status"])

    counts = {b: sum(1 for r in kept if r["bucket"] == b) for b in BUCKETS}
    # The flash cohort (online + offline) is reached two ways — keep the reason visible,
    # it is not the same claim ("old version" vs "cannot ask the device what it runs").
    flash_reasons = {
        reason: sum(1 for r in kept if r["bucket"] in ("FLASH_ONLINE", "FLASH_OFFLINE")
                    and r["reason"] == reason)
        for reason in ("VERSION_BELOW_THRESHOLD", "NO_VERSION_REPORTED")
    }

    lte = [r for r in kept if r["bucket"] == "LTE_CHECK"]
    # A WiFi gateway has no SIM: "LTE traffic?" is undefined for it, not false.
    # It skips the LTE node entirely and goes straight to Vor Ort: Analyse.
    wifi = [r for r in lte if r["internetConnectionType"] == "Wifi"]

    return {
        "fleet_total": len(rows),
        "fleet_kept": len(kept),
        "version_threshold": threshold,
        "excluded_partner_ids": sorted(EXCLUDED_PARTNER_IDS),
        "counts": counts,
        "flash_reasons": flash_reasons,
        "gateways": kept,
        # Only these need the (slow, manual) Swisscom drive.
        "lte_candidates": [r["serialNumber"] for r in lte if r not in wifi],
        # No SIM -> pre-assigned Vor Ort: Analyse without asking Swisscom.
        "lte_skipped_wifi": [r["serialNumber"] for r in wifi],
        "no_state_received": [r["serialNumber"] for r in kept if r["status"] is None],
    }


def worklist_markdown(wl: dict, when: str) -> str:
    """The worklist as Markdown, grouped by action — the deliverable a human works off."""
    out = [f"# Gateway worklist — {when}", ""]
    g = wl["generated_from"]
    out += [f"{g['fleet_kept']} gateways (Version threshold ≥ {g['version_threshold']}).",
            f"**{wl['site_visits']} site visits** required.", ""]

    out += ["| Action | Count |", "|---|---:|"]
    for a in ACTION_ORDER:
        if wl["counts"][a]:
            out.append(f"| {ACTION_LABEL[a]} | {wl['counts'][a]} |")
    out.append("")

    for a in ACTION_ORDER:
        rows = wl["groups"][a]
        if not rows:
            continue
        out += [f"## {ACTION_LABEL[a]} ({len(rows)})", ""]
        out += ["| Seriennummer | Vertragsnummer | Vertragspartner | Version | MDM | Status | Grund |",
                "|---|---|---|---|---|---|---|"]
        for r in rows:
            # Serials are written in FULL — this is a worklist, the value has to be
            # pasteable into the monitoring filter, Swisscom, or a ticket.
            reason = r["reason"]
            if r.get("lte", {}) and r["lte"].get("up"):
                reason += f" (↑{r['lte']['up']} ↓{r['lte']['down']})"
            out.append(
                f"| `{r['serialNumber']}` | {r['partnerId']} | {r['partnerName'] or '—'} "
                f"| {r['version'] or '—'} | {r['mdm'] or '—'} | {r['statusLabel'] or '—'} "
                f"| {reason} |"
            )
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="prod", choices=["prod", "dev"])
    ap.add_argument("--threshold", default=VERSION_THRESHOLD)
    ap.add_argument("--json", action="store_true", help="emit the full result as JSON")
    ap.add_argument("--bucket", choices=BUCKETS, help="list the gateways in one bucket")
    ap.add_argument("--csv", metavar="FILE", help="write the UI-equivalent CSV export")
    ap.add_argument("--worklist", action="store_true",
                    help="group by ACTION — what has to be done with each gateway")
    ap.add_argument("--lte-results", metavar="FILE",
                    help="JSON of Swisscom LTE outcomes (serial -> {outcome, up, down}) "
                         "to fold into the worklist; without it those gateways show as PENDING_LTE")
    ap.add_argument("--out", metavar="DIR",
                    help="write the full result set into DIR (triage.json, worklist.md, worklist.csv)")
    ap.add_argument("--triage", metavar="FILE",
                    help="reuse a triage.json from an earlier run instead of re-fetching. "
                         "Required when assembling the deliverable after the Swisscom step: "
                         "a fresh sweep is a different snapshot (and re-opening SignalR fails), "
                         "so the worklist would not match the LTE outcomes.")
    args = ap.parse_args()

    if args.triage:
        data = load_table(args.triage)
        if args.threshold != VERSION_THRESHOLD and args.threshold != data["version_threshold"]:
            print(f"warning: --threshold {args.threshold} ignored — {args.triage} was built "
                  f"with {data['version_threshold']}; buckets are already assigned",
                  file=sys.stderr)
    else:
        data = build_table(args.env, args.threshold)

    lte_results = None
    if args.lte_results:
        with open(args.lte_results, encoding="utf-8") as f:
            lte_results = json.load(f)
        # Must be a FLAT serial -> {outcome, ...} map. A wrapped shape (e.g.
        # {"results": [...]}) parses fine, matches nothing, and quietly files every
        # LTE candidate as PENDING_LTE — a worklist that looks finished but has the
        # whole Swisscom leg missing. Fail loudly instead.
        if not isinstance(lte_results, dict):
            raise SystemExit(f"{args.lte_results}: expected a JSON object mapping serial -> result")
        serials = {g["serialNumber"] for g in data["gateways"]}
        matched = serials & lte_results.keys()
        if not matched:
            raise SystemExit(
                f"{args.lte_results}: no key matches any gateway serial — expected a flat "
                f'{{"<serial>": {{"outcome": ...}}}} map, got keys like '
                f"{sorted(lte_results)[:3]}")
        no_outcome = [s for s in matched if not (lte_results[s] or {}).get("outcome")]
        if no_outcome:
            print(f"WARNING: {len(no_outcome)} LTE results carry no 'outcome' and stay PENDING_LTE: "
                  f"{no_outcome[:5]}", file=sys.stderr)

    if args.worklist or args.out:
        wl = build_worklist(data, lte_results)
        today = date.today().isoformat()

        if args.out:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "triage.json").write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            (out / "worklist.md").write_text(worklist_markdown(wl, today), encoding="utf-8")
            with open(out / "worklist.csv", "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["action", "serialNumber", "partnerId", "partnerName",
                            "version", "mdm", "status", "reason"])
                for a in ACTION_ORDER:
                    for r in wl["groups"][a]:
                        w.writerow([ACTION_LABEL[a], r["serialNumber"], r["partnerId"],
                                    r["partnerName"], r["version"], r["mdm"],
                                    r["statusLabel"], r["reason"]])
            print(f"wrote triage.json, worklist.md, worklist.csv to {out}")
            print(f"  {wl['site_visits']} site visits required")
            return 0

        if args.json:
            json.dump(wl, sys.stdout, indent=2, ensure_ascii=False)
            print()
        else:
            print(worklist_markdown(wl, date.today().isoformat()))
        return 0

    if args.json:
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        print()
        # A sweep that lost most of the hub's answers still produces well-formed JSON;
        # only this warning distinguishes it from a good one. Loud, on stderr, so it
        # survives `--json > triage.json`.
        _warn_if_states_missing(data)
        return 0

    if args.csv:
        cols = ["status", "lastConnection", "mdm", "partnerId", "partnerName",
                "internalName", "serialNumber", "version", "internetConnectionType", "bucket"]
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(data["gateways"])
        print(f"wrote {len(data['gateways'])} rows to {args.csv}")
        return 0

    if args.bucket:
        rows = [r for r in data["gateways"] if r["bucket"] == args.bucket]
        print(f"{args.bucket} — {len(rows)} gateways\n")
        for r in rows:
            print(f"  {r['serialNumber']:<20} {r['version'] or '—':<10} "
                  f"MDM={r['mdm'] or '—':<6} {r['statusLabel'] or '—':<15} "
                  f"{r['reason']:<26} {(r['partnerName'] or r['partnerId'])}")
        return 0

    print(f"Fleet: {data['fleet_total']} total → {data['fleet_kept']} kept "
          f"(excluded partners: {', '.join(map(str, data['excluded_partner_ids']))})")
    print(f"Version threshold: >= {data['version_threshold']}\n")

    action = {
        "OK": "no action (box 9)",
        "FLASH_ONLINE": "Vor Ort: Flash — reachable (box 3/4)",
        "FLASH_OFFLINE": "Vor Ort: Flash — offline (box 5/6)",
        "ANALYZE_LOGS": "Headwind logs → Connect offline: Logs Summary (box 10/11)",
        "LTE_CHECK": "Swisscom branch (nodes 12-19) → site visit unless cleared",
    }
    for b in BUCKETS:
        print(f"  {b:<16} {data['counts'][b]:>4}   {action[b]}")

    fr = data["flash_reasons"]
    print(f"\n  Flash cohort: {data['counts']['FLASH_ONLINE']} online / "
          f"{data['counts']['FLASH_OFFLINE']} offline (two lists, same action). Splits by reason:")
    print(f"    version < threshold   {fr['VERSION_BELOW_THRESHOLD']:>4}")
    print(f"    no version reported   {fr['NO_VERSION_REPORTED']:>4}   (cannot ask the device what it runs)")

    print(f"\nSwisscom lookups needed: {len(data['lte_candidates'])}")
    if data["lte_skipped_wifi"]:
        print(f"WiFi, no SIM (skip LTE → Vor Ort: Analyse): {len(data['lte_skipped_wifi'])}")
    # Most LTE_CHECK gateways end in a site visit; two outcomes do not — a serial not in
    # the Swisscom account (inventory) and a deactivated SIM that reactivation recovers.
    if data["counts"]["LTE_CHECK"]:
        print(f"\nNOTE: the {data['counts']['LTE_CHECK']} LTE_CHECK gateways need the Swisscom "
              f"drive (nodes 9-16); most end in a site visit, unless the serial is not in the "
              f"account or a deactivated SIM reactivates.")
    if data["no_state_received"]:
        print(f"WARNING: no connect Status received for {len(data['no_state_received'])} gateways")
    return 0


if __name__ == "__main__":
    sys.exit(main())
