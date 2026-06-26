# Test inventory — Maschinenpark (dev)

What a user can do on the Maschinenpark pages, and what each item should assert.
Coverage status: **[done]** in `workflows/test-maschinenpark-geraeteliste.yaml`,
**[confirmed]** seen live, **[inferred]** not yet exercised.

> Hermeticity: grouping (and sort) **persist per user across sessions**, so every
> test must reset them in a `setup` phase. Favorites are mutable shared data —
> assert device *identity* (via filter), never "is in Favoriten". See the
> `maschinenpark-geraeteliste` page gotchas.

## A. Standort (location) sidebar
- A1 **Standort switch** — click another location → right pane + breadcrumb + URL update **[confirmed]**
- A2 **Standort filter** — narrows sidebar (scoped!); clear restores **[done]**
- A3 **Standort sort** (Sortierung, default Name) reorders locations **[inferred]**
- A4 No-match → empty sidebar **[inferred]**

## B. Geräte filtern (device filter)
- B1 by **name** → matching visible / non-matching absent **[done]**
- B2 by **serial number** (e.g. 40-046325) **[inferred — to add]**
- B3 clear (X) restores **[done]**; B4 per-section no-match message **[done]**
- B5 partial / case-insensitive match **[inferred]**

## C. Gerätegruppierungen (regrouping scheme) — STICKY — **[done: every option]**
All options + the sections each produces (Favoriten is always first):

| Option | Sections produced |
|---|---|
| Keine | Favoriten + flat ungrouped list |
| IOT-Geräte | Favoriten / Neu / Bestehender |
| Status | Favoriten / Online / Offline |
| Hersteller | Favoriten / per-manufacturer (Diverse Kaffee, BEKA, Eloma …) |
| Modell | Favoriten / per-model |
| Fahrzeugnummer | Favoriten / FAHRZEUG-NUMMER {n} |
| Fahrzeugtyp | Favoriten / per-vehicle-type |
| Test Partner Gruppe (PARTNER) | Favoriten / GRUPPE #1/#2 + "Nicht zu einer Gruppe zugewiesen" |

- C-each: every STANDARD option selectable, dropdown value reflects it **[done — verified live]**
- C7 Favoriten present under every grouping (incl. Keine) **[done/confirmed]**
- C-regroup: Bestehender is IOT-Geräte-only → vanishes under another grouping, returns under IOT-Geräte **[done]**
- C-partner: PARTNER-GRUPPIERUNGEN are user-CREATED data, not hardcoded — a specific one ("Test Partner Gruppe") was observed disappearing mid-session. Cover via a separate data-driven test that creates a scheme in setup (Maschinenpark Einstellungen → Gerätegruppierungen) and tears it down **[todo]**
- C8 device set **constant** across groupings (sum of counts stable) **[inferred — not yet asserted]**
- C9 selection **persists** across reload/navigation **[confirmed — the sticky-state finding; handled by setup]**
- C10 grouping **+ filter combine** **[confirmed]**

## D. Sorting within the list
- D1 column headers Status / Gerät / Seriennummer sortable; D2 direction toggle **[inferred]**

## E. Device-row actions
- E1 **Favorite star** toggle → moves in/out of Favoriten **[mutating, needs teardown]**
- E2 click row → preview drawer (URL /geraet/{id}) **[done]**
- E3 status icon reflects connection state **[inferred]**

## F. Device-pane header
- F1 **Add device (+)** → add flow **[mutating]**
- F2 **Settings gear** → Maschinenpark einstellungen (see G)
- F3 **Close (X)** → collapses pane to location-list-only **[confirmed]**

## G. Maschinenpark Einstellungen (gear icon) — **[explored live; 2 tests built]**
Modal "Maschinenpark Einstellungen" with two tabs. Mapped in
`pages/maschinenpark-einstellungen.yaml`. Tests:
`workflows/test-maschinenpark-spalten.yaml` (column toggle) and
`workflows/test-maschinenpark-gruppierung-config.yaml` (create/teardown grouping).

### G.1 Benutzer Einstellungen tab
- **Informations Spalten** (= "Config Spalten") — drag-orderable checkbox list of
  device-list columns: Installationsdatum, Artikelnummer, Hersteller, Typ, Modell,
  Interner Name, Letzte Verbindung, Fahrzeugtyp, Fahrzeugnummer (all off by default).
  - Tests: check a column → it appears in the Geräteliste; uncheck → disappears
    **[done — test-maschinenpark-spalten]**; drag to reorder → list column order
    changes; persists across reload **[todo]**. **[mutating]**
- **Geräte Information Kacheln** (= "Geräte Informationskacheln") — drag-orderable
  checkbox list of tiles shown in the preview drawer: Störungsmeldungen *(nur Geräte
  mit IoT Connectivity)*, Geräte-Benachrichtigungen, Service (all on).
  - Tests: uncheck a tile → it disappears from the device preview drawer; reorder →
    tile order in the drawer changes; the IoT-only tile only renders for connected
    devices. **[mutating]**

### G.2 Gerätegruppierungen tab
- Configure custom grouping schemes ("Sortierungsgruppierung") that then appear under
  PARTNER-GRUPPIERUNGEN in the Gerätegruppierungen dropdown (see C).
- "Sortierungsgruppierung hinzufügen" → new scheme with **Gruppierung Typ** +
  **Gruppensortierung Name**; within it "Gerätegruppierung hinzufügen" → add groups;
  a device can belong to multiple groups. Trash icon deletes a row.
  - Gruppierung Typ options: **Partner-Gruppierung** (-> PARTNER-GRUPPIERUNGEN) or
    **Benutzer-Gruppierung** (-> BENUTZER-GRUPPIERUNGEN). Persists on Schliessen.
  - Tests: create a scheme → it appears in the dropdown
    **[done — test-maschinenpark-gruppierung-config, creates+deletes a Benutzer-Gruppierung]**;
    add a group + assign a device → that GRUPPE shows when the scheme is selected **[todo]**.
    **[mutating — has teardown]**

> NB: the settings modal opens over the device pane and intercepts clicks to the
> grouping dropdown/header while open — close it (Schliessen / X) before interacting
> with the list. An incomplete "Sortierungsgruppierung" row can be removed via its
> trash icon.

## H. Navigation / deep-linking
- H1 breadcrumb; H2 list → drawer → Vollansicht → detail **[partly done]**;
  H3 deep-link to /…/{p}/{l} and …/geraet/{id} **[inferred]**

## I. Persistence / edge
- I1 grouping/sort persist across reload **[confirmed for grouping]**;
  I2 empty location (no devices) state **[inferred]**

---
Mutating tests (E1, F1, G1–G2) change state — fine on dev
(`safe_to_submit_forms: true`) but each needs teardown or throwaway data.
