# Proposal: Separate session/identity and tenant-context from workflow "work"

Status: **draft / for discussion** · Author: pairing session 2026-07-03 · Scope: `sites/connect-ggplus-ch-dev` (generalizable)

## Problem

Today a workflow's `fixtures` block silently mixes three different concerns, and
login + partner switching is not encoded at all. Example from
`test-maschinenpark-geraeteliste.yaml`:

```yaml
fixtures:
  partner_id: "10000"                   # WHO/WHERE  — identity + tenant
  location_id: "10000"                  # WHO/WHERE
  location_name: "Gehrig Group AG test" # DATA       — partner-specific
  device_filter_term: "Mastrena"        # DATA
  matching_device: "Diverse Kaffee Mastrena"      # DATA
  non_matching_device: "Diverse Wasseraufbereitung" # DATA
```

Plus a fourth, invisible concern: **who is logged in** and **which partner is
active** (Partnerwechsel). That is done by hand and lives only in tribal
knowledge.

### Evidence this hurts (2026-07-03 Werkstatt run)

Running the three workflows against a different partner ("Werkstatt Demo
Account", `3086769`) instead of Gehrig surfaced two real failures caused by this
coupling:

1. **Data coupling** — every data-driven step (`device_filter_term "Mastrena"`,
   `matching_device`, `location "Renens"`, `location_name`) referenced entities
   that do not exist for Werkstatt. The steps had to be hand-adapted at run time.
2. **No session layer** — the partner switch was a manual, undocumented
   precondition. During teardown a coordinate-based click (a workaround for the
   missing structure) deleted a *pre-existing* Partner-Gruppierung that the test
   did not create. It was recovered, but only by luck and manual attention.

Separating **only** login would not have prevented failure #1. The fix is a
three-layer split.

## The three layers

| Layer | Answers | Owns | Example file |
|-------|---------|------|--------------|
| **Persona / session** | *who is logged in* | login user, auth method, optional starting partner | `personas/benjamin.yaml` |
| **Context / tenant** | *where + what data* | `partner_id`, location(s), data that fills the roles the work needs | `contexts/werkstatt.yaml` |
| **Work / workflow** | *what behavior* | the steps and assertions, referencing roles only — zero hardcoded IDs or device names | `workflows/test-maschinenpark-geraeteliste.yaml` |

Running a workflow becomes: **pick a persona + a context, bind them into the
work.**

## Proposed file layout

```
sites/connect-ggplus-ch-dev/
  personas/
    benjamin.yaml          # live SSO session; NO passwords in the file
  contexts/
    gehrig.yaml            # partner 10000 + its data roles
    werkstatt.yaml         # partner 3086769 + its data roles
  workflows/
    test-maschinenpark-geraeteliste.yaml   # role-based, partner-agnostic
    test-maschinenpark-spalten.yaml        # needs only partner+location
    test-maschinenpark-gruppierung-config.yaml
  macros/
    switch-partner.yaml    # reusable Partnerwechsel setup, authored once
```

### Persona (identity)

```yaml
# personas/benjamin.yaml
persona:
  name: benjamin
  description: Admin user Benjamin Behringer
  auth: session          # use the already-authenticated browser session (dev)
  # For non-session auth, reference a secret at run time — never store a
  # password here. Entering credentials is a human action, not an agent action.
  # credential_ref: env:GGPLUS_DEV_PASSWORD   # example only
```

### Context (tenant + data roles)

```yaml
# contexts/werkstatt.yaml
context:
  name: werkstatt
  partner_id: "3086769"
  location_id: "3086769"
  location_name: "Werkstatt Demo Account"
  single_location: true          # → work may skip the location-sidebar filter
  roles:
    device_filter_term: "Brita"
    matching_device: "Brita PURITY C iQ Filterkopf G3/8"
    non_matching_device: "Hobart Gläser- und Geschirrspülmaschine GXC-14C"
```

```yaml
# contexts/gehrig.yaml
context:
  name: gehrig
  partner_id: "10000"
  location_id: "10000"
  location_name: "Gehrig Group AG test"
  single_location: false
  roles:
    device_filter_term: "Mastrena"
    matching_device: "Diverse Kaffee Mastrena"
    non_matching_device: "Diverse Wasseraufbereitung"
    location_filter_term: "Renens"
    location_match: "1020 Renens"
    location_nonmatch: "8152 Glattbrugg"
```

### Work (role-based, no hardcoded data)

The workflow declares what it **needs** and references roles; it no longer pins
partner-specific values.

```yaml
workflow:
  name: test-maschinenpark-geraeteliste
  requires:                       # a fail-fast contract, checked before run
    context:
      roles: [device_filter_term, matching_device, non_matching_device]
      # location_filter_term/match/nonmatch only required when !single_location
  # no `fixtures:` block — bindings come from the selected context
  steps:
    - action: input
      element: device-filter
      value: "$device_filter_term"     # resolved from context.roles
```

Partner-agnostic workflows (spalten, gruppierung-config) declare a minimal need
and carry no roles:

```yaml
  requires:
    context:
      needs: [partner_id, location_id]   # any partner with ≥1 location
```

## How it maps to the existing schema

- `schema/workflow.yaml` already separates `parameters` (prompted) from
  `fixtures` (pinned). This proposal **replaces per-workflow `fixtures` with a
  selected `context`** and adds a `requires` contract. `parameters` is unchanged.
- The **Partnerwechsel macro** is just a named `setup` fragment (same step
  shape) that the runner injects before `steps` when
  `active_partner != context.partner_id`, and a matching teardown ("Partner
  verlassen"). It is authored once in `macros/switch-partner.yaml` instead of
  copy-pasted.
- Two new tiny schemas: `schema/persona.yaml`, `schema/context.yaml`.

## Runner changes (`docs/skills/run-workflow.md`)

1. Resolve `--persona` (default the site's only persona) and `--context`.
2. Ensure the persona session (login only if needed; never type a password
   unattended).
3. Check the workflow's `requires` against the chosen context → **fail fast**
   with a clear message on a bad pairing, instead of breaking mid-run.
4. If `active_partner != context.partner_id`, run the `switch-partner` macro.
5. Execute `steps`, resolving `$role` from `context.roles` (and `$param` /
   `$captured_var` as today).
6. Teardown restores state and leaves the original partner.

Invocation: `/run test-geraeteliste --context werkstatt`
(`--persona benjamin` implied when the site has one persona).

## Why this is the right fix

- **Adding a partner = writing one context file.** No workflow edits, no
  per-partner forks. This is exactly what was missing on 2026-07-03.
- **The delete-wrong-row incident becomes structurally hard.** The partner
  switch is an explicit macro with its own teardown; the work never touches
  identity, so there is no ad-hoc coordinate juggling in teardown.
- **Credentials stay out of the repo.** Personas reference the live session or a
  run-time secret. This is a security boundary, not just tidiness — entering a
  password is a human action.
- **Honest contracts.** `requires` vs. what a context `provides` fails a bad
  pairing up front instead of producing a misleading half-pass.

## Migration path (incremental, low risk)

1. **Add context files** for gehrig + werkstatt (pure data extraction; nothing
   references them yet — zero risk).
2. **Add the switch-partner macro** documenting the Partnerwechsel we do by hand.
3. **Convert one workflow** (`geraeteliste`) to role-based + `requires`; keep the
   others on the current `fixtures` model until proven.
4. **Update the run skill** to resolve persona/context and inject the macro.
5. Convert the remaining workflows; delete per-workflow partner/data fixtures.

Steps 1–2 are additive and safe to do anytime. Step 3+ change the run path and
should land together with step 4.

## Open questions

- **Persona vs. context ownership of the starting partner.** A persona could
  have a default partner; a context always names one. Rule of thumb: context
  wins (it's the tenant under test); persona's is only a starting point.
- **Where do roles live for partner-agnostic workflows?** Nowhere — they declare
  `needs`, not `roles`.
- **Secret handling for real (non-session) logins** — env var? OS keychain?
  Out of scope for dev (session auth), but the persona schema should leave room.
- **Multi-location contexts** — `location_id` is single today; may later become a
  list with a `primary`.

## Not doing (explicitly)

- Storing passwords or tokens in any committed file.
- A full test-runner/CI framework — this is about structure, not orchestration.
- Changing the page maps (this is a workflow/context concern).
