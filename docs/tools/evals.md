# Triage Evals

Eval cases for the documentation system: bug-report-phrased questions with
ground truth. The `validation-llm` agent runs them against a fresh agent to
measure whether the docs — especially [feature-map.md](../feature-map.md) —
route triage to the right entry point. See Triage Eval Mode in
`.claude/agents/validation-llm.md`.

## Case Format

One row per case. Expected entry points use the same grep-able identifiers as
`feature-map.md`.

| # | Question (bug-report phrasing) | Expected entry point | Expected source |
|---|--------------------------------|----------------------|-----------------|
| 1 | "A staging run wrote data even though the site's policy says `write: ask` — where do you start reading?" | `gate` | feature-map.md (Permission gate) |
| 2 | "The dashboard's run button does nothing for one workflow and works for another." | `Handler` | feature-map.md (Server-side gate) |
| 3 | "A green run still reported the workflow as `broken`, naming a page the workflow never touched." | `Runner.check_fingerprint` | feature-map.md (Drift detection) |
| 4 | "Running a workflow leaves its YAML file modified in `git status`." | `update_trust` | feature-map.md (Trust bookkeeping) |
| 5 | "`/repair` re-explores the page instead of patching the locator from the report." | `Runner.build_failure` | feature-map.md (Structured failure report) |
| 6 | "The runner exits immediately for one tenant and runs fine for another, with no step output." | `load_context` | feature-map.md (Tenant contexts) |
| 7 | "A step value shows up on the page as the literal `$order_id` instead of a number." | `Bindings.resolve` | feature-map.md (Variable resolution) |
| 8 | "A captured value is a raw string where the workflow expects an object." | `do_script` | feature-map.md (Site scripts) |
| 9 | "The share-link chip is always gray even right after a deploy." | `content_hash` | feature-map.md (Staleness badge) |
| 10 | "CI fails with 'inventory.md is stale' but the file looks correct." | `stale` | feature-map.md (Staleness of generated views) |
| 11 | "`check.py --root ../my-maps` reports success but clearly checked nothing about bindings." | `check_bindings` | feature-map.md (Doc/registration consistency) |
| 12 | "A saved session expired and the runner should have logged in again but didn't." | `load_persona` | feature-map.md (Personas) |

**Last Updated:** 2026-08-26
