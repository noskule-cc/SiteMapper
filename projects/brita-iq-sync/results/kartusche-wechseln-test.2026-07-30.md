# kartusche-wechseln-test — run 2026-07-30 (fix verification)

**Result: 4 of 6 findings fixed, 1 regressed into a blocker, 1 unchanged.**
Run **incomplete** — the device is trapped on Clean Extra and could not be restored.

| | |
|---|---|
| Purpose | Verify fixes against the 2026-07-29 run |
| Build | **v2.27.3** (was v2.27.2). Bundle `main.7c2ba30dd863757f.js` (was `main.0b2d8878f4ec09d0.js`) |
| Device | Werkstatt iQ Meter — connect `1eb28001-…`, BRITA `Id 353141283322738` |
| Baseline in | Clean / 1200 / 15.0 °dH / 0 % |
| **Baseline out** | ❌ **NOT restored** — `PURITY_CLEAN_EXTRA / 1200 / Gesamthärte 15.0 °dH / 0 %`, Installationsdatum `30.07.2026 07:57:01` |
| Cartridge installs written | 1 |

> **Read the version from `/logs` *after* applying any pending app update.** The first
> reading this run was the stale service-worker build (2.27.2) and briefly led to the
> wrong conclusion that nothing had shipped.

---

## Finding status

| ID | Finding | Status |
|---|---|---|
| F-1 | Karbonathärte `0` silently rejected | ✅ **Fixed** |
| F-2 | Wizard refuses to reopen | ❌ **Regressed — now a blocker** |
| F-3 | Step-4 Aktuell/Neu labels inverted | ✅ **Fixed** (partially verified) |
| F-4 | Undocumented Verschnitteinstellung constraints | ✅ **Fixed** (now documented in UI) |
| F-5 | BRITA list vs detail disagree | ⚠️ **Not reproduced** — but not a like-for-like retest |
| F-6 | No audit trail on `/logs` | ❌ **Unchanged** |
| — | Cosmetic `Gesammthärte` | ✅ **Fixed** → `Gesamthärte` |

### F-1 — fixed ✅

Entering `0` now shows **"Der eingegebene Wert ist zu klein."** inline and in red,
immediately. The hint was corrected from `0...40 Wasserhärte` to **`1...40 °dH Wasserhärte`**,
so hint and validation finally agree. `41` still gives *"zu gross"*; `1` and `40` save.

### F-3 — fixed ✅

Clean → Clean Extra now renders *Aktuell* = **Karbonathärte**, *Neu* = **Gesamthärte**.
Previously inverted.

Two of the three F-3 sub-cases (the phantom `Dampfsystem` under *Aktuell*, and the
wrong `Karbonathärte 0 °dH`) **could not be retested** — both need cartridge switches
that F-2 now blocks.

### F-4 — fixed ✅

Step 3 now renders a helper line under the slider:
**`Erlaubte Werte: 0-10 % in 10%-Schritten`**. The multiples-of-10 step and the
per-type cap are stated in the UI instead of having to be discovered by probing.

### F-2 — regressed into a blocker ❌

The old symptom is gone: the `Formly component type "slider" … removeEventListener`
exception no longer appears. But the failure it caused got **worse**:

| | v2.27.2 (29.07) | v2.27.3 (30.07) |
|---|---|---|
| Console error | Formly slider TypeError | **none at all** |
| Trigger | after the Clean Extra commit | after the Clean Extra commit |
| Reload recovers? | yes | **no** |
| Fresh tab recovers? | not tried | **no** |
| Attempts before giving up | ~6 | 7+ clicks, 3 reloads, 1 fresh tab |

**Once `PURITY_CLEAN_EXTRA` is installed, "Kartusche austauschen" does nothing and
there is no UI route back to another cartridge type.** The fixture device is trapped
and this run could not restore its baseline.

This needs an out-of-band fix (backend/API cartridge reset) before the next scheduled
run, otherwise the suite starts from a broken fixture.

### F-5 — not reproduced, but not settled ⚠️

All three surfaces agree today: BRITA list **26 weeks / 3333 litres**, BRITA detail
**26 / 3333**, connect **26 Wochen / 3333 Liter**. The step-4 prediction also matched
the committed value exactly.

Not a clean retest, though: yesterday's mismatch was **Clean at 51 vs 52**, and the
device can't be put back on Clean. Leave F-5 open until it can be retested on Clean.

### F-6 — unchanged ❌

`/logs` is still a client-side console dump (AuthService, notification hub, JWT
interceptor, app startup, env config), reset on every page load. No record of the
cartridge change made during this run.

---

## Propagation re-verified on v2.27.3 ✅

The Clean Extra commit reached BRITA intact:

| Field | connect | BRITA |
|---|---|---|
| Cartridge type | PURITY_CLEAN_EXTRA | Clean Extra |
| Cartridge size | 1200 | 1200 |
| Hardness | Gesamthärte 15.0 °dH | **Total hardness** 15 °dH |
| Bypass | Verschnitteinstellung 0 % | Bypass percentage 0 % |
| Lifetime / capacity | 26 Wochen / 3333 L | 26 weeks / 3333 litres |
| Install date | 30.07.2026 07:57:01 | 30/07/2026 |

The `brita_water_rows` expectation for Clean Extra (`Total hardness` + `Bypass percentage`)
holds on the new build.

---

## Not covered this run

Suite B ran **1 of 4** cartridge types (Clean Extra only) before the blocker. Not executed:
Quell St, Steam, Clean; the size/step-3 matrix regression for those three; required-field
gating; Suite B2 cancel paths; Suite A2 (Verschnitteinstellung round-trip); A3 boundary
saves; A4 cancel.

## Environment notes

- The BRITA session expired mid-run; the user re-authenticated. Budget for this on long runs.
- Chrome reported viewport `2844×1388` against `1568×765` screenshots — coordinate clicks
  drifted by a scroll-dependent offset. **Use `find` + `ref` clicks on this site**, not coordinates.
- The device showed a `warning` status icon (was a green check on 29.07), and its cartridge
  had already been changed overnight (`30.07.2026 05:57:34`) before this run started —
  neither was caused by this test.

## Next run

1. **Blocked** until the device is off Clean Extra. Fix F-2 or reset the cartridge out-of-band first.
2. Retest F-5 on a **Clean** cartridge specifically — the 51/52 case.
3. Retest the two unverified F-3 sub-cases once type switching works again.
4. Consider dropping Clean Extra from the matrix, or ordering it so a working type is installed last.
