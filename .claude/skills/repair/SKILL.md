---
name: repair
description: Fix a site map after a headless runner failure — consume the failure report, patch the locator, re-verify, restore trust.
disable-model-invocation: true
argument-hint: [workflow-name]
arguments: [workflow]
---

# Repair

Consume a headless runner failure report, fix the **map**, restore trust.
This is the LLM half of the runner's failure story (`docs/code-over-llm.md`:
the runner fails fast and reports; judgement about what changed is repair's
job). Registered jobs: `docs/tools/jobs.md`.

Workflow argument: $workflow

## Input

The runner's JSON result (`python scripts/run.py <workflow> --json`), whose
`failure:` block carries: phase + step index, action, page, element, the
locator **as tried**, resolved variables, actual URL and title, the page's
fingerprint state, and a failure screenshot path. Ask for the JSON (or re-run
the workflow to produce it) if only a prose description is offered.

## Branch on the class first

Read `class` and `next` from the result (`docs/interface.md` → Failure
classes). Only `drift` is a map problem.

- **`drift`** → run the Sequence below.
- **`assert`** → follow `next` once: compare the failed assertion with the
  live page. A page that changed is drift, so run the Sequence. A site that
  broke is a finding for the user, and the map stays as it is.
- **`input`, `refused`, `auth`, `error`** → do not touch the map. Follow
  `next` once if it is a step you can take without bending a permission rule
  (re-run with the missing parameter, for example), then report the class,
  `next` and what happened. Consent, credentials and policy are the user's.

## Sequence

1. **Look before touching.** Open the failure screenshot; open the live page
   at `failure.url` (browser capabilities per `docs/host-bindings.md`).
2. **Find the element again**, alternative strategies in order: exact text →
   fuzzy text (wording may have changed) → aria-label → role → data-testid →
   css. Read the DOM around where the element used to be.
3. **Found it** → patch that element's `locator` in the page YAML. A repair is
   a map **patch** — never edit workflow steps to route around a broken map,
   and never weaken an assert to make a run green.
4. **Check the neighbourhood.** Drift rarely hits one element. Verify the
   page's other mapped elements while there (same vocabulary as
   `/verify-map`); update the page `fingerprint` if its anchor moved.
5. **Re-run**: `python scripts/run.py <workflow> --json`. Green → restore the
   workflow's `trust:` (`broken → draft`, or `verified` **only** if it was
   verified before the drift and the run is reviewed — see
   `schema/workflow.yaml`). The run that set `broken` was recorded with
   `keep: keep`; delete its folder or lower its `keep` once trust is back.
6. **Cannot find it** → ask the user for a focused re-map of that page
   (`/map-site`). Never guess a locator into the map: a plausible-but-wrong
   locator is worse than a missing one, because it fails only sometimes.

## Rules

- Permission-aware: repairing against production inspects **read-only**; a
  mutating re-verification obeys `docs/permissions.md` like any run.
- Record what changed: one commit per repair, naming the drifted element(s)
  and what the site changed, so the map's history explains the site's.
- If the same element breaks repeatedly, say so — that is a locator-strategy
  problem (prefer `data-testid`/`aria-label` over `text`), not bad luck.

## Required capabilities

Read/edit map YAML; run `scripts/run.py`; a browser to inspect the live page
(read-only). No agent needed — repair is interactive by nature.
