# test-maschinenpark-gruppierung-config

UI test for custom Gerätegruppierungen — creating a Benutzer-Gruppierung scheme in
Maschinenpark Einstellungen makes it appear as an option in the Gerätegruppierungen
dropdown.

**At a glance** — Site: `connect-ggplus-ch-dev` · Mode: `deterministic` ·
In: fixtures `$partner_id`, `$location_id`, `$grouping_type` (`"Benutzer-Gruppierung"`,
user-scoped = smallest blast radius), `$grouping_name` (`"SiteMapper Test Gruppe"`)
→ Out: assertions only (no `capture`) · **Mutating** — creates a grouping scheme and
deletes it in `teardown`.

## Flow

```mermaid
flowchart TD
  subgraph SETUP["setup"]
    S1["navigate /geraete/maschinenpark/$partner_id/$location_id"] --> S2["wait: device list renders"]
  end

  S2 --> A1

  subgraph STEPS["steps — create the scheme, then see it in the dropdown"]
    A1["click location-settings-button (gear)"] --> A2["click tab-geraetegruppierungen"]
    A2 --> A3["click add-sortierungsgruppierung-button — new scheme row"]
    A3 --> A4["input gruppierung-typ-select = $grouping_type"]
    A4 --> A5["input gruppensortierung-name-input = $grouping_name"]
    A5 --> A6["click schliessen-button — persists the new scheme"]
    A6 --> A7["wait: dropdown picks up the new option"]
    A7 --> B1["click device-grouping-dropdown — open it"]
    B1 --> B2["assert dropdown lists $grouping_name<br/>under BENUTZER-GRUPPIERUNGEN"]
    B2 --> B3["key 'Escape' — close the dropdown<br/>without changing the active grouping"]
  end

  B3 --> T1

  subgraph TEARDOWN["teardown — delete only the scheme this test created"]
    T1["click location-settings-button — reopen settings"] --> T2["click tab-geraetegruppierungen"]
    T2 --> T3["wait: scheme rows render before targeting one"]
    T3 --> T4["click delete-row-button SCOPED to $grouping_name<br/>the trash icon is identical on every row"]
    T4 --> T5["wait: row removal re-renders and SHRINKS the modal"]
    T5 --> T6["guard · assert settings-modal no longer contains $grouping_name<br/>catches a delete that hit the wrong row"]
    T6 --> T7["click schliessen-button by its 'Schliessen' text locator<br/>NEVER by a remembered coordinate"]
  end
```

## Why teardown is the risky half

The teardown carries its own assertion — the only assert outside `steps` — because the
delete is the dangerous operation, not the create. The trash icon is identical on every
scheme row and deleting a row shifts the remaining controls upward, so an unscoped or
coordinate-based click can silently remove a pre-existing, shared Partner-Gruppierung.
Scoping the delete by `$grouping_name`, asserting the row is gone, and re-locating
Schliessen by text are all load-bearing. See the page map for the full hazard note.

## See also

- [`test-maschinenpark-gruppierung-config.yaml`](test-maschinenpark-gruppierung-config.yaml) — source of truth
- Page maps: [`maschinenpark-geraeteliste.yaml`](../pages/maschinenpark-geraeteliste.yaml),
  [`maschinenpark-einstellungen.yaml`](../pages/maschinenpark-einstellungen.yaml)
- Companion test for the STANDARD groupings:
  [`test-maschinenpark-geraeteliste.md`](test-maschinenpark-geraeteliste.md)
- No result file recorded yet under [`../results/`](../results/).
