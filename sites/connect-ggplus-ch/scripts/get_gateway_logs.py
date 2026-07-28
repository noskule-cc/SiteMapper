"""Fetch Headwind (HMDM) device logs — the "Analyse Logs from Headwind" node.

Defaults: severity WARNING, last 5 days.

The API's `severity` filter is CUMULATIVE, not an exact level — so asking for
WARNING already includes ERROR. The noise ('Push long polling inquiry' = VERBOSE,
'Configuration updated' = INFO) is dropped server-side and never crosses the wire.

Beyond dumping rows, this classifies WHY a gateway is unreachable, which is the
point of the node: the log messages distinguish "no network at all" from "network
fine, but the gateway cannot complete its handshake with connect".

This is the MDM-green branch of the tree: those devices are still reachable, so their
logs are fresh and actually explain why they will not talk to connect. (For MDM-red
devices the management channel is dead — there is nothing to ask, so those go down the
LTE branch instead.)

Usage:
    python get_gateway_logs.py 2023110600000332              # WARNING+ERROR, last 5 days
    python get_gateway_logs.py 2023110600000332 --days 14
    python get_gateway_logs.py 2023110600000332 --errors-only --json
    python get_gateway_logs.py --bucket ANALYZE_LOGS         # every MDM-green / connect-offline gateway
    python get_gateway_logs.py --bucket ANALYZE_LOGS --triage run/triage.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from ggplus_api import SEVERITY_ALL, SEVERITY_ERROR, SEVERITY_WARNING, get_hmdm_logs
from ggplus_auth import session

# The Windows console defaults to cp1252 and cannot encode the box/arrow characters used
# below. Files are written as UTF-8 regardless.
if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

# Message signatures -> a diagnosis. Ordered: first match wins.
SIGNATURES: list[tuple[str, str, str]] = [
    ("NO_DNS",          r"Unable to resolve host|No address associated with hostname",
     "No DNS / no network — the gateway cannot reach bff.ggplus.ch at all"),
    ("HUB_HANDSHAKE",   r"HubException|handshake|Handshake was canceled",
     "Network is up but the SignalR handshake with connect fails — this is how a "
     "gateway can be 'offline' in connect while its SIM still moves data"),
    ("WATCHDOG_REBOOT", r"WatchdogManager|Triggering reboot",
     "Watchdog reboot loop — a service is not reporting its heartbeat"),
    ("CONFIG_FAILED",   r"Failed to update config",
     "Config update failing (network error)"),
    ("CONNECTIVITY",    r"Connectivity_ConnectivityChanged",
     "Connectivity flapping"),
]


def diagnose(items: list[dict]) -> list[dict]:
    """Group the log rows into diagnoses, most frequent first."""
    hits: Counter[str] = Counter()
    for it in items:
        msg = it.get("message") or ""
        for key, pattern, _ in SIGNATURES:
            if re.search(pattern, msg, re.I):
                hits[key] += 1
                break
        else:
            hits["OTHER"] += 1

    out = []
    for key, n in hits.most_common():
        meaning = next((m for k, _, m in SIGNATURES if k == key), "Unclassified")
        out.append({"signature": key, "count": n, "meaning": meaning})
    return out


def for_device(s, serial: str, hours: int, severity: int) -> dict:
    items, total = get_hmdm_logs(s, serial=serial, hours=hours, severity=severity)
    return {
        "serial": serial,
        "hours": hours,
        "days": round(hours / 24, 1),
        "count": len(items),
        "total_on_server": total,
        # True when paging stopped before the server's total — say so rather than
        # letting a truncated set read as complete.
        "truncated": len(items) < total,
        "severities": dict(Counter(i.get("severity") for i in items)),
        "first_seen": _ts(min((i.get("createTime") for i in items), default=None)),
        "last_seen": _ts(max((i.get("createTime") for i in items), default=None)),
        "diagnosis": diagnose(items),
        "items": items,
    }


def _ts(ms: int | None) -> str | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# File output: <serial>.log (raw), <serial>.md (summary), Summary.md (across all)
# --------------------------------------------------------------------------
def write_log(out: Path, r: dict) -> None:
    """Raw rows, newest first — the evidence, unedited."""
    lines = [
        f"# {r['serial']} — Headwind log",
        f"# window: last {r['days']}d ({r['first_seen']} .. {r['last_seen']})",
        f"# severity: WARNING+ERROR | rows: {r['count']} of {r['total_on_server']} on server",
        "",
    ]
    if r["truncated"]:
        lines.insert(3, f"# TRUNCATED: only the newest {r['count']} rows were fetched")
    for it in r["items"]:
        msg = (it.get("message") or "").rstrip()
        lines.append(f"{_ts(it.get('createTime'))}  {it.get('severity'):<8} {msg}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(out: Path, r: dict) -> None:
    """Short per-gateway summary — what the log actually says."""
    lines = [f"# {r['serial']}", ""]
    if not r["count"]:
        lines += [f"No WARNING or ERROR entries in the last {r['days']} days.", "",
                  "That is not necessarily good news: a device that logs *nothing* may "
                  "simply not be reporting at all."]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    top = r["diagnosis"][0]
    lines += [
        f"**{r['count']} WARNING/ERROR entries** in the last {r['days']} days "
        f"({r['first_seen']} .. {r['last_seen']}).",
        "",
    ]
    if r["truncated"]:
        lines += [
            f"> ⚠️ **Truncated:** the server holds **{r['total_on_server']}** matching rows; "
            f"only the newest {r['count']} were fetched. The counts below are a sample of "
            f"the most recent entries, not the full window — treat them as proportions, "
            f"not totals.",
            "",
        ]
    lines += [
        f"**Most likely cause — {top['signature']}:** {top['meaning']}",
        "",
        "| Signature | Count | Meaning |",
        "|---|---:|---|",
    ]
    for d in r["diagnosis"]:
        lines.append(f"| `{d['signature']}` | {d['count']} | {d['meaning']} |")

    lines += ["", "## Most recent entries", "", "```"]
    for it in r["items"][:5]:
        msg = " ".join((it.get("message") or "").split())[:160]
        lines.append(f"{_ts(it.get('createTime'))}  {it.get('severity'):<8} {msg}")
    lines += ["```", "", f"Full log: [`{r['serial']}.log`](./{r['serial']}.log)"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_overall_summary(out: Path, results: list[dict], days: int) -> None:
    """Summary.md — the cross-gateway picture, which is what you actually act on."""
    total = Counter()
    per_gateway_top: list[tuple[str, str, int]] = []
    silent: list[str] = []

    for r in results:
        if not r["count"]:
            silent.append(r["serial"])
            continue
        for d in r["diagnosis"]:
            total[d["signature"]] += d["count"]
        top = r["diagnosis"][0]
        per_gateway_top.append((r["serial"], top["signature"], r["count"]))

    lines = [
        "# Headwind log summary",
        "",
        f"{len(results)} gateways analysed · last {days} days · severity WARNING+ERROR "
        f"(the filter is cumulative, so WARNING already includes ERROR).",
        "",
        "These are the gateways where **MDM is green but connect is offline** — we can still "
        "reach the device, so its logs are fresh and actually explain why it will not talk "
        "to connect.",
        "",
        "## What the fleet is complaining about",
        "",
        "| Signature | Entries | Meaning |",
        "|---|---:|---|",
    ]
    meanings = {k: m for k, _, m in SIGNATURES}
    meanings["OTHER"] = "Unclassified"
    for sig, n in total.most_common():
        lines.append(f"| `{sig}` | {n} | {meanings.get(sig, '')} |")

    truncated = [r for r in results if r["truncated"]]
    if truncated:
        lines += [
            "",
            "> ⚠️ **Some logs are truncated** — the paging cap was reached, so the counts "
            "above are a sample of the most recent entries rather than totals for the "
            "whole window. Affected: "
            + ", ".join(f"`{r['serial']}` ({r['count']} of {r['total_on_server']})"
                        for r in truncated),
        ]

    lines += ["", "## Per gateway", "",
              "| Seriennummer | Entries | Dominant signature | Details |",
              "|---|---:|---|---|"]
    for serial, sig, n in sorted(per_gateway_top, key=lambda x: -x[2]):
        r = next(x for x in results if x["serial"] == serial)
        shown = f"{n} of {r['total_on_server']}" if r["truncated"] else str(n)
        lines.append(f"| `{serial}` | {shown} | `{sig}` | [{serial}.md](./{serial}.md) |")

    if silent:
        lines += ["", "## Silent gateways", "",
                  "No WARNING or ERROR entries at all in the window. This is **not** a clean "
                  "bill of health — a device that logs nothing may simply have stopped "
                  "reporting:", ""]
        for serial in silent:
            lines.append(f"- `{serial}`")

    if total.get("HUB_HANDSHAKE"):
        lines += ["", "## Note", "",
                  "`HUB_HANDSHAKE` means the network is up but the gateway cannot complete its "
                  "SignalR handshake with connect. A gateway showing this **plus** real LTE "
                  "traffic is alive and moving data — its \"offline\" status in connect is a "
                  "false negative, not a dead device."]

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("serial", nargs="?", help="gateway serial number (Seriennummer)")
    ap.add_argument("--bucket", choices=["ANALYZE_LOGS", "LTE_CHECK", "FLASH_ONLINE", "FLASH_OFFLINE", "OK"],
                    help="run for every gateway in a triage bucket. ANALYZE_LOGS is the "
                         "one that matters: MDM green but connect offline — we can reach "
                         "those devices, so their logs are fresh and worth reading.")
    window = ap.add_mutually_exclusive_group()
    window.add_argument("--days", type=float, default=5.0, help="lookback window in days (default: 5)")
    window.add_argument("--hours", type=float, help="lookback window in hours (overrides --days)")
    level = ap.add_mutually_exclusive_group()
    level.add_argument("--errors-only", action="store_true", help="ERROR only (drop WARNING)")
    level.add_argument("--all-severities", action="store_true",
                       help="everything incl. INFO/VERBOSE noise — rarely what you want")
    ap.add_argument("--triage", metavar="FILE",
                    help="with --bucket: take the bucket membership from a triage.json written "
                         "by an earlier run instead of re-running the fleet sweep. Prefer this "
                         "inside a workflow run — the sweep re-opens SignalR (which the server "
                         "refuses a second time) and would return a different snapshot.")
    ap.add_argument("--env", default="prod", choices=["prod", "dev"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", metavar="DIR",
                    help="write <serial>.log, <serial>.md and Summary.md into DIR")
    args = ap.parse_args()

    if not args.serial and not args.bucket:
        ap.error("give a serial, or --bucket ANALYZE_LOGS")
    if args.triage and not args.bucket:
        ap.error("--triage only applies to --bucket")

    hours = int(args.hours if args.hours is not None else args.days * 24)
    severity = (SEVERITY_ERROR if args.errors_only
                else SEVERITY_ALL if args.all_severities
                else SEVERITY_WARNING)          # default: WARNING (already includes ERROR)

    s = session(args.env)

    if args.bucket:
        from get_gateway_status_table import build_table, load_table
        table = load_table(args.triage) if args.triage else build_table(args.env)
        serials = [g["serialNumber"] for g in table["gateways"]
                   if g["bucket"] == args.bucket]
        src = args.triage if args.triage else "a fresh fleet sweep"
        print(f"{len(serials)} gateways in {args.bucket} (from {src})\n", file=sys.stderr)
    else:
        serials = [args.serial]

    results = [for_device(s, serial, hours, severity) for serial in serials]

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for r in results:
            write_log(out / f"{r['serial']}.log", r)
            write_summary(out / f"{r['serial']}.md", r)
        write_overall_summary(out / "Summary.md", results, int(hours / 24))
        n_files = len(results) * 2 + 1
        print(f"wrote {n_files} files to {out}  "
              f"({len(results)} × <serial>.log + <serial>.md, plus Summary.md)")
        return 0

    if args.json:
        json.dump(results if len(results) > 1 else results[0], sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0

    label = {SEVERITY_WARNING: "WARNING+ERROR", SEVERITY_ERROR: "ERROR only",
             SEVERITY_ALL: "all severities"}[severity]
    for r in results:
        print(f"\n{r['serial']} — {r['count']} rows, last {r['days']}d ({label})")
        if r["truncated"]:
            print(f"  NOTE: server has {r['total_on_server']} rows; only the newest "
                  f"{r['count']} were fetched")
        if not r["count"]:
            print("  (no entries — the gateway logged nothing at this level)")
            continue
        print(f"  window: {r['first_seen']} .. {r['last_seen']}")
        for d in r["diagnosis"]:
            print(f"  [{d['count']:>5}x] {d['signature']:<16} {d['meaning']}")
        print("  most recent:")
        for it in r["items"][:3]:
            msg = " ".join((it.get("message") or "").split())[:110]
            print(f"    {it.get('severity'):<8} {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
