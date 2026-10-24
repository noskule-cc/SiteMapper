# Jobs

Runnable tasks for keeping the repo healthy. This is the central registry —
check here to see what is available before writing something new. `/maintain`
dispatches from this table; add project jobs here with their trigger class,
never to the skill.

Per [code-over-llm.md](../code-over-llm.md): a job that can run mechanically is a
script; only jobs needing judgement are skills or agents.

## Cycle-End Binding

Full maintenance (`/maintain full`) fires on a real project event, never a
calendar date:

- **Cycle-end event:** epic close — the repo's unit of work is the EPIC issue
  (e.g. #18 the headless runner, #27 the dashboard); when its last sub-issue
  closes, run `/maintain full`. There are no releases, tags or sprints to bind
  to. See [issue-tracker.md](../issue-tracker.md).

## Available Jobs

| Job | Command | Trigger class | Runs when |
|-----|---------|---------------|-----------|
| [Repo consistency checks](#repo-consistency-checks) | `python scripts/check.py [--root <maps>]` | per-change | any change, before committing (also runs in CI) |
| [Check docs (mechanical)](#check-docs) | `python docs/tools/check-docs.py` | per-change | any doc or feature-map change |
| [Regenerate views](#regenerate-views) | `python scripts/inventory.py [--root <maps>]` | per-change | a site, page, workflow or project was added or removed |
| [Headless workflow run](#headless-workflow-run) | `python scripts/run.py <workflow> --param k=v` | per-change | a deterministic workflow changed |
| [Runner tests](#runner-tests) | `python -m unittest discover tests` | per-change | `scripts/run.py` changed (also runs in CI) |
| [Live dashboard](#live-dashboard) | `python scripts/serve.py [--root <maps>]` | on demand | you want the dashboard with real run buttons |
| [Deploy the dashboard](#deploy-the-dashboard) | automatic on push; fallback `/deploy-dashboard` | on demand | the shared page must show uncommitted or out-of-band state |
| [Map drift check](#map-drift-check) | `/verify-map <site>` | on demand | a workflow step failed to find a mapped element |
| [Deterministic UI test](#deterministic-ui-test) | `/test <workflow>` | per-change | a deterministic workflow changed |
| [Map repair](#map-repair) | `/repair <workflow>` | on demand | a headless run failed and degraded `trust` to `broken` |
| [Validate docs (judgment)](#validate-docs) | Invoke `validation-docs` agent | cycle-end | docs/ or wiki changed since last run |
| [Triage evals](#triage-evals) | Invoke `validation-llm` agent (Triage Eval Mode) | cycle-end | feature-map, evals, or routing docs changed since last run |

**Trigger classes:**

- **per-change** — diff-conditional; dispatched by `/maintain change` before each
  PR (pre-PR contract in `AGENTS.md`)
- **cycle-end** — judgment and eval battery; dispatched by `/maintain full` at
  the bound event, scoped to changes since the last-run stamp
  (`docs/.maintain-last-run`)
- **on demand** — operator-initiated; never dispatched automatically

`check.py` and `inventory.py` accept `--root <path>` to run against a separate
map repository. Schemas and bindings still come from this repo, so a map
repository never carries a forked copy.

## Job Details

### Repo consistency checks

Fifteen mechanical checks over the YAML tree and the docs, non-zero exit on
failure. What each one catches, and what to do when it fires:

| Check | Catches | On failure |
|---|---|---|
| `yaml` | a file that does not parse | fix the YAML |
| `schema` | keys used by files but absent from `schema/*.yaml` (and vice versa, as notes) | add the key to the template, with its comment |
| `listings` | `site.yaml`/`project.yaml`/`app.yaml` naming files that are not on disk, or files nobody lists; a project without a `kind`, a producer without a `dataset`, a `state` file inside the project folder; a workflow without `mode` or with an `effect` other than `read-only`, `mutating`, `destructive` | fix the listing, add the file, or declare the key |
| `companions` | a workflow without its sibling `.md` | invoke the `workflow-companion` agent |
| `apps` | a tier naming a missing site, a site whose `environment` disagrees with its tier key, a site in two apps, an app script also declared by a site | fix `app.yaml` or the site's settings |
| `placement` | a site workflow carrying `tiers`, `sites:` or tier-keyed fixtures, or stepping onto another site | move it into a project |
| `tiers` | `required` ⊄ `allowed` ⊄ the app's tiers; a tier neither allowed nor declared absent; `environment` options ≠ allowed; a missing `fixtures.<tier>` | declare the tier or its absence with a reason |
| `scripts` | a script declared nowhere, or declared in a home that does not cover every caller | move it to the narrowest home that does |
| `parity` | a page map on one tier of an app and not on another, unless declared under `parity.gaps`; a stale gap | map the page, or declare the gap with a reason |
| `rollback` | a mutating workflow without `rollback`, `none` without a reason, `snapshot` without a capturing phase | declare it |
| `produced` | a `results/` or `state/` folder under a site or a project | move it to the runs or state store |
| `links` | markdown links, path refs and `screenshot:` targets that do not resolve (case-sensitively — Linux CI is the honest judge) | fix the reference, not the check |
| `endpoints` | a page `endpoints` entry with a key outside the schema (a header, a cookie, a description), a field of the wrong type, a name that is not snake_case, a token-shaped path segment, host label, query key or placeholder, a literal query value, a fragment, an undeclared `effect` or an input that names no element; `gotchas` that are not a list of strings; a secret header, credential or token in `purpose`, `gotchas` or `settings` | replace the value with a `{placeholder}` or delete it; the message never shows the value |
| `bindings` | a skill or agent in `.claude/` that is unregistered in `docs/skills-and-agents.md`, or a project doc unreachable from `docs/project-index.md` | finish the registration (framework repo only) |
| `inventory` / `overview` | generated views out of date | `python scripts/inventory.py` |

CI runs the same checks on every push, plus the headless runner smoke test.

### Check docs

Structural checks of the aiDocs doc set: link resolution (case-sensitive),
orphan pages, index consistency, agent/skill registration, template hygiene,
feature-map entry-point resolution.

1. Run `python docs/tools/check-docs.py`
2. Exit code non-zero on errors; warnings don't fail the build

### Regenerate views

`scripts/inventory.py` regenerates `docs/inventory.md` and
`docs/overview.html` from the YAML tree. `--check` exits non-zero when either
is stale; never hand-edit the generated files.

### Headless workflow run

`scripts/run.py` executes a `mode: deterministic` workflow with no LLM in the
loop and emits a `result` (`--json` for the machine-readable form, `--record`
to write a run folder to the runs store; a `rollback: snapshot` workflow is
recorded always).

### Runner tests

`tests/` runs `scripts/run.py` as a subprocess against a fixture tree in a
temporary folder, with no browser: script, human and capture steps only. It
covers what a real run of the acceptance workflow cannot show, such as the
record a killed run leaves behind.

### Live dashboard

`scripts/serve.py` serves `docs/overview.html` at `http://127.0.0.1:8765/`,
rendered fresh on every load, with run buttons that execute for real. The
permission gate stays server-side — see [permissions.md](../permissions.md).

### Deploy the dashboard

**Automatic on push:** the `deploy-dashboard` cloud routine republishes the
standing artifact on every push to `noskule-cc/SiteMapper` and daily at 03:00
UTC as a safety net. The standing URL is
<https://claude.ai/code/artifact/88589587-c88d-4092-b4d7-3e1ac07e47a7> —
framework page only. A map repository's page deploys, consent-gated and manual
only, to its OWN private artifact registered in its `config.yaml` (#34,
[permissions.md](../permissions.md) → "Dashboard deploy"). Manual fallback: the
live page's deploy button builds, `/deploy-dashboard` publishes.

### Map drift check

`/verify-map <site>` walks a whole map and reports FOUND / MISSING per element.
For a background sweep across sites, invoke the `verify-map` agent instead.

Do this when a workflow step fails to find a mapped element, and periodically
for sites you do not control — a long-stale `verified_at` in `site.yaml` is the
signal. There is no fixed cadence worth pretending to have; the honest trigger
is "the site shipped a release" or "a run broke".

### Deterministic UI test

`/test <workflow>` evaluates the workflow's `assert` steps and emits a `result`
plus, where the run is worth keeping, a run folder in the runs store.

### Map repair

`/repair <workflow>` consumes the runner's `--json` failure report, patches the
**map** (never the workflow, never a weakened assert), re-runs, and restores
`trust`. `mapped_at` far behind reality plus repeated repairs on one page means
re-map the page (`/map-site`), not another patch.

### Validate docs

Judgment checks a script can't do: duplicated knowledge, stale content, wiki
structure, file focus.

1. Invoke the `validation-docs` agent (auto-discovered from `.claude/agents/`)
2. Its instructions run `check-docs.py` first, then the judgment checklist
3. Output: report with issues to fix

### Triage evals

Routing-effectiveness test: bug-report-phrased questions from
[evals.md](evals.md) run against a fresh agent, scored on landing at the
expected entry point (with and without `feature-map.md`).

1. Invoke the `validation-llm` agent — Triage Eval Mode runs when
   `tools/evals.md` exists
2. Output: hit-rate report per mode, misses diagnosed with navigation traces

## Runs retention

Nothing a run wrote is ever committed. A recorded run is a folder in the runs
store (`schema/run.yaml`), outside every repository; `check.py`'s `produced`
check fails a `results/` or `state/` folder under a site or a project, and
`.gitignore` (`data/gitignore.template` for a map repository) excludes the
stores as a class. The rules, stated once here for every project:

- **A run folder lives one day** unless the project's `keep:` says longer. A
  run that is **evidence someone will come back to** — the record behind a
  published number, the reviewed green run behind a `trust: verified`
  promotion, the reproduction of a bug — is kept by the page that cites it:
  that page cites the run id, and the run's `run.yaml` says `keep: keep`.
- **Who sweeps, when:** `run.py` sweeps the runs store after every recorded
  run, and `python scripts/run.py --sweep [--runs PATH] [--dry-run]` sweeps
  on demand (a scheduler may call it). The sweep covers every lib's records,
  since all libs write the same `run.yaml`; a folder without a readable
  `run.yaml` (a migration's `legacy-results/`) is never touched. Rules for
  `keep`: `schema/run.yaml`.
- **A snapshot run is always recorded**, so the pre-state of a mutating
  workflow outlives the session and the machine.
- **Log size:** a device that is offline all window repeats one failure with a
  full stack trace — tens of MB. The project's `keep` is the brake; a summary
  on the citing page is what people read.

## Housekeeping

- Prune remote branches whose work landed (`git branch -r --merged`).
- `__pycache__/`, `.runner/`, `.$*.bkp` (draw.io backups) are gitignored — if one
  shows up in `git status`, the gitignore of that repo regressed.
- The pre-2026-08-17 history is preserved on `backup/old-main-cb46c2b`
  locally; it is not on the remote and should not return there.
