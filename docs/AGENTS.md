# AGENTS.md — SiteMapper LLM Entry Point

**Audience:** any AI agent working on this project — Claude Code, Codex, Cursor,
Copilot. Host-specific tool names live in one file only
([HOST_BINDINGS.md](HOST_BINDINGS.md)); everything else here applies to all of them.

## Mandatory Reading

- [docs/INDEX.md](INDEX.md) — navigation map of all documentation
- [docs/guardrails.md](guardrails.md) — standing rules every session follows

## Situational References

| When you're...                          | Read...                                  |
|-----------------------------------------|------------------------------------------|
| Mapping a new site                      | `docs/skills/map-site.md`               |
| Running a workflow                      | `docs/skills/run-workflow.md`           |
| Running a UI **test** workflow          | `docs/skills/test.md`                   |
| Listing available workflows             | `docs/skills/list-workflows.md`         |
| Asking what exists in the repo          | `docs/inventory.md` (generated)         |
| Checking a map for drift                | `docs/skills/verify-map.md`             |
| Looking up which tool does what         | `docs/HOST_BINDINGS.md`                 |
| Writing a new workflow YAML             | `schema/workflow.yaml` (+ a sibling `<workflow>.md` with a Mermaid flowchart — see `USAGE.md`) |
| Emitting or consuming a run result      | `schema/result.yaml`, `docs/INTERFACE.md` |
| Creating a cross-site project           | `schema/project.yaml`                   |
| Configuring contact/behavior/defaults   | `schema/settings.yaml`, `config.yaml`   |
| Being called by another system          | `docs/INTERFACE.md`                     |
| Understanding the project               | `PRD.md`                                |
| Writing or updating documentation       | `docs/INFORMATION_MINIMALISM.md`        |
| Deciding **where** a fact belongs       | `docs/KNOWLEDGE_PLACEMENT.md`           |
| Opening an issue or recording a decision| `docs/issue-tracker.md`                 |
| About to save something to agent memory | `docs/KNOWLEDGE_PLACEMENT.md` **first** |
| Validating YAML before commit           | `scripts/lint.py`                       |
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
- **Settings** are layered (`config.yaml` global → `site.yaml` → page YAML), merged most-specific-wins; `policy.safe_to_submit_forms` gates form submission.
- **A workflow's `mode`** is `deterministic` (mechanical, runnable with no LLM) or `agentic` (needs judgement). Tests should be deterministic.
- **Prefer a script over the browser.** Where data is reachable from a site's API, `action: script` is faster, headless, host-neutral, and does not break when the UI changes.
- **The repo is the source of truth; agent memory is a staging area.** Project-true facts live in the repo (page `gotchas`, `scripts/README.md`, `settings:`, `guardrails.md`); machine- or person-specific facts live in the host agent's own memory store. Never both — when they disagree, the repo wins. See `docs/KNOWLEDGE_PLACEMENT.md`.
- **Open decisions are GitHub issues**, not files in this repo. See `docs/issue-tracker.md`.

## Host Bindings

This project is host-independent. `docs/` is neutral and authoritative;
`.claude/` (and any future equivalent) holds thin registration stubs that point
back at it and contain no instructions of their own. See
[HOST_BINDINGS.md](HOST_BINDINGS.md) and [INTERFACE.md](INTERFACE.md) → Bindings.

**Last Updated:** 2026-08-05
