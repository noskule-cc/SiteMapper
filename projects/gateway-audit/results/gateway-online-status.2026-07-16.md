# gateway-online-status — 2026-07-16

Full run of the gateway triage workflow (project **gateway-audit**) against the
19-box decision tree in [`gateway_online_status.drawio`](../workflows/gateway_online_status.drawio).
Assigns **one action per gateway**. Sections below follow the diagram's **Rapport** lane.

- **Workflow:** [`gateway-online-status.yaml`](../workflows/gateway-online-status.yaml)
- **Status:** **complete** — connect side (API) + Swisscom MDM-red branch (browser) both run
- **Operator:** noskule · Swisscom login: Benjamin Behringer
- **Version threshold:** ≥ 1.15.1.2 (inclusive)
- **Exclusions:** partnerId {1000, 10000, 3086769}
- **Fleet:** 370 gateways → **348 kept**
- **Method:** connect side is API-only (no browser). Swisscom side is a **read-only** UI drive
  (Vaadin, no REST API) — no settings were changed (see the note on `…175`).

> **New this run:** version-low is split by connect Status into **online** (reachable) and
> **offline** — same action (Vor Ort: Flash) but two separate lists, so the reachable ones
> can be tried remotely before booking a truck.

## Worklist

| § (Rapport) | Action | Count | Site visit? |
|---|---|---:|:---:|
| **6** Version low, offline: Gateway Upgrade List | Vor Ort: Flash Gateway | **219** | ✓ |
| **4** Version low, online: Gateway Upgrade List | Vor Ort: Flash Gateway (reachable) | **19** | ✓ * |
| **19** Unknown MDM error: offline Logs Summary | Vor Ort: Signalstärke-Test, Flash | **1** | ✓ |
| **17** Unknown Network Error: Gateway Reset List | Vor Ort: Reset (Flash) | **29** | ✓ |
| **11** Connect offline: Logs Summary | Analyse Logs (desk) | **2** | — |
| **14** activate SIM (Deaktiviert) | recorded, **not** actioned | **1** | pending |
| **9** Gateway OK: nothing to do | — | **77** | — |
| **15** SIM nicht im Account | inventory | **0** | — |

**Site visits: 268** (219 + 19 Flash + 29 Reset + 1 Signalstärke). \* The 19 **online** flash
gateways are counted as visits, but they're reachable in connect — the cohort to try a
remote push on first, potentially shaving them off the truck-roll list.

Full list, complete serials:
[`worklist.md`](./gateway-online-status.2026-07-16/worklist.md) ·
[`worklist.csv`](./gateway-online-status.2026-07-16/worklist.csv) ·
[`triage.json`](./gateway-online-status.2026-07-16/triage.json) ·
[`lte-results.json`](./gateway-online-status.2026-07-16/lte-results.json)

## §6 — Version low, offline: Gateway Upgrade List (219) — **flash priority**

Version low **and** offline in connect. No remote lever, so every one is a guaranteed site
visit — **this is the list to flash first.** Split by reason:

| Reason | Count | Meaning |
|---|---:|---|
| `VERSION_BELOW_THRESHOLD` | **161** | runs a connect-app version below 1.15.1.2 |
| `NO_VERSION_REPORTED` | **58** | never reported a connect version (grey MDM / pre-Headwind firmware) |

Full list: [`worklist.md`](./gateway-online-status.2026-07-16/worklist.md) →
*Vor Ort: Flash Gateway (Version low, offline)*.

## §4 — Version low, online: Gateway Upgrade List (19)

Version low **but reachable** in connect — try a remote/OTA push before booking a truck.
Work these **after** the offline list. Split by reason:

| Reason | Count | Meaning |
|---|---:|---|
| `VERSION_BELOW_THRESHOLD` | **18** | runs a connect-app version below 1.15.1.2 |
| `NO_VERSION_REPORTED` | **1** | never reported a connect version |

Full list: [`worklist.md`](./gateway-online-status.2026-07-16/worklist.md) →
*Vor Ort: Flash Gateway (Version low, online)*.

Together this is **one migration, not 238 failures**: the 59 no-version gateways across both
lists are a **reporting** gap (never enrolled in Headwind), not an update regression.

## §19 / §17 — the MDM-red branch (31 gateways, Swisscom read-only)

All 31 candidates were found in the Swisscom account this run — including `…427` and `…136`,
which were **missing on 2026-07-14**; the SIM inventory has since been reconciled.

| Outcome | Count | Rule |
|---|---:|---|
| **§19** Signalstärke-Test, Flash | **1** | LTE traffic in last 24h (alive on cellular, offline in connect) |
| **§17** Reset (Flash) | **29** | no 24h traffic, SIM active |
| **§14** recorded, not actioned | **1** | SIM **Deaktiviert** — see below |

- **§19 — `2023110600000504`**: the *only* gateway with 24h traffic — **↑2.64 kB / ↓2.66 kB**,
  i.e. keep-alive chatter (22.63 kB month-to-date). Alive but barely; handshake with connect
  is failing → on-site Signalstärke-Test + Flash.
- **§17 — 29 gateways, 0 Bytes in the last 24h.** Six of them **moved real volume earlier this
  month** and have since gone silent — they died recently rather than never having worked:

  | Serial | Monthly | Last 24 h |
  |---|---:|---:|
  | `2023110600000493` | 1.93 GB | 0.00 Bytes |
  | `2023110600000436` | 887.59 MB | 0.00 Bytes |
  | `2023110600000147` | 615.19 MB | 0.00 Bytes |
  | `2023110600000375` | 112.93 MB | 0.00 Bytes |
  | `2023110600000019` | 50.43 MB | 0.00 Bytes |
  | `2023110600000141` | 30.83 MB | 0.00 Bytes |

  `2023110600000493` is notable: on 2026-07-14 it was moving ~87 MB/day while failing DNS
  (`Unable to resolve host bff.ggplus.ch`); in the last 24 h it has gone fully silent.

## §14 — deactivated SIM, recorded only (1)

| Serial | Swisscom status | Monthly | Handling |
|---|---|---:|---|
| `2023110600000175` | **Deaktiviert** | 5.00 GB | **No change made.** Per instruction, the status is recorded and left for a human decision — the tree's *activate SIM* step (node 14) was **not** executed. |

## §11 — Connect offline: Logs Summary (2)

MDM green but connect offline (both borderline/flapping this run):

| Serial | WARNING+ERROR (5d) | Dominant signature |
|---|---:|---|
| `2023110600000516` | 510 | `NO_DNS` — cannot resolve `bff.ggplus.ch` |
| `2023110600000014` | 409 | `OTHER` — unclassified |

Evidence: [`logs/Summary.md`](./gateway-online-status.2026-07-16/logs/Summary.md).

## §9 — Gateway OK: nothing to do (77)

Version ok, MDM green, connect online. No action.

## Machine-readable result

```json
{
  "workflow": "gateway-online-status",
  "site": "connect-ggplus-ch",
  "status": "passed",
  "started_at": "2026-07-16",
  "finished_at": "2026-07-16",
  "fixtures": {
    "version_threshold": "1.15.1.2",
    "excluded_partner_ids": [1000, 10000, 3086769],
    "log_lookback_days": 5
  },
  "captures": {
    "fleet_total": 370,
    "fleet_kept": 348,
    "site_visits": 268,
    "buckets": { "OK": 77, "FLASH_ONLINE": 19, "FLASH_OFFLINE": 219, "ANALYZE_LOGS": 2, "LTE_CHECK": 31 },
    "flash_reasons": { "VERSION_BELOW_THRESHOLD": 179, "NO_VERSION_REPORTED": 59 },
    "actions": {
      "VOR_ORT_FLASH_OFFLINE": 219,
      "VOR_ORT_FLASH_ONLINE": 19,
      "VOR_ORT_RESET_FLASH": 29,
      "VOR_ORT_SIGNAL_FLASH": 1,
      "ANALYZE_LOGS": 2,
      "PENDING_SIM_ACTIVATION": 1,
      "OK": 77
    },
    "swisscom_all_found": true,
    "swisscom_with_24h_traffic": 1
  },
  "evidence": [
    "projects/gateway-audit/results/gateway-online-status.2026-07-16/worklist.md",
    "projects/gateway-audit/results/gateway-online-status.2026-07-16/worklist.csv",
    "projects/gateway-audit/results/gateway-online-status.2026-07-16/triage.json",
    "projects/gateway-audit/results/gateway-online-status.2026-07-16/lte-results.json",
    "projects/gateway-audit/results/gateway-online-status.2026-07-16/logs/Summary.md"
  ]
}
```

## Notes / method

- **The connect side used no browser.** Fleet from `GET /gateway/api/v1/gateway/all`; live
  connect Status from the **SignalR hub** (`AddDeviceWatcher` → `ConnectionState`), because the
  REST list reports `connectionState: "Unconfigured"` for every gateway. Logs from
  `POST /gateway/api/v1/hmdm/logs` at severity WARNING (cumulative, includes ERROR).
- **Version-low split by connect Status** (new): 19 of 238 flash gateways are reachable in
  connect (online) and were separated into their own list — the cohort worth a remote push
  before a site visit. The other 219 are offline.
- **Swisscom was read-only.** For each of the 31 candidates: list search → SIM status + monthly
  volume; for the 7 with non-zero monthly, the *Letzte 24 Stunden* panel was opened to read the
  24h up/down. `monthly = 0` is a safe proxy for `24h = 0`. **No control that changes state was
  clicked** — the deactivated SIM (`…175`) was left untouched.
- **The fleet flaps between passes.** The Swisscom outcomes and the online/offline split were
  folded into the **saved snapshot** (not a re-fetch), so all artifacts agree.
