# Development Guide

Working on the framework itself — the Python under `scripts/` and the contracts
under `schema/`. Using SiteMapper (mapping sites, writing workflows, running
them) is [../USAGE.md](../USAGE.md).

## Tech Stack

- **Language:** Python 3 (no build step, no packaging — the scripts are run directly)
- **Required dependency:** PyYAML, and nothing else for the framework's own checks and views
- **Optional dependency:** `mcp` 2.x (`pip install "mcp>=2.3,<3"`), needed only by `scripts/mcp_server.py` and its tests
- **Optional dependency:** Playwright (`pip install playwright`), needed only by the headless runner, and only for a workflow with a step other than `script`, `human` or a step on a captured value; it drives your installed Chrome (`channel="chrome"`), so there is no browser download
- **Serving:** `http.server` from the standard library — `scripts/serve.py` deliberately adds no web framework
- **Standard library first.** A new third-party dependency needs a reason in the PR
- **CI:** GitHub Actions (`.github/workflows/check.yml`) — the consistency checks plus a real headless run on every push

## The Seven Scripts

| Script | Role | Notes |
|--------|------|-------|
| `check.py` | every mechanical consistency check, non-zero exit on failure | the CI gate; `--only <name>` runs one, `--list` names them |
| `inventory.py` | walks the tree and renders `docs/inventory.md`; owns the collectors | `--check` fails when a generated view is stale |
| `overview.py` | renders `docs/overview.html` from `inventory.py`'s collectors | `--links github` and `--fragment` produce the shareable build |
| `libtree.py` | renders `lib-tree.json` at the lib root from the same collectors | the host's lib-neutral format (TeamOS#21); the host draws it as a tree |
| `run.py` | the headless deterministic runner: permission gate, session, steps, watch, result | the largest file; see the Reuse Rules in [architecture-rules.md](architecture-rules.md) |
| `serve.py` | serves the overview live with a run API, localhost only | keeps the permission gate server-side — the browser is untrusted UI |
| `mcp_server.py` | the workflows as MCP tools over stdio ([interface.md](interface.md#the-mcp-server)) | runs `run.py` as a child, so the gate and the record stay the runner's |

## Three Roots, Deliberately

`HOME` is this repository (schemas, docs, `.claude/`). `ROOT` is the tree being
checked or rendered, repointed by `--root <path>` at a private map repository.
`PROJECTS` is the projects tree and `RUNS` the runs store: inside `ROOT` in
this repository and in a classic map repository, beside it in a deployment's
shared data tree (`data/SiteMapper`, `data/projects`, `data/runs`).
`scripts/tree.py` resolves both by presence, so neither layout needs a flag;
`--projects` and `--runs` override it.

Every function that reads a *contract* must resolve against `HOME`; every
function that reads *data* must resolve against `ROOT` or `PROJECTS`. Getting
this wrong is not a small bug — `--root .` from a map repository once resolved
to the framework and reported it green. `inventory.py`, `overview.py` and
`libtree.py` expose `set_root(root, projects)` for the same reason, and all
three must be repointed together.

The alternative — copying the script and the schemas next to the maps — is
forbidden: a forked schema validates green against a contract nobody updated.

## File Organization

```
schema/     # Commented YAML templates — the format's source of truth
sites/      # Mapped sites: site.yaml + pages/ + workflows/ (building blocks) + scripts/, personas/, contexts/
apps/       # One application mapped as several tier sites: app.yaml (tier map, parity) + scripts/
projects/   # Questions: project.yaml + workflows/ + data/ + scripts/, grouped in folders
scripts/    # The seven executables above, plus tree.py (where the roots are)
docs/       # Everything agents and maintainers read — start at docs/INDEX.md
.claude/    # Skills and agents, each carrying its complete instructions
data/       # Copyable skeleton for a private map repository
runs/       # The runs store when it sits inside this tree — gitignored, never committed
```

## Common Tasks

**Add a check.** Write a function returning a list of failure strings, register
it in `CHECKS`, and give it a docstring whose first line is what it catches.
`--list` prints those docstrings. Every check exists because the thing it
catches actually happened, and the docstring says which. If the check cannot run against a `--root`
tree, add its name to `SKIPPED` and a `NOTES` line — a check that did not run
must never read like one that passed.

**Add a schema key.** [extending.md](extending.md) → "Add a schema key". The
key-set diff in `check.py` means the template update *is* the check update.

**Add a workflow action.** [extending.md](extending.md) → "Add a workflow
action". Four places, all of them enforced or documented; `key` and `script`
shipped without two of them once and went undocumented for weeks.

**Change the runner.** Run the acceptance workflow for real:
`python scripts/run.py search-issues --json`. CI's `runner-smoke` job runs the
same command.

**Change what a run record holds.** `RunRecord` in `run.py` writes `run.yaml`
twice, `running` before the first step and final at the end, and appends a
line to `RUNS/SiteMapper/index.<instance>.jsonl` each time. Their keys
belong to the deployment's run-record contract (connectOS
`contracts/run-record.yaml`), which changes first; then `schema/run.yaml`, then
the code. The index is appended under an exclusive file lock and is never
swept. `--trigger schedule` is what a scheduled task passes; the default is
`manual`. `python -m unittest discover tests` proves both lines and a killed
run's leftover `running` record.

**Change a generated view.** Edit the renderer, then re-run
`python scripts/inventory.py`. Never edit `docs/inventory.md`,
`docs/overview.html` or `lib-tree.json` by hand — `check.py` fails on staleness.

## Troubleshooting

- **`PyYAML not installed`** — `python -m pip install pyyaml`.
- **A link resolves locally but CI fails it.** NTFS is case-insensitive; Linux
  is not. `exists_cased` in `check.py` is the local guard, CI is the honest
  judge.
- **The runner refuses to start.** By design: agentic workflows, `verify` steps,
  an undeclared `effect` and a denied permission class are all rejected before
  the browser opens. The message names which. See [permissions.md](permissions.md).
- **`--root` reported the wrong tree.** A relative `--root` resolves against the
  shell's cwd captured *before* the chdir; if you added code that resolves paths
  after it, that is the bug.

**Last Updated:** 2026-10-20
