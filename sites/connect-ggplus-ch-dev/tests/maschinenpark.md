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

## C. Gerätegruppierungen (regrouping scheme) — STICKY
Options: **Keine**; STANDARD: **IOT-Geräte, Status, Hersteller, Modell,
Fahrzeugnummer, Fahrzeugtyp**; PARTNER: custom sets (e.g. *Test Partner Gruppe*).
- C1 IOT-Geräte → Favoriten / Neu / Bestehender **[confirmed]**
- C2 Status / Hersteller / Modell / Fahrzeugnummer / Fahrzeugtyp → matching group headers **[inferred]**
- C6 Partner-Gruppierung → GRUPPE #1/#2 + "Nicht zu einer Gruppe zugewiesen" **[confirmed]**
- C7 Favoriten always present as a group **[confirmed]**
- C8 device set is **constant** across groupings (sum of counts stable) **[inferred]**
- C9 selection **persists** across reload/navigation **[confirmed — this is the sticky-state finding]**
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

## G. Maschinenpark einstellungen (needs careful exploration)
- G1 **Benutzer** — manage users/access **[mutating]**
- G2 **Gerätegruppen** — create/edit/delete the custom groups powering C6's Partner-Gruppierungen
- G3 **Config Spalten** — toggle which list columns show
- G4 **Geräte Informationskacheln** — order & selection of device info tiles

## H. Navigation / deep-linking
- H1 breadcrumb; H2 list → drawer → Vollansicht → detail **[partly done]**;
  H3 deep-link to /…/{p}/{l} and …/geraet/{id} **[inferred]**

## I. Persistence / edge
- I1 grouping/sort persist across reload **[confirmed for grouping]**;
  I2 empty location (no devices) state **[inferred]**

---
Mutating tests (E1, F1, G1–G2) change state — fine on dev
(`safe_to_submit_forms: true`) but each needs teardown or throwaway data.
