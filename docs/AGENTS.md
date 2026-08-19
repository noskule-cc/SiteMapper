# AGENTS.md — SiteMapper LLM Entry Point

**Audience:** any AI agent working on this project — Claude Code, Codex, Cursor,
Copilot. Host-specific tool names live in one file only
([HOST_BINDINGS.md](HOST_BINDINGS.md)); everything else here applies to all of them.

## Mandatory Reading

- [docs/INDEX.md](INDEX.md) — navigation map of all documentation
- [docs/GUARDRAILS.template.md](GUARDRAILS.template.md) — how to write the standing rules a
  deployment follows. The rules THEMSELVES are deployment-specific and live with that
  deployment's own maps, not here (see INDEX.md).

## Situational References

| When you're...                          | Read...                                  |
|-----------------------------------------|------------------------------------------|
| Mapping a new site                      | `docs/skills/map-site.md`               |
| Running a workflow                      | `docs/skills/run-workflow.md`           |
| Running a UI **test** workflow          | `docs/skills/test.md`                   |
| Listing available workflows             | `docs/skills/list-workflows.md`         |
| Asking what exists in the repo          | `docs/inventory.md` (generated)         |
| Showing a **human** what exists         | `docs/overview.html` (generated) — open in a browser |
| Checking a map for drift                | `docs/skills/verify-map.md`             |
| Looking up which tool does what         | `docs/HOST_BINDINGS.md`                 |
| Writing a new workflow YAML             | `schema/workflow.yaml` (+ a sibling `<workflow>.md` with a Mermaid flowchart — see `USAGE.md`) |
| Emitting or consuming a run result      | `schema/result.yaml`, `docs/INTERFACE.md` |
| Creating a cross-site project           | `schema/project.yaml`                   |
| Configuring contact/behavior/defaults   | `schema/settings.yaml`, `config.yaml`   |
| Being called by another system          | `docs/INTERFACE.md`                     |
| Understanding the project               | `PRD.md`                                |
| Writing or updating documentation       | `docs/INFORMATION_MINIMALISM.md`, then `docs/DOCUMENTATION_GUIDELINES.md` (which level it goes on) |
| Documenting how SiteMapper *functions*  | the wiki — see `docs/wiki.md`           |
| Looking for a runnable maintenance task | `docs/JOBS.md`                          |
| Deciding script vs. LLM for a task      | `docs/CODE_OVER_LLM.md`                 |
| Finding drift a script could catch      | add a check to `scripts/check.py`       |
| Creating or invoking a sub-agent        | `docs/subagents/README.md`              |
| Deciding **where** a fact belongs       | `docs/KNOWLEDGE_PLACEMENT.md`           |
| Opening an issue or recording a decision| `docs/issue-tracker.md`                 |
| About to save something to agent memory | `docs/KNOWLEDGE_PLACEMENT.md` **first** |
| Checking the repo before a commit       | `scripts/check.py`                      |
| Adding/removing a site or workflow      | re-run `scripts/inventory.py`           |

## Available Skills

Invoked as slash commands in hosts that support them; in other hosts, read the
doc and follow it directly.

| Skill            | Trigger           | Purpose                                    |
|------------------|-------------------|--------------------------------------------|
| map-site         | `/map-site`       | Start a discovery session for a site       |
| run              | `/run`            | Execute a named workflow                   |
| test             | `/test`           | Execute a deterministic test workflow and emit a `result` |
| list-workflows   | `/list-workflows` | Show available workflows                   |
| verify-map       | `/verify-map`     | On-demand drift check for a mapped site    |

## Key Concepts

- **Site maps** are YAML files in `sites/<site-name>/pages/` describing page elements and gotchas.
- **Workflows** are YAML files in `sites/<site-name>/workflows/` defining step sequences, each with a sibling `<workflow>.md` — a short human-readable summary with a Mermaid flowchart.
- **Cross-site workflows** live in `projects/<project>/workflows/` and span multiple sites using capture variables.
- **Schemas** in `schema/` define the YAML format for pages, sites, workflows, projects, settings and results.
- **Settings** are layered (`config.yaml` global → `site.yaml` → page YAML), merged most-specific-wins; `policy.permissions` (allow/ask/deny per action class) gates what a run may do — see `docs/PERMISSIONS.md`.
- **A workflow's `mode`** is `deterministic` (mechanical, runnable with no LLM) or `agentic` (needs judgement). Tests should be deterministic.
- **Prefer a script over the browser.** Where data is reachable from a site's API, `action: script` is faster, headless, host-neutral, and does not break when the UI changes.
- **The repo is the source of truth; agent memory is a staging area.** Project-true facts live in the repo (page `gotchas`, `scripts/README.md`, `settings:`, the deployment's guardrails); machine- or person-specific facts live in the host agent's own memory store. Never both — when they disagree, the repo wins. See `docs/KNOWLEDGE_PLACEMENT.md`.
- **Open decisions are GitHub issues**, not files in this repo. See `docs/issue-tracker.md`.

## Sub-Agents

Specialised instruction sets for self-contained work, in `docs/subagents/` with
thin host wrappers (`.claude/agents/`). A sub-agent is an execution strategy,
never part of the contract — see [subagents/README.md](subagents/README.md).

| Agent | Use when |
|-------|----------|
| `workflow-companion` | A workflow YAML has no sibling `.md` |
| `validation-llm` | The docs were restructured — test them on a fresh LLM |

## Host Bindings

This project is host-independent. `docs/` is neutral and authoritative;
`.claude/` (and any future equivalent) holds thin registration stubs that point
back at it and contain no instructions of their own. See
[HOST_BINDINGS.md](HOST_BINDINGS.md) and [INTERFACE.md](INTERFACE.md) → Bindings.

**Last Updated:** 2026-08-19
