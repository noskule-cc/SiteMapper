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

Eight mechanical checks over the YAML tree and the docs, non-zero exit on
failure. What each one catches, and what to do when it fires:

| Check | Catches | On failure |
|---|---|---|
| `yaml` | a file that does not parse | fix the YAML |
| `schema` | keys used by files but absent from `schema/*.yaml` (and vice versa, as notes) | add the key to the template, with its comment |
| `listings` | `site.yaml`/`project.yaml` naming files that are not on disk, or files nobody lists | fix the listing or add the file |
| `companions` | a workflow without its sibling `.md` | invoke the `workflow-companion` agent |
| `links` | markdown links, path refs and `screenshot:` targets that do not resolve (case-sensitively — Linux CI is the honest judge) | fix the reference, not the check |
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
to write a `results/` entry).

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
plus, where the run is worth keeping, a `results/` record.

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

## Results retention

Commit a run when it is **evidence someone will come back to** — the record
behind a published number, the reviewed green run behind a `trust: verified`
promotion, the reproduction of a bug. Routine green runs are noise; do not
commit them. Two guards, stated once here for every project:

- **Log size:** a device that is offline all window repeats one failure with a
  full stack trace — tens of MB, a few thousand unique lines. Commit the sibling
  `.md` summary; leave raw logs local.
- **Map repositories exclude `results/` blanket-style** in `.gitignore` (see
  `data/gitignore.template`), so committing a record is a deliberate exception,
  never a default.

## Housekeeping

- Prune remote branches whose work landed (`git branch -r --merged`).
- `__pycache__/`, `.runner/`, `.$*.bkp` (draw.io backups) are gitignored — if one
  shows up in `git status`, the gitignore of that repo regressed.
- The pre-2026-08-17 history is preserved on `backup/old-main-cb46c2b`
  locally; it is not on the remote and should not return there.
