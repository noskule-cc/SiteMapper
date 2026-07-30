# gateway-online-status — 2026-07-14

First full run of the gateway triage workflow (project **gateway-audit**). Walks the
decision tree in `gateway_online_status.drawio` over the whole fleet and assigns **one
action per gateway**.

- **Workflow:** `projects/gateway-audit/workflows/gateway-online-status.yaml`
- **Status:** passed — connect side + Swisscom LTE branch both complete
- **Operator:** Benjamin Behringer
- **Version threshold:** ≥ 1.15.1.2 (inclusive)
- **Exclusions:** partnerId {1000, 10000, 3086769}
- **Fleet:** 375 gateways → **353 kept**
- **Method:** connect side is API-only (no browser). Swisscom side is a UI drive (Vaadin, no REST API).

## The worklist

| Action | Count |  
|---|---:|
| Vor Ort: Restart, Flash Gateway | **1** |
| Vor Ort: Flash Gateway | **243** |
| Vor Ort: Analyse | **29** |
| Analize Logs from Headwind | 1 |
| SIM nicht im Account (Inventar, kein Einsatz) | 2 |
| SIM deaktiviert (administrativ, kein Einsatz) | 1 |
| OK — nichts zu tun | **76** |

→ **273 site visits.** Full list, grouped by action, with complete serials:
[`worklist.md`](./gateway-online-status.2026-07-14/worklist.md) ·
[`worklist.csv`](./gateway-online-status.2026-07-14/worklist.csv)

## Headline: only ~22% of the fleet is healthy

**76 of 353 gateways are OK.** The other 277 need something. But the shape of that work
is not what the raw numbers suggest — see below.

## The 243 flash candidates are one migration, not 243 failures

The tree routes them all to *Vor Ort: Flash Gateway*, and the action is right. But the
reason is not "the update broke". Broken down by MDM state:

| MDM | Count | What it actually means |
|---|---:|---|
| **Grey** | **232** | Not enrolled in Headwind at all. `hmdmConnectVersionInstalled` is `null` — the version shown (`1.14.1.0`) is the **firmware** version, not a connect-app version |
| Red | 9 | genuinely running an old connect app |

**232 of the 243 have never reported a connect version**, because they are on
pre-Headwind firmware and are not managed. This is *"the rollout never reached 232
devices that were never enrolled"* — one large migration — not *"the rollout regressed
on 243 devices"*.

⚠️ It also exposes a flaw in the tree: for a grey gateway the version compared against
`1.15.1.2` is a **firmware** version, a different numbering scheme from the connect-app
version the threshold refers to. It reaches the right action by luck, not by logic.
Recommend rephrasing that lane as *"enrolled in Headwind and on connect ≥ 1.15.1.2?"* —
same outcome, honest reasoning.

## The one live gateway: 2023110600000493

| Field | Value |
|---|---|
| Vertragspartner | Pestalozzi Jugendstätte Burghof |
| Version | 1.15.1.3 |
| MDM | 🟡 Yellow *(was Green at the start of this run)* |
| connect Status | offline |
| Swisscom 24 h | **↑ 17.77 MB / ↓ 69.15 MB** (monthly 1.86 GB) |
| Headwind log | **9,633 × `Unable to resolve host "bff.ggplus.ch"`** |

**This gateway is alive and moving 87 MB a day, but cannot resolve connect's hostname.**
Not a dead gateway, not a dead SIM — a **DNS failure**. It is burning real data on
retries while unreachable. → *Vor Ort: Restart, Flash Gateway*.

It also demonstrates the tree working: its MDM flipped Green → Yellow *between* the two
halves of this run, which correctly rerouted it from *"ask the device"* (Headwind logs)
to *"ask the network"* (Swisscom LTE).

## The 29 "Vor Ort: Analyse" are genuinely silent

Of 34 gateways sent to the Swisscom lookup, **only one had any 24 h traffic at all**
(`…504`, ~2 kB — keep-alive). The rest are `0.00 Bytes` in both directions.

Six of them moved **substantial volume earlier this month** and have since gone quiet —
they died recently rather than never having worked:

| Serial | Monthly | Last 24 h |
|---|---:|---:|
| `2023110600000436` | 887.59 MB | 0.00 Bytes |
| `2023110600000147` | 615.19 MB | 0.00 Bytes |
| `2023110600000375` | 112.93 MB | 0.00 Bytes |
| `2023110600000118` | 56.80 MB | 0.00 Bytes |
| `2023110600000019` | 50.43 MB | 0.00 Bytes |
| `2023110600000141` | 30.83 MB | 0.00 Bytes |

## Not a site visit (3 gateways)

| Serial | Vertragspartner | Why |
|---|---|---|
| `2023110600000136` | Lakeside School | Not on Swisscom account 02001639 — **also missing on 2026-07-09**. SIM-inventory problem; a technician cannot fix it. |
| `2023110600000427` | Kinderkrippe Hexenburg | Same — missing two runs running. |
| `2023110600000164` | Kulturzentrum Braui | SIM status **`Deaktiviert`** — switched off, not merely silent. Administrative fix. |

Two SIMs absent from the account across two separate runs is a signal the SIM inventory
needs reconciling, not a gateway fault.

## Corrections made during this run

Three things would have produced **wrong numbers** and were fixed before reporting:

1. **"Throughput minimal" was a unit-string test** (`both directions are Byte-level`).
   `2023110600000504` reads 316 B up / **1.71 kB** down — by that rule *not* minimal, so
   it would have been reported as a healthy, data-moving gateway needing only a restart.
   ~2 kB in 24 h is keep-alive. Replaced with a magnitude test: **< 1 MB per 24 h = minimal**.
2. **The Swisscom serial is not always in "Gateway Ausprägung"** — for some SIMs
   (e.g. `2023110600000092`) it is in the **Label** column instead. The old recipe matched
   only on Ausprägung and would have mis-read or lost those.
3. **The Swisscom grid lags the search box.** Reading `rows[0]` after a fixed wait returned
   the *previous* serial's row. Every lookup is now polled until the grid matches the serial
   asked for, and every detail reading is verified against the IMSI in the page URL.

## Machine-readable result

```json
{
  "workflow": "gateway-online-status",
  "site": "connect-ggplus-ch",
  "status": "passed",
  "started_at": "2026-07-14",
  "finished_at": "2026-07-14",
  "fixtures": {
    "version_threshold": "1.15.1.2",
    "excluded_partner_ids": [1000, 10000, 3086769],
    "log_lookback_days": 5,
    "minimal_traffic_bytes": 1000000
  },
  "captures": {
    "fleet_total": 375,
    "fleet_kept": 353,
    "site_visits": 273,
    "actions": {
      "VOR_ORT_RESTART_FLASH": 1,
      "VOR_ORT_FLASH": 243,
      "VOR_ORT_ANALYSE": 29,
      "ANALYZE_LOGS": 1,
      "SIM_NICHT_IM_ACCOUNT": 2,
      "SIM_DEAKTIVIERT": 1,
      "OK": 76
    },
    "flash_not_enrolled_in_headwind": 232,
    "swisscom_lookups": 34,
    "swisscom_with_24h_traffic": 2
  },
  "evidence": [
    "projects/gateway-audit/results/gateway-online-status.2026-07-14/worklist.md",
    "projects/gateway-audit/results/gateway-online-status.2026-07-14/worklist.csv",
    "projects/gateway-audit/results/gateway-online-status.2026-07-14/triage.json",
    "projects/gateway-audit/results/gateway-online-status.2026-07-14/lte-results.json",
    "projects/gateway-audit/results/gateway-online-status.2026-07-14/logs/Summary.md"
  ]
}
```

## Notes / method

- **The connect side used no browser at all.** Fleet from `GET /gateway/api/v1/gateway/all`;
  the live connect Status from the **SignalR hub** (`AddDeviceWatcher` → `ConnectionState`),
  because the REST list reports `connectionState: "Unconfigured"` for every gateway and
  must not be trusted. Logs from `POST /gateway/api/v1/hmdm/logs` at severity WARNING
  (cumulative, so it already includes ERROR).
- **Swisscom shortcut:** 24 of the 34 serials showed `0.00 Bytes` for the entire
  month-to-date, so they cannot have moved data in the last 24 h. Validated against
  `2023110600000012` (monthly 0 → 24 h 0/0) before relying on it. Only the 7 with non-zero
  monthly volume were opened individually — and 6 of those 7 turned out to have **zero**
  24 h traffic, so the monthly figure alone would have been a misleading proxy.
- The SignalR handshake returned a transient 404 on one attempt and succeeded on retry;
  worth adding a retry to `get_connection_states()`.
- **The fleet is live and moves between runs** — `2023110600000493` changed MDM state
  mid-run. Any two runs will differ slightly; the dated run folder keeps each one intact.
- `2023110600000097` is registered on **two** gateways/partners in connect (Bakery Bakery AG
  and Bakery Bakery AG Länggasse) with one Swisscom SIM. Worth investigating as a data issue.
