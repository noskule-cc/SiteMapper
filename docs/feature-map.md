# Feature Map

Routing table for triage. Bug reports speak feature language ("the run wrote to
production even though policy said ask"); this file maps it to the code entry
point where reading starts. It earns documentation here because SiteMapper's
features **smear across a handful of large scripts** — the permission gate lives
in both `run.py` and `serve.py`, drift detection is a side effect inside the step
loop, and the dashboard's staleness chip is decided by the server. None of
that is derivable from eight filenames.

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
| Trust bookkeeping — `broken` on drift or a failed assert, never auto-promotion | `update_trust` | Writes back into the workflow YAML, so a run mutates a tracked file; a "why is my workflow file dirty" report lands here. Green runs never promote `draft` to `verified`. A run whose class is `auth`, `input`, `refused` or `error` leaves trust alone. | [Watch & repair](https://github.com/noskule-cc/SiteMapper/wiki/features-watch-and-repair) |
| Failure classes — every result's `class` and one `next` step | `CLASSES` | The classes and what each means: [interface.md](interface.md#failure-classes). A raise site names its class on `RunError`; an untagged one is `error`. "Marked broken but the map is fine" means a raise site lacks its class. Any Playwright error on a step with an element, a table read that finds no header or row, and a field that reverts its value are `drift`; so is a failure in the login page's map. A closed or crashed browser and a `net::ERR_` are `error` (`NOT_THE_MAP`). | [Results](https://github.com/noskule-cc/SiteMapper/wiki/concepts-result) |
| Structured failure report the repair loop consumes | `Runner.build_failure` | Carries the locator **as tried** plus resolved variables; if either is missing the repair skill will re-explore instead of patching. | [Results](https://github.com/noskule-cc/SiteMapper/wiki/concepts-result) |
| Personas — authenticated runs without owned credentials | `Runner.start` | Decides reuse of the saved state or a login, before the browser opens. `session` auth never logs in: a missing or expired saved state is an `auth` error, so "it should have logged in again" is expected there. `automated` and `human` reuse a saved state only while it has not expired, and log in again otherwise; an `automated` login is refused unless the site's `auth` permission allows it (`--yes-auth` where it says `ask`). `load_persona` only picks the persona file. | [Personas & contexts](https://github.com/noskule-cc/SiteMapper/wiki/concepts-persona-context) |
| Tenant contexts — one workflow, many tenants | `load_context` | A workflow's `requires:` contract is validated before the run starts; a missing role fails early with the name, which is why "it just exits" reports belong here. | [Personas & contexts](https://github.com/noskule-cc/SiteMapper/wiki/concepts-persona-context) |
| Variable resolution — `$name` across params, context, fixtures, captures | `Bindings.resolve` | Resolution order is params → context roles/ids → fixtures → captures; a value that "silently stays literal" means no binding matched, not a substitution bug. | [Workflows](https://github.com/noskule-cc/SiteMapper/wiki/concepts-workflow) |
| Scripts — API calls instead of DOM driving | `Runner.do_script` | `script_path` resolves site → project → app; a "not declared" error names all three homes it looked in. Stdout is always tried as JSON and kept as raw text when it does not parse, with no warning unless the step declares a `shape:` (then `drift`, "not JSON"). A capture holding a raw string means the script printed text: check the arguments in the step's `value`. | [Headless runs](https://github.com/noskule-cc/SiteMapper/wiki/features-headless-runs) |
| Run records — the folder a recorded run leaves in the runs store | `RunRecord` | A record stuck at `running` is a killed runner, not a slow one. Written outside the tree (`runs_root`), never linked from the generated views. Lifecycle and keys: `schema/run.yaml`. | [Results](https://github.com/noskule-cc/SiteMapper/wiki/concepts-result) |
| Runs retention — expired run folders are swept | `sweep_runs` | A "my run vanished" report means its `keep` ran out. A folder that is never swept has no readable `run.yaml` or is `waiting`. Rules: `schema/run.yaml`; policy: [tools/jobs.md](tools/jobs.md#runs-retention). | [Results](https://github.com/noskule-cc/SiteMapper/wiki/concepts-result) |
| Where the roots are — projects beside the lib tree, runs beside both | `projects_root` | Resolved by presence (`<root>/projects`, else `<root>/../projects`); a workflow "not found" on a shared data tree usually means the projects folder sits elsewhere, pass `--projects`. | [Framework vs deployment](https://github.com/noskule-cc/SiteMapper/wiki/concepts-framework-vs-deployment) |
| Generated inventory and dashboard | `collect_workflows` | The collectors are shared by both views; a wrong count in `overview.html` is almost always a collector bug, not a renderer one. | [Dashboard](https://github.com/noskule-cc/SiteMapper/wiki/features-dashboard) |
| Staleness chip and share link — "your changes aren't shared yet" | `Handler.map_dashboard` | Two gray elements, two meanings: a gray **artifact chip** is "none" or currency unknown (map repository: no `artifact_url` or no `published_hash` in `config.yaml`, or no git remote); a gray, dashed **share link** means stale. The framework page decides currency in `Handler.deployed_state` (dirty inputs or `HEAD` not pushed); a map repository compares `content_hash` of a fresh build with `published_hash`, which the publish step copies from `deploy_build`'s `build-info.json`. | [Dashboard](https://github.com/noskule-cc/SiteMapper/wiki/features-dashboard) |
| Staleness of the generated views themselves | `generated_is_stale` | CI runs `check.py`, so its "is stale" message comes from here, not from `inventory.py --check`. Compares a fresh render against the committed file, for `inventory.md`, `overview.html` and `lib-tree.json`. | [Health checks](https://github.com/noskule-cc/SiteMapper/wiki/features-health-checks) |
| Doc/registration consistency | `check_bindings` | Framework-only: it skips against `--root`, and a skipped check must never read as a pass. | [Health checks](https://github.com/noskule-cc/SiteMapper/wiki/features-health-checks) |

**Last Updated:** 2026-11-06
