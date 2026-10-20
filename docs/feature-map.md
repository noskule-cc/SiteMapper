# Feature Map

Routing table for triage. Bug reports speak feature language ("the run wrote to
production even though policy said ask"); this file maps it to the code entry
point where reading starts. It earns documentation here because SiteMapper's
features **smear across a handful of large scripts** — the permission gate lives
in both `run.py` and `serve.py`, drift detection is a side effect inside the step
loop, and the dashboard's staleness badge is computed in the renderer. None of
that is derivable from five filenames.

## Rules

- One row per user-facing feature. Skip features whose location is obvious from
  structure or naming (minimalism Q2, applied per row).
- **No file inventories** — they rot fast and duplicate grep. Trace from the
  entry point.
- Behavior and rationale live on the wiki feature page — link, never restate.
- Entry points must be grep-able identifiers; `docs/tools/check-docs.py` fails
  when one no longer resolves in the source tree.

## Features

| Feature | Entry point | Gotchas & failure modes | Behavior |
|---------|-------------|-------------------------|----------|
| Permission gate — a run is allowed or refused before the browser opens | `gate` | Gated against every site a step runs on, strictest wins; a site listed only under `sites:` to be read is still in scope. Non-interactive contexts degrade `ask` to `deny`, so a CI failure reads as a policy refusal, not a bug. `permission_verdict` resolves one class against the layered settings. | [Permissions](https://github.com/noskule-cc/SiteMapper/wiki/features-permissions) |
| Tier resolution — which site a tiered workflow runs on | `resolve_scope` | The `environment` parameter picks the tier, the app maps it to a site; a value outside `tiers.allowed` is refused before the gate. "Wrong site" reports on a project workflow start here, not in the fixtures. | [Workflows](https://github.com/noskule-cc/SiteMapper/wiki/concepts-workflow) |
| Server-side gate for the dashboard's run buttons | `Handler` | The browser is untrusted UI: consent arrives per run and can never widen policy. A "the button did nothing" report is usually `deny` refused server-side. | [Dashboard](https://github.com/noskule-cc/SiteMapper/wiki/features-dashboard) |
| Drift detection (watch) — fingerprint verified on every page arrival | `Runner.check_fingerprint` | Fires in passing, not as a step, so a drift report can name a page the workflow never asserted on. Mismatch degrades `trust`, it does not stop the run. | [Watch & repair](https://github.com/noskule-cc/SiteMapper/wiki/features-watch-and-repair) |
| Trust bookkeeping — `broken` on failure, never auto-promotion | `update_trust` | Writes back into the workflow YAML, so a run mutates a tracked file; a "why is my workflow file dirty" report lands here. Green runs never promote `draft` to `verified`. | [Watch & repair](https://github.com/noskule-cc/SiteMapper/wiki/features-watch-and-repair) |
| Structured failure report the repair loop consumes | `Runner.build_failure` | Carries the locator **as tried** plus resolved variables; if either is missing the repair skill will re-explore instead of patching. | [Results](https://github.com/noskule-cc/SiteMapper/wiki/concepts-result) |
| Personas — authenticated runs without owned credentials | `load_persona` | `session` auth fails loud when the saved state expired rather than re-logging in silently; `automated` is refused unless the environment's `auth` permission allows it. | [Personas & contexts](https://github.com/noskule-cc/SiteMapper/wiki/concepts-persona-context) |
| Tenant contexts — one workflow, many tenants | `load_context` | A workflow's `requires:` contract is validated before the run starts; a missing role fails early with the name, which is why "it just exits" reports belong here. | [Personas & contexts](https://github.com/noskule-cc/SiteMapper/wiki/concepts-persona-context) |
| Variable resolution — `$name` across params, context, fixtures, captures | `Bindings.resolve` | Resolution order is params → context roles/ids → fixtures → captures; a value that "silently stays literal" means no binding matched, not a substitution bug. | [Workflows](https://github.com/noskule-cc/SiteMapper/wiki/concepts-workflow) |
| Scripts — API calls instead of DOM driving | `script_path` | Resolved site → project → app; a "not declared" error names all three homes it looked in. Stdout is parsed as JSON only when the script was run with `--json`; a capture holding a raw string is usually a missing flag in the step's `value`. | [Headless runs](https://github.com/noskule-cc/SiteMapper/wiki/features-headless-runs) |
| Run records — the folder a recorded run leaves in the runs store | `RunRecord` | `running` with the runner's `pid` from the first step, rewritten final at the end, one index line each under one `run_id`; a killed run stays `running`. Written outside the tree (`runs_root`), never linked from the generated views; a `rollback: snapshot` workflow is recorded even without `--record`, and its `snapshot/` holds the pre-state. | [Results](https://github.com/noskule-cc/SiteMapper/wiki/concepts-result) |
| Runs retention — expired run folders are swept | `sweep_runs` | Runs after every recorded run and on `run.py --sweep`; sweeps every lib's records, never a folder without a readable `run.yaml`. A "my run vanished" report means its `keep` ran out: `keep: keep` in `run.yaml` is the only way to keep it forever. | [Results](https://github.com/noskule-cc/SiteMapper/wiki/concepts-result) |
| Where the roots are — projects beside the lib tree, runs beside both | `projects_root` | Resolved by presence (`<root>/projects`, else `<root>/../projects`); a workflow "not found" on a shared data tree usually means the projects folder sits elsewhere, pass `--projects`. | [Framework vs deployment](https://github.com/noskule-cc/SiteMapper/wiki/concepts-framework-vs-deployment) |
| Generated inventory and dashboard | `collect_workflows` | The collectors are shared by both views; a wrong count in `overview.html` is almost always a collector bug, not a renderer one. | [Dashboard](https://github.com/noskule-cc/SiteMapper/wiki/features-dashboard) |
| Staleness badge — "your changes aren't shared yet" | `content_hash` | Compares the built page against `published_hash` in config; an always-stale chip means the publish step never wrote the hash back. `deploy_build` produces the build and its `build-info.json`. | [Dashboard](https://github.com/noskule-cc/SiteMapper/wiki/features-dashboard) |
| Staleness of the generated views themselves | `stale` | Compares rendered output against the committed file; CI fails here when someone edits `inventory.md` by hand. | [Health checks](https://github.com/noskule-cc/SiteMapper/wiki/features-health-checks) |
| Doc/registration consistency | `check_bindings` | Framework-only: it skips against `--root`, and a skipped check must never read as a pass. | [Health checks](https://github.com/noskule-cc/SiteMapper/wiki/features-health-checks) |

**Last Updated:** 2026-08-26
