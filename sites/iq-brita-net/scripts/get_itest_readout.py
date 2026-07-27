"""Daily readout for the two iQ-Meter test devices, straight from the BRITA API.

Headless replacement for the browser-driven itest-daily-readout workflow: fetch each
device by its tenant+resource id and report "Capacity remaining" + "Last activity" —
the two values appended to GG+ wiki page 2599.

    python get_itest_readout.py            # human table
    python get_itest_readout.py --json     # {device: {capacity_remaining, last_activity, ...}}
    python get_itest_readout.py --raw      # dump each device's raw API JSON (to pin the mapping)

Auth: needs a seeded BRITA refresh token — see brita_auth.py / README.md.

NOTE: the API JSON field names are not yet confirmed (see brita_api.py). The extractor
below is best-effort over likely keys and ALWAYS keeps the raw JSON available via --raw
and in --json output, so the mapping can be pinned on the first authenticated run and
this heuristic replaced with the exact field paths.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import brita_api
import brita_auth

TENANT_ID = "dae9a265-0efa-4616-b75b-58848d8f7b35"

# The two devices under test (see sites/iq-brita-net/workflows/itest-daily-readout.yaml).
DEVICES = [
    {"key": "werkstatt",  "label": "Werkstatt (3086769)",  "resource_id": "d3e78486-13c6-436c-abe8-8996aa49113e"},
    {"key": "pausenraum", "label": "Pausenraum (10000)",   "resource_id": "6c9a40e6-76f8-47fd-a589-9b04b7bc4443"},
]


def _leaves(obj, prefix=""):
    """Yield (dotted_path, value) for every scalar leaf in a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _leaves(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def extract_capacity(device: dict):
    """Best-effort 'capacity remaining' in litres (int). None if not found."""
    best = None
    for path, val in _leaves(device):
        p = path.lower()
        if "capacit" in p and "remain" in p and isinstance(val, (int, float)):
            return int(val)
        if "capacit" in p and isinstance(val, (int, float)) and best is None:
            best = int(val)
    return best


def extract_last_activity(device: dict):
    """Best-effort 'last activity' formatted 'DD/MM/YYYY, HH:MM'. None if not found.

    Returns (formatted, raw_value). Raw is kept so a mis-parse is visible.
    """
    pat = re.compile(r"last.?(activ|seen|message|contact|update|communicat)", re.I)
    candidate = None
    for path, val in _leaves(device):
        if pat.search(path) and isinstance(val, str) and val:
            candidate = val
            break
    if candidate is None:
        return None, None
    return _fmt_ts(candidate), candidate


def _fmt_ts(raw: str):
    """Format an ISO-ish timestamp as 'DD/MM/YYYY, HH:MM' (local wall time)."""
    s = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return raw  # leave unparsed values visible rather than guessing
    if dt.tzinfo is not None:
        dt = dt.astimezone()  # to local time, matching the portal display
    return dt.strftime("%d/%m/%Y, %H:%M")


def read_device(dev: dict, sess) -> dict:
    raw = brita_api.get_resource(TENANT_ID, dev["resource_id"], sess=sess)
    cap = extract_capacity(raw)
    last_fmt, last_raw = extract_last_activity(raw)
    return {
        "key": dev["key"],
        "label": dev["label"],
        "resource_id": dev["resource_id"],
        "capacity_remaining": cap,
        "last_activity": last_fmt,
        "last_activity_raw": last_raw,
        "raw": raw,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BRITA iQ-Meter test devices daily readout")
    ap.add_argument("--json", action="store_true", help="emit structured JSON")
    ap.add_argument("--raw", action="store_true", help="dump each device's raw API JSON")
    args = ap.parse_args(argv)

    try:
        sess = brita_auth.session()
    except RuntimeError as e:
        print(f"auth error: {e}", file=sys.stderr)
        return 2

    results = []
    for dev in DEVICES:
        try:
            results.append(read_device(dev, sess))
        except Exception as e:  # noqa: BLE001 - surface per-device failure, keep going
            results.append({"key": dev["key"], "label": dev["label"],
                            "resource_id": dev["resource_id"], "error": str(e)})

    if args.raw:
        print(json.dumps({r["key"]: r.get("raw", {"error": r.get("error")}) for r in results},
                         indent=2, ensure_ascii=False))
        return 0

    if args.json:
        slim = [{k: v for k, v in r.items() if k != "raw"} for r in results]
        print(json.dumps({"tenant_id": TENANT_ID, "devices": slim},
                         indent=2, ensure_ascii=False))
        return 0

    # human table
    print(f"{'Device':<24} {'Kapazität übrig':>16}  {'Letzte Aktualisierung':<22}")
    print("-" * 66)
    for r in results:
        if "error" in r:
            print(f"{r['label']:<24} {'ERROR':>16}  {r['error'][:22]}")
            continue
        cap = "-" if r["capacity_remaining"] is None else str(r["capacity_remaining"])
        la = r["last_activity"] or "-"
        print(f"{r['label']:<24} {cap:>16}  {la:<22}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
