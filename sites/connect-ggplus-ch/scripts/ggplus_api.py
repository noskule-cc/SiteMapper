"""GG+connect BFF API client — everything the gateway workflows need.

Endpoints (all under https://bff.ggplus.ch, Bearer auth via ggplus_auth):

  GET  /gateway/api/v1/gateway/all          fleet list (typed)
  POST /gateway/device-connection           SignalR hub — live connect Status
  POST /gateway/api/v1/hmdm/logs            Headwind device logs (severity filtered)
  GET  /gateway/api/v1/hmdm/{serial}/infos  Headwind per-device detail
  GET  /erp/api/v1/partner/all              partnerId -> partner name

Two things here are NOT obvious and are the reason this module exists at all:

1. `connectionState` in /gateway/all is a PLACEHOLDER. The REST list returns
   "Unconfigured" for every gateway. The real connect Status only exists on the
   SignalR hub: you connect, invoke AddDeviceWatcher(deviceId, classification)
   per device, and the server pushes back a `ConnectionState` message. That is
   what `get_connection_states()` does, and it is why a plain HTTP script cannot
   answer "is this gateway online?".

2. The "Version" shown in the UI is a HYBRID field, not one column:
       hmdmState != Grey  ->  hmdmConnectVersionInstalled
       hmdmState == Grey  ->  firmwareVersion
   `displayed_version()` reproduces the app's getDisplayedVersion() exactly.
   Reading firmwareVersion naively gives a different (wrong) answer.
"""

from __future__ import annotations

import json
import time
from typing import Iterable

import requests
from websocket import WebSocket, create_connection  # websocket-client

from ggplus_auth import base_url, session

RS = "\x1e"  # SignalR record separator

# Headwind log severity. The API filter is CUMULATIVE (everything at least this
# severe), not an exact level — so severity=2 yields WARNING + ERROR and nothing
# else. Fleet-wide over 24h that is ~11k rows instead of ~139k.
SEVERITY_ERROR = 1
SEVERITY_WARNING = 2  # == WARNING + ERROR  <- the default: "WARNING" already includes ERROR
SEVERITY_INFO = 3
SEVERITY_ALL = -1

DEFAULT_HOURS = 120  # 5 days


# --------------------------------------------------------------------------
# fleet list
# --------------------------------------------------------------------------
def get_all_gateways(s: requests.Session, env: str = "prod") -> list[dict]:
    """All gateways. NOTE: each row's `connectionState` is a placeholder —
    use get_connection_states() for the real value."""
    r = s.get(f"{base_url(env)}/gateway/api/v1/gateway/all", timeout=60)
    r.raise_for_status()
    body = r.json()
    if not body.get("succeeded"):
        raise RuntimeError(f"gateway/all failed: {body.get('messages')}")
    return body["result"]


def get_partners(s: requests.Session, env: str = "prod") -> dict[int, str]:
    """partnerId -> partner name (the Vertragspartner column)."""
    r = s.get(f"{base_url(env)}/erp/api/v1/partner/all", timeout=60)
    r.raise_for_status()
    body = r.json()
    rows = body.get("result", body) if isinstance(body, dict) else body
    out: dict[int, str] = {}
    for p in rows or []:
        pid = p.get("id") or p.get("partnerId")
        name = p.get("name") or p.get("companyName") or p.get("displayName") or ""
        if pid is not None:
            out[int(pid)] = name
    return out


def displayed_version(gw: dict) -> str:
    """The Version as the UI shows it (app's getDisplayedVersion)."""
    if (gw.get("hmdmState") or "").lower() != "grey":
        return gw.get("hmdmConnectVersionInstalled") or ""
    fw = gw.get("firmwareVersion")
    return fw if isinstance(fw, str) else ""


def version_at_least(version: str, threshold: str) -> bool | None:
    """Dotted numeric compare. None if no version was reported at all."""
    if not version:
        return None
    a = [int(x) if x.isdigit() else 0 for x in version.split(".")]
    b = [int(x) if x.isdigit() else 0 for x in threshold.split(".")]
    for i in range(max(len(a), len(b))):
        x, y = (a[i] if i < len(a) else 0), (b[i] if i < len(b) else 0)
        if x != y:
            return x > y
    return True  # equal — threshold is inclusive


# --------------------------------------------------------------------------
# connect Status — SignalR hub
# --------------------------------------------------------------------------
def get_connection_states(
    gateways: Iterable[dict],
    bearer: str,
    env: str = "prod",
    timeout: float = 420.0,
    idle_timeout: float = 60.0,
) -> dict[str, str]:
    """deviceId -> 'Connected' | 'Disconnected' | 'Unconfigured'.

    Protocol (reverse-engineered from the app's DeviceWatchListService):
      negotiate -> websocket -> JSON handshake
      -> invoke AddDeviceWatcher(deviceId, classification) per device
      -> server pushes ConnectionState { deviceId, deviceIotConnectionStatus, ... }

    BE PATIENT. The server answers ~380 watchers over roughly FIVE MINUTES, in
    bursts with long gaps between them. The old defaults (90s total / 10s idle)
    bailed out after the first gap with about FOUR states in hand, and because the
    caller used to fall back to the REST placeholder the run still looked complete
    (2026-08-03: 356/360 gateways silently bucketed from `connectionState:
    "Unconfigured"`, giving OK=0). Do not lower these without re-checking how many
    states actually arrive: a partial answer here mis-buckets the entire fleet.

    The returned dict may still be short of the fleet — callers MUST treat a
    missing deviceId as "no state received", never as a status.
    """
    devices = [g for g in gateways if g.get("id")]
    if not devices:
        return {}

    hub = f"{base_url(env)}/gateway/device-connection"
    neg = requests.post(
        f"{hub}/negotiate?negotiateVersion=1",
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=30,
    )
    neg.raise_for_status()
    token = neg.json()["connectionToken"]

    ws: WebSocket = create_connection(
        f"{hub.replace('https://', 'wss://')}?id={token}&access_token={bearer}",
        timeout=idle_timeout,
    )
    states: dict[str, str] = {}
    try:
        ws.send('{"protocol":"json","version":1}' + RS)

        for i, g in enumerate(devices, start=1):
            ws.send(
                json.dumps(
                    {
                        "type": 1,
                        "target": "AddDeviceWatcher",
                        "arguments": [g["id"], g.get("deviceClassification")],
                        "invocationId": str(i),
                    }
                )
                + RS
            )

        deadline = time.monotonic() + timeout
        while len(states) < len(devices) and time.monotonic() < deadline:
            try:
                raw = ws.recv()
            except Exception:
                break  # idle timeout — the server has nothing more to say
            for part in str(raw).split(RS):
                if not part:
                    continue
                try:
                    msg = json.loads(part)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == 1 and msg.get("target") == "ConnectionState":
                    arg = (msg.get("arguments") or [{}])[0]
                    if arg.get("deviceId"):
                        states[arg["deviceId"]] = arg.get("deviceIotConnectionStatus")
    finally:
        try:
            ws.close()
        except Exception:
            pass

    return states


CONNECTION_STATE_LABEL = {
    "Connected": "verbunden",
    "Disconnected": "offline",
    "Unconfigured": "unkonfiguriert",
}


# --------------------------------------------------------------------------
# Headwind logs
# --------------------------------------------------------------------------
def get_hmdm_logs(
    s: requests.Session,
    serial: str = "",
    hours: int = DEFAULT_HOURS,
    severity: int = SEVERITY_WARNING,
    page_size: int = 200,
    max_pages: int = 50,
    env: str = "prod",
) -> tuple[list[dict], int]:
    """Headwind log rows for one device (or the whole fleet if serial == "").

    Returns (items, total_items). total_items is what the server reports, so the
    caller can tell when paging was cut short by max_pages rather than silently
    reporting a truncated set as if it were complete.

    severity defaults to WARNING(2) = WARNING + ERROR (the filter is cumulative).
    The noise — VERBOSE 'Push long polling inquiry', INFO 'Configuration updated' —
    is dropped server-side and never crosses the wire.
    """
    now = time.time()
    body = {
        "applicationFilter": "",
        "messageFilter": "",
        "deviceFilter": serial,
        "dateFrom": _iso(now - hours * 3600),
        "dateTo": _iso(now),
        "pageNum": 1,
        "pageSize": page_size,
        "severity": severity,
        "sortDirection": "desc",
        "sortValue": "createTime",
    }

    items: list[dict] = []
    total = 0
    for page in range(1, max_pages + 1):
        body["pageNum"] = page
        r = s.post(f"{base_url(env)}/gateway/api/v1/hmdm/logs", json=body, timeout=60)
        r.raise_for_status()
        result = r.json().get("result") or {}
        total = result.get("totalItems") or 0
        batch = result.get("items") or []
        items.extend(batch)
        if not batch or len(items) >= total:
            break
    return items, total


def get_hmdm_infos(s: requests.Session, serial: str, env: str = "prod") -> dict:
    """Headwind per-device detail (imei, publicIp, lastUpdate, installed apps)."""
    r = s.get(f"{base_url(env)}/gateway/api/v1/hmdm/{serial}/infos", timeout=60)
    r.raise_for_status()
    return (r.json() or {}).get("result") or {}


def _iso(epoch_seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch_seconds)) + ".000Z"


__all__ = [
    "session",
    "get_all_gateways",
    "get_partners",
    "get_connection_states",
    "get_hmdm_logs",
    "get_hmdm_infos",
    "displayed_version",
    "version_at_least",
    "CONNECTION_STATE_LABEL",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "SEVERITY_INFO",
    "SEVERITY_ALL",
]
