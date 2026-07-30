# kartusche-wechseln-test — run 2026-07-29

**Result: PASS with 6 findings.** Propagation GG+connect → BRITA works for every
field of every cartridge type. All findings are UI/validation defects on the
GG+connect side; none is a sync failure.

| | |
|---|---|
| Workflow | `projects/brita-iq-sync/workflows/kartusche-wechseln-test.yaml` |
| Sites | `connect-ggplus-ch-stg` (app **v2.27.2**, `bff-stg.ggplus.ch` / `stg-api.ggplus.ch`) → `iq-brita-net` |
| Device | Werkstatt iQ Meter — connect `1eb28001-…`, BRITA `Id 353141283322738` / `G5UYU6ZPRE` |
| Operator | Benjamin Behringer |
| Baseline in / out | Clean / 1200 / 15.0 °dH / 0 % — **restored on both sides** ✅ |
| Cartridge installs written | 5 (irreversible; Installationsdatum 11:06:27 → 12:52:34) |

---

## Suite results

| Suite  | Test                                                         | Result                          |
|--------|--------------------------------------------------------------|---------------------------------|
| A1     | Karbonathärte 15→20, save, **reload**, BRITA                 | ✅ PASS                          |
| A2     | Verschnitteinstellung 0→10, save, reload, BRITA              | ✅ PASS                          |
| A3     | Validation `41` / `-1` / empty / `40` / `1`                  | ✅ PASS                          |
| A3     | Validation `0`                                               | ❌ **F-1**                       |
| A4     | Cancel discards (typed 33, X)                                | ✅ PASS                          |
| B1     | Quell St · Steam · Clean · Clean Extra — full wizard + BRITA | ✅ PASS (4/4)                    |
| B1     | Size + step-3 shape matrix regression                        | ✅ matches baseline              |
| B1     | Required-field gating (Quell St, Steam)                      | ✅ PASS                          |
| B2     | Cancel on steps 1–4 + X                                      | ✅ PASS (5/5)                    |
| B3     | Restore to baseline                                          | ✅ PASS                          |
| C1     | Join key on both sides                                       | ✅ PASS                          |
| C2     | Propagation latency                                          | ✅ < 60 s, plain reload suffices |
| C3     | BRITA list vs detail                                         | ❌ **F-5**                       |
| C4     | Audit trail on `/logs`                                       | ❌ **F-6** (not found)           |
| C5     | Map drift                                                    | 5 map updates applied           |

---

## Propagation — every field round-tripped

The three previously open questions are answered: **no GG+connect field is
BRITA-only**. BRITA's Water tab reshapes per cartridge type exactly as connect's
Brita Filter card does.

| GG+connect                  | BRITA                | Types                          |
|-----------------------------|----------------------|--------------------------------|
| Karbonathärte               | Carbonate hardness   | Quell St · Steam · Clean       |
| **Gesammthärte**            | **Total hardness**   | Clean Extra                    |
| Verschnitteinstellung (%)   | Bypass percentage    | Quell St · Clean · Clean Extra |
| Verschnitteinstellung (0–3) | **Bypass setting**   | Steam                          |
| Hauswasserenthärtungsanlage | **Central softener** | Quell St                       |
| Dampfsystem                 | **Steam system**     | Steam                          |

### Per-type run detail

| Type        | Size   | Hardness   | Bypass   | Extra                      | connect → BRITA          |
|-------------|--------|------------|----------|----------------------------|--------------------------|
| Quell St    | 600    | 18 °dH     | 20 %     | Kein Enthärter installiert | 3133 L / 24 wk — matched |
| Steam       | 450    | 12 °dH     | 2        | Boiler                     | 3067 L / 23 wk — matched |
| Clean       | 1200   | 25 °dH     | 10 %     | —                          | 5227 L / 41 wk — matched |
| Clean Extra | 1200   | 30 °dH     | 0 %      | —                          | 1667 L / 12 wk — matched |

Capacity and lifetime agreed between the two systems on every single run.

---

## Findings

### F-1 · Karbonathärte `0` is silently rejected — **highest value**

The inline editor's own hint reads `0...40 Wasserhärte`, but saving `0` does
**nothing at all**: no error text, no snackbar, the editor simply stays open.

|           | Behaviour                                                        |
|-----------|------------------------------------------------------------------|
| `41`      | ❌ "Der eingegebene Wert ist zu gross." — save button removed    |
| `-1`      | ❌ "Der eingegebene Wert ist zu klein."                          |
| `0`       | ⚠️ **silent no-op — no message of any kind**                     |
| `1`, `40` | ✅ saved                                                        |

Either the hint should read `1...40`, or `0` should be accepted. The silent
failure is the real problem — a user has no way to tell why nothing happened.

### F-2 · Wizard intermittently refuses to reopen (JS error)

After several wizard runs, "Kartusche austauschen" stops responding. Console:

```
An error occurred while destroying the Formly component type "slider"
TypeError: Cannot read properties of undefined (reading 'removeEventListener')
    at Ft.ngOnDestroy … zt.resolveFieldTypeRef
```

The slider field type throws on teardown and leaves the Formly registry broken.
**Workaround: reload the device page.** This blocked the B3 restore until diagnosed.

### F-3 · Step-4 "Aktuell" column is wrong when the type changes

Three separate manifestations:

1. Quell St → Steam: *Aktuell* showed `Dampfsystem: Direkteinsprizer`, but the installed Quell St cartridge has no Dampfsystem.
2. Clean → Clean Extra: hardness labels **inverted** — *Aktuell* (Clean) labelled `Gesammthärte`, *Neu* (Clean Extra) labelled `Karbonathärte`.
3. Clean Extra → Clean: *Aktuell* read `Karbonathärte 0 °dH` when the device actually held `Gesammthärte 30`.

The *Neu* column was correct every time. Users comparing before/after in this
dialog are being shown a wrong "before".

### F-4 · Verschnitteinstellung constraints are undocumented in the UI

- Only **multiples of 10** are accepted; typing `5` snaps silently back to `0`.
- For **Clean Extra** the value is **capped at 10 %** — typing, arrow keys and dragging all refuse to go higher, yet the slider still renders a `100` tick label and drags freely downward.

### F-5 · BRITA list disagrees with BRITA detail (reproduced)

Same device, same moment: `/purityciqs` list says **52 weeks**, the detail page and
GG+connect both say **51**. Capacity agrees (8000 L).

Refined this run: the split is consistent — **(wizard summary + BRITA list) = 52**
vs **(connect tile + BRITA detail) = 51**. So it is one off-by-one appearing in two
places, not random noise. The wizard's "predicted 52 → actual 51" discrepancy noted
on 2026-07-16 is the *same* bug, seen from the connect side. Reproduced 3×.

### F-6 · No audit trail — *not found*

`/logs` is a **client-side console dump** (AuthService, notification hub, JWT
interceptor, app startup, env config), and it resets on every page load. It contains
no record of the cartridge replacements or hardness edits. There is no user-facing
audit trail for these changes.

### Cosmetic (not tracked as findings)

- `Kein enthörter installiert` on the device tile vs `Kein Enthärter installiert` on the wizard card — inconsistent, and the tile spelling is wrong.
- `Direkteinsprizer` should be `Direkteinspritzer`.
- `Gesammthärte` should be `Gesamthärte`.

---

## Map updates applied (C5)

- `sites/iq-brita-net/pages/flowmeter-detail.yaml` — Water tab is type-dependent; added `total-hardness`, `bypass-setting`, `central-softener`, `steam-system`, System-tab rows; tab-click flakiness.
- `sites/connect-ggplus-ch-stg/pages/geraet-detail.yaml` — added `gesammthaerte-tile`, `hauswasserenthaertungsanlage-tile`, `dampfsystem-tile`; card-shape matrix; F-1; slider-only inline editor; snackbar auto-dismiss.
- `sites/connect-ggplus-ch-stg/pages/brita-kartusche-wechseln.yaml` — F-2, F-3, F-4; modal fade-in swallows clicks; type switch resets hardness prefill.
- `projects/brita-iq-sync/workflows/kartusche-wechseln-test.yaml` — fixtures corrected (multiples of 10; Clean Extra cap), `brita_water_rows` added as a label-level assertion.

## Notes for the next run

- Expect ~5 cartridge installs. Device left at Clean / 1200 / 15 °dH / 0 %.
- Budget for F-2: reload the device page between wizard iterations rather than retry-clicking.
- Promote `brita_water_rows` from "record" to hard assertions — the shape is now established.
- If F-1 or F-5 are fixed, update the fixtures and drop the corresponding expected-failure notes.
