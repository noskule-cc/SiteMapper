# switch-partner-to-maschinenpark

Switch to a partner account and navigate to their Maschinenpark (machine list).

**At a glance** — Site: `connect-ggplus-ch` · Mode: deterministic · In: `$partner_name` → Out: _(no captures)_

Read-only navigation: it changes the session's partner context but writes no
records. Not a test — there is no `assert` step and no result file.

## Flow

```mermaid
flowchart TD
  subgraph P1["Phase 1 — reach Partner wechseln (page: dashboard)"]
    A["open sidebar (hamburger-menu)"] --> B["expand Adminbereich (chevron, not text)"] --> C["click Partner wechseln"]
  end

  subgraph P2["Phase 2 — switch context (page: partner-wechseln)"]
    D["input search-field = $partner_name"] --> E["click the matching partner-table row"]
  end

  subgraph P3["Phase 3 — reach Maschinenpark (page: dashboard)"]
    F["reopen sidebar (hamburger-menu)"] --> G["expand Geraete (chevron)"] --> H["click Maschinenpark"]
  end

  subgraph P4["Phase 4 — two-click drill-in (page: maschinenpark)"]
    I["click 1 — location-filter: pick the location"] --> J["click 2 — location row chevron: open the machine list"]
  end

  C --> D
  E -->|"sidebar collapsed itself on the switch"| F
  H --> I
  J --> V["verify: partner banner + MASCHINENPARK title + Bestehender Maschinenpark"]
```

## Why the shape is what it is

- **The sidebar is opened twice.** Phase 3 repeats the hamburger step because
  switching partner collapses the sidebar — see the gotchas in
  [`../pages/partner-wechseln.yaml`](../pages/partner-wechseln.yaml), which also
  cover the chevron-vs-text click targets used in phases 1 and 3.
- **The last two clicks are one navigation, not two.** Maschinenpark shows
  locations first and the machine list only after a second click; documented in
  [`../pages/maschinenpark.yaml`](../pages/maschinenpark.yaml). Dropping either
  click leaves you on the wrong level with no error.

## See also

- [`switch-partner-to-maschinenpark.yaml`](switch-partner-to-maschinenpark.yaml)
