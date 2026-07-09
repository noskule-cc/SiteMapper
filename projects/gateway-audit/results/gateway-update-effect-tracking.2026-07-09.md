# gateway-update-effect-tracking — 2026-07-09

Run of the cross-site gateway firmware-rollout audit (project **gateway-audit**),
correlating GG+connect gateway-monitoring with the Swisscom M2M portal.

- **Workflow:** `projects/gateway-audit/workflows/gateway-update-effect-tracking.yaml`
- **Sites:** connect-ggplus-ch, portal-m2m-swisscom-ch
- **Status:** passed (ran to completion)
- **Operator:** Benjamin Behringer (live session)
- **Version threshold:** 1.15.1.2 (inclusive)
- **Exclusions:** Vertragsnummer {1000, 10000, 3086769}; gateways with empty Version
- **Fleet:** 372 gateways total → 289 kept after exclusions

## Headline metrics

| # | Metric | Count |
|---|--------|------:|
| 1 | Headwind online (green) **but** gateway Status offline | **5** |
| 2 | Version ≥ 1.15.1.2 **but** Headwind offline (red) | **34** |
| 3 | Status offline **and** version ≥ 1.15.1.2 **and** last-24h Swisscom traffic | **5** |

## Metric 3 detail

32 unique offline + updated gateways were checked on the Swisscom portal
(search serial → open subscription → expand *Letzte 24 Stunden*):

- **5 with last-24h traffic** (offline in monitoring, but the SIM is alive)
- **25 with zero traffic** (genuinely silent)
- **2 not found** on Swisscom account 02001639 (serials absent — cannot be checked here)

### Traffic-positive (metric 3 hits)

| Serial | Partner | Headwind | ↑ 24h | ↓ 24h |
|--------|---------|:--------:|------:|------:|
| …296 | Japigo GmbH | 🟢 | 47.32 MB | 341.40 MB |
| …448 | Amrize Technology Switzerland GmbH | 🟢 | 39.32 MB | 247.93 MB |
| …493 | Pestalozzi Jugendstätte Burghof | 🟢 | 32.40 MB | 10.04 MB |
| …182 | GHG Rosenberg (M. Bühler) | 🟢 | 10.87 MB | 45.43 MB |
| …504 | Migrantenseelsorge Luzern | 🔴 | 184 B | 295 B *(negligible)* |

### Not found on Swisscom (excluded from the traffic count)

| Serial | Partner | Vertrag | Headwind |
|--------|---------|---------|:--------:|
| …136 | Lakeside School | 2998514 | 🔴 |
| …427 | Kinderkrippe Hexenburg | 2936574 | 🔴 |

## Finding

**4 of the 5 traffic-positive gateways also have Headwind = green** (all except …504).
For those, the monitoring **"offline" Status is a false negative** — Headwind reports the
management channel online *and* the SIM is moving real MB of data, so the gateway is in
fact connected. The gateway's own connection-status reporting is what is stale, not the
connectivity. …504 is borderline (a few hundred bytes = keep-alive traffic, not usage).

## Machine-readable result

```json
{
  "workflow": "gateway-update-effect-tracking",
  "site": "connect-ggplus-ch",
  "status": "passed",
  "started_at": "2026-07-09",
  "finished_at": "2026-07-09",
  "fixtures": { "version_threshold": "1.15.1.2", "excluded_vertragsnummern": ["1000", "10000", "3086769"] },
  "captures": {
    "fleet_total": 372,
    "fleet_kept": 289,
    "metric1_count": 5,
    "metric2_count": 34,
    "metric3_count": 5,
    "metric3_candidates_unique": 32,
    "metric3_no_traffic": 25,
    "metric3_not_found_on_swisscom": 2
  },
  "evidence": [
    "projects/gateway-audit/results/gateway-update-effect-tracking.2026-07-09/metric3-raw.json"
  ]
}
```

## Notes / method

- Metrics 1 & 2 are computed by a DOM scrape of the monitoring table (Status = router-icon
  colour; Headwind = `.status-dot` class; Version numeric compare). The CSV export currently
  omits the Headwind and Version columns, so DOM scraping is required.
- Metric 3 required driving the Swisscom Vaadin UI once per serial (no per-IMSI REST API):
  clear search → type serial → open detail → scroll to bottom → expand *Letzte 24 Stunden*
  → read Daten hoch/heruntergeladen. Detail sub-panels are Angular virtual-scroll (only in
  the DOM when in the viewport) and the expand state does not persist across SIMs.
- Reliability note: after a serial returns 0 results the list stays scrolled, which can shift
  the search box; the flow scrolls the list to top before each search to avoid this.
- Full per-serial dataset (all 32, incl. IMSIs and byte counts): see the evidence JSON.
