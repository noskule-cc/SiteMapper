# gateway-online-status — 2026-07-28

Full run of the gateway triage workflow (project **gateway-audit**) against the
19-box decision tree in [`gateway_online_status.drawio`](../workflows/gateway_online_status.drawio).
Assigns **one action per gateway**. Sections below follow the diagram's **Rapport** lane.

- **Workflow:** [`gateway-online-status.yaml`](../workflows/gateway-online-status.yaml)
- **Status:** **complete** — connect side (API) + Swisscom MDM-red branch (browser) both run
- **Operator:** noskule · Swisscom login: Benjamin Behringer
- **Version threshold:** ≥ 1.15.1.2 (inclusive)
- **Exclusions:** partnerId {1000, 10000, 3086769} → 379 total, **357 kept**
- **Method:** connect side is API-only (no browser). Swisscom side is a **read-only** UI drive
  (Vaadin, no REST API) — no SIM was reactivated, no setting changed.

> **Headline this run:** the MDM-red branch grew from 31 to **45** candidates, and a pattern
> appeared that was invisible at 31: **six SIMs sit at ~5 GB month-to-date and five of them are
> now `Deaktiviert`** — this looks like a data-cap cutoff, not six independent gateway faults.
> See §14.

## Worklist

| § (Rapport) | Action | Count | Site visit? |
|---|---|---:|:---:|
| **6** Version low, offline: Gateway Upgrade List | Vor Ort: Flash Gateway | **217** | ✓ |
| **4** Version low, online: Gateway Upgrade List | Vor Ort: Flash Gateway (reachable) | **18** | ✓ * |
| **17** Unknown Network Error: Gateway Reset List | Vor Ort: Reset (Flash) | **35** | ✓ |
| **19** Unknown MDM error: offline Logs Summary | Vor Ort: Signalstärke-Test, Flash | **5** | ✓ |
| **11** Connect offline: Logs Summary | Analyse Logs (desk) | **2** | — |
| **14** activate SIM (Deaktiviert) | recorded, **not** actioned | **5** | pending |
| **9** Gateway OK: nothing to do | — | **75** | — |
| **15** SIM nicht im Account | inventory | **0** | — |

**Site visits: 275** (217 + 18 Flash + 35 Reset + 5 Signalstärke). \* The 18 **online** flash
gateways are counted as visits, but they're reachable in connect — the cohort to try a remote
push on first.

Full list, complete serials:
[`worklist.md`](./gateway-online-status.2026-07-28/worklist.md) ·
[`worklist.csv`](./gateway-online-status.2026-07-28/worklist.csv) ·
[`triage.json`](./gateway-online-status.2026-07-28/triage.json) ·
[`lte-results.json`](./gateway-online-status.2026-07-28/lte-results.json)

## §6 — Version low, offline: Gateway Upgrade List (217) — **flash priority**

Version low **and** offline in connect. No remote lever, so every one is a guaranteed site
visit — **this is the list to flash first.** Split by reason:

| Reason | Count | Meaning |
|---|---:|---|
| `VERSION_BELOW_THRESHOLD` | **160** | runs a connect-app version below 1.15.1.2 |
| `NO_VERSION_REPORTED` | **57** | never reported a connect version (grey MDM / pre-Headwind firmware) |

Full list: [`worklist.md`](./gateway-online-status.2026-07-28/worklist.md) →
*Vor Ort: Flash Gateway (Version low, offline)*.

## §4 — Version low, online: Gateway Upgrade List (18)

Version low **but reachable** in connect — try a remote/OTA push before booking a truck.
Work these **after** the offline list.

| Reason | Count | Meaning |
|---|---:|---|
| `VERSION_BELOW_THRESHOLD` | **17** | runs a connect-app version below 1.15.1.2 |
| `NO_VERSION_REPORTED` | **1** | never reported a connect version |

The 58 no-version gateways across both lists remain a **reporting** gap (never enrolled in
Headwind), not an update regression — one migration, not 235 separate failures.

## §19 / §17 / §14 — the MDM-red branch (45 gateways, Swisscom read-only)

**All 45 candidates were found in the Swisscom account** → §15 is empty again. SIM status:
39 Aktiv, 6 Deaktiviert.

| Outcome | Count | Rule |
|---|---:|---|
| **§19** Signalstärke-Test, Flash | **5** | LTE traffic in last 24h (alive on cellular, offline in connect) |
| **§17** Reset (Flash) | **35** | no 24h traffic, SIM active |
| **§14** recorded, not actioned | **5** | SIM **Deaktiviert** and silent — see below |

### §19 — alive on cellular, unreachable in connect (5)

Traffic in the last 24 h proves the device and its SIM are working; the fault is between the
gateway and connect (handshake/DNS), so it needs an on-site Signalstärke-Test + Flash rather
than a SIM action.

| Serial | Vertragsnr. | Partner | ↑ 24 h | ↓ 24 h | Monthly | SIM |
|---|---|---|---:|---:|---:|---|
| `2023110600000335` | 3134620 | Bäckerei Zingg GmbH | 125.63 MB | 1.00 GB | 3.20 GB | Aktiv |
| `2023110600000049` | 2435586 | Grindelwald Bakery GmbH | 15.34 MB | 102.06 MB | 5.03 GB | **Deaktiviert** |
| `2023110600000377` | 2202991 | Remimag AG Wirtschaft Brandenberg | 915.82 kB | 29.34 MB | 0.00 Bytes | Aktiv |
| `2023110600000239` | 1004932 | Gemmet Handels AG | 548.00 Bytes | 805.00 Bytes | 2.21 GB | Aktiv |
| `2023110600000504` | 3059307 | Migrantenseelsorge der Röm.-kath. Kirche Luzern | 104.00 Bytes | 156.00 Bytes | 37.17 kB | Aktiv |

Two of these deserve a second look:

- **`2023110600000049` — Deaktiviert, yet it moved 102 MB down in the last 24 h.** The tree asks
  node 12 (traffic) *before* node 13 (SIM status), so it lands in §19 and never reaches the SIM
  question — which is the right call: a device that is moving data does not need its SIM
  reactivated. But *a deactivated SIM that still carries traffic* is contradictory, and the
  reading was re-taken independently and reproduced exactly. Either the deactivation is very
  recent (within the 24 h window) or it has not taken effect on the network. Worth one manual
  check before a technician is dispatched.
- **`2023110600000377`** shows 30 MB in the last 24 h but **0.00 Bytes month-to-date** — the
  monthly counter appears to have just rolled over or been reset; the 24 h figure is the one to
  trust here.
- **`2023110600000239` and `…504`** move only a few hundred bytes — keep-alive chatter, alive
  but barely.

Note `2023110600000335` is MDM **Yellow** (not Red) and is burning 1 GB/day; at that rate it
reaches the ~5 GB mark within days — see §14.

### §17 — SIM active but silent, on-site Reset (35)

0 Bytes in both directions over the last 24 h with an **active** SIM. **13 of the 35 moved real
volume earlier this month and have since gone silent** — these died recently rather than never
having worked, which usually points at the site (power, position, antenna) rather than at
provisioning:

| Serial | Vertragsnr. | Partner | Monthly | Last 24 h |
|---|---|---|---:|---:|
| `2023110600000493` | 1671006 | Pestalozzi Jugendstätte Burghof | 2.78 GB | 0.00 Bytes |
| `2023110600000007` | 2317856 | KiBiZ Langmatt | 1.51 GB | 0.00 Bytes |
| `2023110600000489` | 2918682 | Hotel Ochsen | 1.06 GB | 0.00 Bytes |
| `2023110600000436` | 2109991 | Shamrock Irish Pub | 887.59 MB | 0.00 Bytes |
| `2023110600000147` | 3101945 | Jugendraum EG | 615.19 MB | 0.00 Bytes |
| `2023110600000428` | 2794303 | Restaurant Spiegelberg | 607.20 MB | 0.00 Bytes |
| `2023110600000375` | 3129595 | V-Zug AG Zugorama Crissier | 112.93 MB | 0.00 Bytes |
| `2023110600000399` | 3135249 | Schulhaus Mattenbach | 68.16 MB | 0.00 Bytes |
| `2023110600000395` | 3135249 | Schulhaus Mattenbach | 37.02 MB | 0.00 Bytes |
| `2023110600000353` | 1618704 | Restaurant O-Bolles | 32.41 MB | 0.00 Bytes |
| `2023110600000096` | 1664032 | Primarschule Hinwil | 31.67 MB | 0.00 Bytes |
| `2023110600000386` | 3135249 | Schulhaus Mattenbach | 31.21 MB | 0.00 Bytes |
| `2023110600000141` | 3134980 | Schulprovisorium / Modulbau | 30.83 MB | 0.00 Bytes |

**Schulhaus Mattenbach (Vertragsnr. 3135249) appears three times** (`…386`, `…395`, `…399`), all
silent in the last 24 h. Three gateways at one address failing together is a *site* problem —
one visit, not three tickets. Check that address before dispatching individually.

`2023110600000493` continues its trajectory from earlier runs: 2.78 GB month-to-date, DNS
failures on 2026-07-14, and now fully silent.

The remaining 22 show 0 Bytes both for the month and the last 24 h — never-working or
long-dead installs.

### §14 — deactivated SIM, recorded only (5) — **likely a data cap, not five faults**

**No SIM was reactivated.** Node 14 mutates Swisscom state and is operator-gated; the run
records these and stops.

| Serial | Vertragsnr. | Partner | Swisscom status | Monthly | 24 h |
|---|---|---|---|---:|---:|
| `2023110600000122` | 2249953 | Viva Luzern AG Eichhof Hotellerie | Deaktiviert | 5.03 GB | 0.00 Bytes |
| `2023110600000330` | 2235126 | Argenti Olivia & Fredy von Büren | Deaktiviert | 5.03 GB | 0.00 Bytes |
| `2023110600000398` | 2769186 | Kantonsspital Graubünden | Deaktiviert | 5.01 GB | 0.00 Bytes |
| `2023110600000296` | 3081897 | Japigo GmbH | Deaktiviert | 5.01 GB | 0.00 Bytes |
| `2023110600000175` | 2187845 | Kirchgemeindehaus | Deaktiviert | 5.00 GB | 0.00 Bytes |

**All five sit between 5.00 and 5.03 GB month-to-date** — and so does `2023110600000049` in §19,
the sixth deactivated SIM. Six SIMs independently stopping within 30 MB of each other is not a
coincidence: this is a **~5 GB monthly cap cutting them off**, not six gateway failures.

That changes the handling. Reactivating them one by one treats the symptom; they will be cut off
again next month at the same threshold. What this needs is a decision about the tariff/cap and
about *why* these particular gateways consume 5 GB when most of the fleet consumes a few dozen
MB. `2023110600000335` (§19, 1 GB/day) is the next one heading for the same cliff.

**Requested decision:** reactivate these five now (a one-line change per SIM in the Swisscom
portal, which will clear them to §9 if the gateway recovers), investigate the consumption first,
or both? Nothing was changed pending your answer. `2023110600000175` has now been sitting
deactivated across three consecutive runs (2026-07-14, -16, -28).

## §11 — Connect offline: Logs Summary (2)

MDM green but connect offline — we can still reach these, so their logs are fresh:

| Serial | Vertragsnr. | Partner | WARNING+ERROR (5 d) | Dominant signature |
|---|---|---|---:|---|
| `2023110600000164` | 2568619 | Kulturzentrum Braui | 1705 | `NO_DNS` (1323) |
| `2023110600000231` | 1004932 | Gemmet Handels AG | 195 | `OTHER` (64), `NO_DNS` (64) |

Both are dominated by `NO_DNS` — *cannot resolve `bff.ggplus.ch` at all.* That is genuine
network loss at the site, **not** the "connect says offline but the device is fine" false
negative that `HUB_HANDSHAKE` would indicate. `HUB_HANDSHAKE` is a minority signature in both
(19 and 30 entries). Treat these as connectivity faults, not as connect-side reporting errors.

Evidence: [`logs/Summary.md`](./gateway-online-status.2026-07-28/logs/Summary.md).

## §9 — Gateway OK: nothing to do (75)

Version ok, MDM green, connect online. No action.

## Change since 2026-07-16

| Metric | 2026-07-16 | 2026-07-28 | Δ |
|---|---:|---:|---:|
| Fleet total / kept | 370 / 348 | 379 / 357 | +9 / +9 |
| OK (§9) | 77 | 75 | −2 |
| Flash offline (§6) | 219 | 217 | −2 |
| Flash online (§4) | 19 | 18 | −1 |
| LTE_CHECK candidates | 31 | 45 | **+14** |
| Signalstärke-Test (§19) | 1 | 5 | +4 |
| Reset (§17) | 29 | 35 | +6 |
| Pending SIM (§14) | 1 | 5 | **+4** |
| **Site visits** | **268** | **275** | **+7** |

The flash backlog is essentially unmoved in twelve days (238 → 235). The movement is all in the
MDM-red branch, which grew by 45 %.

## Machine-readable result

```json
{
  "workflow": "gateway-online-status",
  "site": "connect-ggplus-ch",
  "status": "passed",
  "started_at": "2026-07-28",
  "finished_at": "2026-07-28",
  "fixtures": {
    "version_threshold": "1.15.1.2",
    "excluded_partner_ids": [1000, 10000, 3086769],
    "swisscom_account_id": "02001639",
    "log_lookback_days": 5
  },
  "captures": {
    "fleet_total": 379,
    "fleet_kept": 357,
    "site_visits": 275,
    "buckets": { "OK": 75, "FLASH_ONLINE": 18, "FLASH_OFFLINE": 217, "ANALYZE_LOGS": 2, "LTE_CHECK": 45 },
    "flash_reasons": { "VERSION_BELOW_THRESHOLD": 177, "NO_VERSION_REPORTED": 58 },
    "flash_reasons_offline": { "VERSION_BELOW_THRESHOLD": 160, "NO_VERSION_REPORTED": 57 },
    "flash_reasons_online": { "VERSION_BELOW_THRESHOLD": 17, "NO_VERSION_REPORTED": 1 },
    "actions": {
      "VOR_ORT_FLASH_OFFLINE": 217,
      "VOR_ORT_FLASH_ONLINE": 18,
      "VOR_ORT_RESET_FLASH": 35,
      "VOR_ORT_SIGNAL_FLASH": 5,
      "VOR_ORT_ANALYSE": 0,
      "ANALYZE_LOGS": 2,
      "SIM_NICHT_IM_ACCOUNT": 0,
      "PENDING_SIM_ACTIVATION": 5,
      "PENDING_LTE": 0,
      "OK": 75
    },
    "lte_skipped_wifi": 0,
    "no_state_received": 0,
    "swisscom_all_found": true,
    "swisscom_sim_status": { "Aktiv": 39, "Deaktiviert": 6 },
    "swisscom_with_24h_traffic": 5,
    "sims_at_data_cap": 6
  },
  "evidence": [
    "projects/gateway-audit/results/gateway-online-status.2026-07-28/worklist.md",
    "projects/gateway-audit/results/gateway-online-status.2026-07-28/worklist.csv",
    "projects/gateway-audit/results/gateway-online-status.2026-07-28/triage.json",
    "projects/gateway-audit/results/gateway-online-status.2026-07-28/lte-results.json",
    "projects/gateway-audit/results/gateway-online-status.2026-07-28/logs/Summary.md"
  ]
}
```

## Notes / method

- **The connect side used no browser.** Fleet from `GET /gateway/api/v1/gateway/all`; live
  connect Status from the **SignalR hub** (`AddDeviceWatcher` → `ConnectionState`), because the
  REST list reports `connectionState: "Unconfigured"` for every gateway. Logs from
  `POST /gateway/api/v1/hmdm/logs` at severity WARNING (cumulative, includes ERROR).
- **Every gateway returned a SignalR state** (`no_state_received: 0`) and **no WiFi gateway
  reached node 12** (`lte_skipped_wifi: 0`), so §-less edge cases are empty this run.
- **The Swisscom leg was read differently this time — and it is much cheaper.** Instead of 45
  individual searches, the subscriptions list (599 rows, Vaadin-virtualised) was scroll-harvested
  once to get IMSI + SIM status + monthly volume for the whole account; the run then jumped
  straight to each detail page by IMSI. The *Letzte 24 Stunden* panel was opened for **all 45**
  candidates rather than only those with non-zero monthly volume — which is what caught
  `2023110600000377` (0.00 Bytes monthly but 30 MB in the last 24 h), a gateway the previous
  method's `monthly = 0 → 24h = 0` shortcut would have mis-filed into §17.
- **Every reading was identity-checked.** Before trusting any traffic number, both the page's
  IMSI *and* its `Gateway Ausprägung` had to match the serial being asked about, and were
  re-checked after the read; the previous subscription's panel had to be torn down first. No read
  was accepted from a stale or mismatched page (`stale_guard` clean on all 45).
- **Swisscom was read-only.** No status pencil, no mutating control, no SIM reactivation.
- **The fleet flaps between passes.** The Swisscom outcomes were folded into the **saved
  snapshot** rather than a re-fetch, so triage.json, worklist.\* and lte-results.json all agree.

### Two script issues found during this run — **fixed**

1. `get_gateway_logs.py --bucket` **failed**: it calls `build_table()`, which re-opens the SignalR
   hub, and the server answered the second connection of the session with
   `Handshake status 404`.
2. `get_gateway_status_table.py --out` had the same shape of problem — it re-runs `build_table()`,
   so the deliverable would describe a *different* fleet snapshot than the one the Swisscom leg
   was derived from.

Both now take **`--triage FILE`**, reusing a saved `triage.json` instead of re-sweeping (new
`load_table()` in `get_gateway_status_table.py`). The run's deliverable was regenerated through
the new flag and is byte-for-byte identical to the hand-driven workaround used during the run,
so nothing above depends on the workaround. A run now sweeps **once**; the workflow YAML and
`scripts/README.md` were updated to pass `--triage` at every later step.
