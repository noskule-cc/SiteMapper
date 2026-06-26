# Test run: test-maschinenpark-geraeteliste

- **Workflow:** `test-maschinenpark-geraeteliste`
- **Site:** `connect-ggplus-ch-dev` (https://dev-connect.ggplus.ch)
- **Target:** `/geraete/maschinenpark/10000/10000`
- **Date:** 2026-06-26
- **Runner:** `/test` (LLM host, Chrome MCP)
- **Status:** ✅ passed (14/14 assertions)

## Assertions

| # | Level | Element | Expect | Actual | Pass |
|---|-------|---------|--------|--------|------|
| 1 | L1 | location-header | contains "Gehrig Group AG test" | "10000 Gehrig Group AG test" | ✅ |
| 2 | L1 | device-filter | visible | present | ✅ |
| 3 | L1 | device-grouping-dropdown | value "IOT-Geräte" | "IOT-Geräte" | ✅ |
| 4 | L1 | favoriten-section | visible | present (2 Geräte) | ✅ |
| 5 | L1 | neu-section | visible | present (8 Geräte) | ✅ |
| 6 | L1 | bestehender-section | visible | present (119 Geräte) | ✅ |
| 7 | L5 | device-row "Diverse Kaffee Mastrena" | visible | present (Favoriten + Bestehender) | ✅ |
| 8 | L5 | device-row "Diverse Wasseraufbereitung" | absent | not present after filter | ✅ |
| 9 | L4 | no-match-message | visible | "Für den angegeben Filter wurden keine Maschinen gefunden." | ✅ |
| 10 | L5 | device-row "Diverse Wasseraufbereitung" (after clear) | visible | restored | ✅ |
| 11 | L5 | location-list-sidebar "1020 Renens" | visible | present | ✅ |
| 12 | L5 | location-list-sidebar "8152 Glattbrugg" | absent | not in sidebar | ✅ |
| 13 | L2 | geraet-vorschau / open-full-view-button | visible | "Vollansicht öffnen" present | ✅ |
| 14 | L2 | (url) | url_matches `/geraete/maschinenpark/.*/geraet/.*` | `/geraete/maschinenpark/10000/10000/geraet/7f8a8004-…` | ✅ |

## Machine-readable result

```json
{
  "workflow": "test-maschinenpark-geraeteliste",
  "site": "connect-ggplus-ch-dev",
  "target": "/geraete/maschinenpark/10000/10000",
  "date": "2026-06-26",
  "status": "passed",
  "fixtures": {
    "partner_id": "10000",
    "location_id": "10000",
    "location_name": "Gehrig Group AG test",
    "device_filter_term": "Mastrena",
    "matching_device": "Diverse Kaffee Mastrena",
    "non_matching_device": "Diverse Wasseraufbereitung",
    "location_filter_term": "Renens",
    "location_match": "1020 Renens",
    "location_nonmatch": "8152 Glattbrugg"
  },
  "counts": { "total": 14, "passed": 14, "failed": 0 },
  "assertions": [
    { "id": "location-header.contains", "level": "L1", "expect": {"contains": "Gehrig Group AG test"}, "actual": "10000 Gehrig Group AG test", "pass": true },
    { "id": "device-filter.visible", "level": "L1", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "device-grouping-dropdown.value", "level": "L1", "expect": {"value": "IOT-Geräte"}, "actual": "IOT-Geräte", "pass": true },
    { "id": "favoriten-section.visible", "level": "L1", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "neu-section.visible", "level": "L1", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "bestehender-section.visible", "level": "L1", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "device-row.matching.visible", "level": "L5", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "device-row.nonmatching.absent", "level": "L5", "expect": "absent", "actual": "absent", "pass": true },
    { "id": "no-match-message.visible", "level": "L4", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "device-row.nonmatching.restored", "level": "L5", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "sidebar.location-match.visible", "level": "L5", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "sidebar.location-nonmatch.absent", "level": "L5", "expect": "absent", "actual": "absent", "pass": true },
    { "id": "geraet-vorschau.open-full-view.visible", "level": "L2", "expect": "visible", "actual": "visible", "pass": true },
    { "id": "url.geraet-segment", "level": "L2", "expect": {"url_matches": "/geraete/maschinenpark/.*/geraet/.*"}, "actual": "/geraete/maschinenpark/10000/10000/geraet/7f8a8004-615f-1025-a864-0c14e05f0000", "pass": true }
  ]
}
```

## Notes

- **Volatile counts:** section counts differed from earlier runs (Neu 6→7→8, Bestehender 121→120→119). The test reads/asserts row *identity* via value-scoping, not counts, so it stays green across data churn.
- **Scope matters:** the location address "8152 Glattbrugg" also appears in the right-pane header, so assertion #12 must be scoped to `location-list-sidebar` — an unscoped `absent` check would wrongly fail.
- **Async + live filtering:** the list renders after navigation and filters apply live; `wait` steps precede the dependent assertions.
- **Clear control:** clearing uses the mapped `device-filter-clear` (X) button — browser form-input can't reliably submit an empty string.
