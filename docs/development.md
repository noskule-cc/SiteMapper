# Development Guide

Working on the framework itself — the Python under `scripts/` and the contracts
under `schema/`. Using SiteMapper (mapping sites, writing workflows, running
them) is [../USAGE.md](../USAGE.md).

## Tech Stack

- **Language:** Python 3 (no build step, no packaging — the scripts are run directly)
- **Required dependency:** PyYAML, and nothing else for the framework's own checks and views
- **Optional dependency:** Playwright (`pip install playwright`), needed only by the headless runner; it drives your installed Chrome (`channel="chrome"`), so there is no browser download
- **Serving:** `http.server` from the standard library — `scripts/serve.py` deliberately adds no web framework
- **Standard library first.** A new third-party dependency needs a reason in the PR
- **CI:** GitHub Actions (`.github/workflows/check.yml`) — the consistency checks plus a real headless run on every push

## The Five Scripts

| Script | Role | Notes |
|--------|------|-------|
| `check.py` | every mechanical consistency check, non-zero exit on failure | the CI gate; `--only <name>` runs one, `--list` names them |
| `inventory.py` | walks the tree and renders `docs/inventory.md`; owns the collectors | `--check` fails when a generated view is stale |
| `overview.py` | renders `docs/overview.html` from `inventory.py`'s collectors | `--links github` and `--fragment` produce the shareable build |
| `run.py` | the headless deterministic runner: permission gate, session, steps, watch, result | the largest file; see the Reuse Rules in [architecture-rules.md](architecture-rules.md) |
| `serve.py` | serves the overview live with a run API, localhost only | keeps the permission gate server-side — the browser is untrusted UI |

## Two Roots, Deliberately

`HOME` is this repository (schemas, docs, `.claude/`). `ROOT` is the tree being
checked or rendered, repointed by `--root <path>` at a private map repository.

Every function that reads a *contract* must resolve against `HOME`; every
function that reads *data* must resolve against `ROOT`. Getting this wrong is
not a small bug — `--root .` from a map repository once resolved to the
framework and reported it green. `inventory.py` and `overview.py` expose
`set_root()` for the same reason, and both must be repointed together.

The alternative — copying the script and the schemas next to the maps — is
forbidden: a forked schema validates green against a contract nobody updated.

## File Organization

```
schema/     # Commented YAML templates — the format's source of truth
sites/      # Mapped sites: site.yaml + pages/ + workflows/ (+ scripts/, personas/, contexts/)
projects/   # Cross-site projects (none in the framework repo)
scripts/    # The five executables above
docs/       # Everything agents and maintainers read — start at docs/INDEX.md
.claude/    # Skills and agents, each carrying its complete instructions
data/       # Copyable skeleton for a private map repository
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

**Change a generated view.** Edit the renderer, then re-run
`python scripts/inventory.py`. Never edit `docs/inventory.md` or
`docs/overview.html` by hand — `check.py` fails on staleness.

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

**Last Updated:** 2026-09-19
