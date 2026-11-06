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
| 8 | "A captured value is a raw string where the workflow expects an object." | `Runner.do_script` | feature-map.md (Scripts) |
| 9 | "On my map repository's dashboard the artifact chip says `artifact: published` and never `current`, even right after a deploy." | `Handler.map_dashboard` | feature-map.md (Staleness chip and share link) |
| 10 | "CI fails with 'inventory.md is stale' but the file looks correct." | `generated_is_stale` | feature-map.md (Staleness of generated views) |
| 11 | "`check.py --root ../my-maps` reports success but clearly checked nothing about bindings." | `check_bindings` | feature-map.md (Doc/registration consistency) |
| 12 | "A saved session expired and the runner should have logged in again but didn't." | `Runner.start` | feature-map.md (Personas) |
| 13 | "A project workflow ran on the dev site although I passed `--param environment=prod`." | `resolve_scope` | feature-map.md (Tier resolution) |
| 14 | "A run failed, the page map is fine, and the workflow was still set to `broken`." | `CLASSES` | feature-map.md (Failure classes) |
| 15 | "A run folder in the runs store still says `status: running` hours after the run ended." | `RunRecord` | feature-map.md (Run records) |
| 16 | "Yesterday's run folder is gone from the runs store, and nobody deleted it." | `sweep_runs` | feature-map.md (Runs retention) |
| 17 | "On the shared data tree, `run.py` says a project workflow is not found, but it is there under `projects/`." | `projects_root` | feature-map.md (Where the roots are) |

**Last Updated:** 2026-11-06
