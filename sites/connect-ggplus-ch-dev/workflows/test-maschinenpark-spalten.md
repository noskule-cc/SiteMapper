# test-maschinenpark-spalten

UI test for the Informations Spalten setting — toggling a column in Maschinenpark
Einstellungen adds or removes that column in the device list.

**At a glance** — Site: `connect-ggplus-ch-dev` · Mode: `deterministic` ·
In: fixtures `$partner_id`, `$location_id`, `$test_column` (`"Hersteller"`, a column
that is off by default) → Out: assertions only (no `capture`) · **Mutating** — the
column toggle is a persisted user setting; `teardown` unchecks it again.

## Flow

```mermaid
flowchart TD
  subgraph SETUP["setup"]
    S1["navigate /geraete/maschinenpark/$partner_id/$location_id"] --> S2["wait: device list renders"]
  end

  S2 --> A1

  subgraph STEPS["steps"]
    A1["baseline · assert column-headers does NOT contain $test_column"] --> B1
    B1["click location-settings-button (gear)<br/>opens the Maschinenpark Einstellungen modal"]
    B1 --> B2["assert tab-benutzer-einstellungen visible<br/>modal opened on its default tab"]
    B2 --> B3["click informations-spalten-checkbox scoped to $test_column"]
    B3 --> B4["click schliessen-button — closing persists the change"]
    B4 --> B5["wait: list re-renders with the new column"]
    B5 --> C1["assert column-headers now contains $test_column"]
  end

  C1 --> T1

  subgraph TEARDOWN["teardown — restore the setting"]
    T1["click location-settings-button — reopen settings"] --> T2["click informations-spalten-checkbox scoped to $test_column — uncheck"]
    T2 --> T3["click schliessen-button — persists the restore"]
  end
```

## What it proves

The Informations-Spalten checkboxes map 1:1 onto device-list columns: checking
`$test_column` adds that column header, unchecking removes it. The baseline assert at
the start is what makes the second assert meaningful — it establishes that the column
was not already present.

Element semantics and modal hazards (the modal intercepts clicks to the list, the
Schliessen button must be resolved by locator) live in the page maps linked below.

## See also

- [`test-maschinenpark-spalten.yaml`](test-maschinenpark-spalten.yaml) — source of truth
- Page maps: [`maschinenpark-geraeteliste.yaml`](../pages/maschinenpark-geraeteliste.yaml),
  [`maschinenpark-einstellungen.yaml`](../pages/maschinenpark-einstellungen.yaml)
- No result file recorded yet under [`../results/`](../results/).
