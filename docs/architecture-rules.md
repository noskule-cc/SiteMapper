# SiteMapper Architecture Rules

Enforceable design principles. The `architecture-rules` skill auto-reads this
file before writing new code.

> **Companion skill:** `.claude/skills/architecture-rules/SKILL.md` auto-triggers during coding.

## Layer Boundaries

SiteMapper's layers are files, not packages. The dependency direction:

```
schema/  ←  sites/ + projects/ (data)  ←  scripts/ (executors)  ←  .claude/ + docs/ (instructions)
```

| Rule | Allowed | Forbidden |
|------|---------|-----------|
| `schema/*.yaml` | comments only — it is a commented template, and the comment IS the documentation | importing, generating or deriving from anything |
| `sites/`, `projects/` data | reference schema keys, reference `settings:` by key | embedding a credential, a contact value, or host tool names |
| `scripts/` | read the schema and the data, emit `result` | pushing a result anywhere; deciding what to do with it |
| `.claude/` skills and agents | name *capabilities* (navigate, click, read page) | naming a host's concrete tools |
| `docs/host-bindings.md` | the only place host tool names appear | project behaviour or step semantics |

**Framework vs. map repository is also a boundary.** The framework repo holds
schemas, scripts, docs and one demo site. A deployment's real maps live in its
own private repository, bootstrapped from `data/`. Nothing about a real
deployment — tenant name, hostname, identifier, fleet data — belongs in this
repo, its wiki, or the generated dashboard.

## Design Principles

- **LLM for decisions, code for work.** [code-over-llm.md](code-over-llm.md) is
  the governing rule; `mode: deterministic` vs `agentic` is how a workflow
  declares which side it is on.
- **Declared, not inferred.** A workflow states its `effect`; a page states its
  `fingerprint`; a site states its `scripts`. A runner cannot judge whether a
  click mutates, so it never tries.
- **Trust and permission are independent axes.** `trust: verified` means proven
  to run. It never means allowed to write.
- **One tool, many trees.** `check.py`, `inventory.py`, `run.py` and `serve.py`
  take `--root <path>` and keep their schemas from the framework. A forked
  schema next to the maps is worse than no check.
- **Patch the map, never the workflow.** Drift is a map problem. Editing a
  workflow step or weakening an assert to make a run green destroys the only
  signal the system has.
- **Generated files are never hand-edited.** `docs/inventory.md` and
  `docs/overview.html` are rendered; a staleness check fails the build.
- **One capability, one file.** A skill or agent carries its complete
  instructions in exactly one place. A second copy per host diverges silently.

## Reuse Rules

Before implementing new logic, check this table. If what you need exists, use it.

### Loading and resolution

| Need | Use | Location |
|------|-----|----------|
| Parse a YAML file | `load_yaml` | `scripts/run.py` |
| Locate a workflow by name across sites and projects | `find_workflow` | `scripts/run.py` |
| Site config, page map, element lookup | the `Site` class (`page`, `element`) | `scripts/run.py` |
| Merge layered `settings:` (global → site → page) | `resolve_settings` / `deep_merge` | `scripts/run.py` |
| Resolve `$name` (params → context → fixtures → captures) | the `Bindings` class (`lookup`, `resolve`) | `scripts/run.py` |
| Read a secret by reference, never by value | `env_secret` | `scripts/run.py` |

### Policy and trust

| Need | Use | Location |
|------|-----|----------|
| Decide allow/ask/deny for one action class | `permission_verdict` | `scripts/run.py` |
| Gate a whole run up front, strictest site wins | `gate` | `scripts/run.py` |
| Write `trust:` / `verified_at:` back into a workflow YAML | `update_trust` | `scripts/run.py` |

### Views

| Need | Use | Location |
|------|-----|----------|
| Enumerate sites / workflows / projects | `collect_sites`, `collect_workflows`, `collect_projects` | `scripts/inventory.py` |
| Point a generator at another tree | `set_root` | `scripts/inventory.py`, `scripts/overview.py` |
| Render the dashboard HTML from those collectors | `render` | `scripts/overview.py` |
| Detect a stale generated view | `stale` | `scripts/inventory.py` |

### Checks

| Need | Use | Location |
|------|-----|----------|
| Case-exact path existence (NTFS hides Linux breakage) | `exists_cased` | `scripts/check.py`, `docs/tools/check-docs.py` |
| A new class of mechanical drift | add a function to `CHECKS` | `scripts/check.py` |

## Extension Points

How to add a skill, agent, workflow action, schema key, site script or host:
[extending.md](extending.md). Every one of them ends with a registration step
that `scripts/check.py` enforces.

## Anti-Patterns

| Don't | Do Instead | Why |
|-------|-----------|-----|
| Copy `check.py` or `schema/` next to a map repository | run the framework's copy with `--root` | A forked schema validates green against a contract nobody updated |
| Write a rule into a doc that asks someone to remember | add a check that exits non-zero | 7 of 9 findings in the 2026-08-05 audit were mechanically detectable |
| Name a host's tool inside a skill or agent | name the capability; map it in `host-bindings.md` | The instructions stop being portable the moment one host's vocabulary leaks in |
| Guess a locator into a map to make a run pass | ask for a focused re-map | A plausible-but-wrong locator fails only sometimes — worse than a missing one |
| Fan out over work that switches tenant or sticky UI state | run it serially | The session behind the tabs is shared; concurrent agents read another tenant's data |
| Put a project-true fact in agent memory | put it in the map, the site config, or the schema | [knowledge-placement.md](knowledge-placement.md) |
| Hand-edit `inventory.md` or `overview.html` | re-run `scripts/inventory.py` | The staleness check will fail the build anyway |

## Known Violations

| File | Violation | Status |
|------|-----------|--------|
| — | — | — |

**Last Updated:** 2026-08-26
