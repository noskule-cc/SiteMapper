# Skills & Agents

All available skills and specialized agents for this project. **Project-owned:**
extend this file as you add skills and agents. Full instructions live in
`.claude/` — this registry routes every AI tool (Claude Code discovers them
natively; other tools read the linked files directly).

**Every SiteMapper skill is slash-only** (`disable-model-invocation: true`) — a
deliberate decision, not a default. Each one drives a browser against a real
site or edits maps; that is operator-initiated work, and auto-triggering on a
description match would sidestep the intent behind [permissions.md](permissions.md).
See [extending.md](extending.md).

## Skills

**SiteMapper skills** (slash commands, never auto-triggered):

| Skill | Trigger | Purpose |
|-------|---------|---------|
| [`map-site`](../.claude/skills/map-site/SKILL.md) | `/map-site <site>` | Human-in-the-loop discovery session for a site |
| [`run`](../.claude/skills/run/SKILL.md) | `/run <workflow>` | Execute a named workflow |
| [`test`](../.claude/skills/test/SKILL.md) | `/test <workflow>` | Execute a deterministic test workflow, emit a `result` |
| [`list-workflows`](../.claude/skills/list-workflows/SKILL.md) | `/list-workflows [site]` | Show available workflows from the generated inventory |
| [`verify-map`](../.claude/skills/verify-map/SKILL.md) | `/verify-map <site>` | On-demand drift check for a mapped site |
| [`repair`](../.claude/skills/repair/SKILL.md) | `/repair <workflow>` | Fix the map after a headless runner failure, restore trust |
| [`deploy-dashboard`](../.claude/skills/deploy-dashboard/SKILL.md) | `/deploy-dashboard` | Publish a dashboard to its artifact (framework page: automatic on push) |

**aiDocs job skills** (slash commands for runnable tasks):

| Skill | Purpose |
|-------|---------|
| [`/setup`](../.claude/skills/setup/SKILL.md) | Initial aiDocs setup in a project (interview form) |
| [`/update-aidocs`](../.claude/skills/update-aidocs/SKILL.md) | Pull upstream aiDocs standard updates |
| [`/validate-docs`](../.claude/skills/validate-docs/SKILL.md) | Validate doc structure (forked) |
| [`/maintain`](../.claude/skills/maintain/SKILL.md) | Dispatch maintenance jobs (`change`: diff-scoped pre-PR; `full`: cycle-end) |

**Convention skills** (slash command + auto-triggered):

| Skill | Purpose |
|-------|---------|
| [`/documentation`](../.claude/skills/documentation/SKILL.md) | Documentation writing rules |

**Auto-triggered skills** (no slash command, invoked automatically):

| Skill | Triggers when... |
|-------|-------------------|
| [`architecture-rules`](../.claude/skills/architecture-rules/SKILL.md) | Implementing features or writing new code |
| [`coding-workflow`](../.claude/skills/coding-workflow/SKILL.md) | Starting a development task (tracks the workflow steps incl. 8.5) |

## Agents

Full instructions in `.claude/agents/<name>.md`. Claude Code runs them forked;
other tools read and follow the file inline. An agent is an **execution
strategy, never part of the contract** — see [interface.md](interface.md).

| Agent | Purpose | Skill |
|-------|---------|-------|
| [`map-site-scout`](../.claude/agents/map-site-scout.md) | Read-only page-map draft for the human to review in `/map-site` | `map-site` |
| [`verify-map`](../.claude/agents/verify-map.md) | Background drift sweep of a whole site, read-only | `verify-map` |
| [`workflow-companion`](../.claude/agents/workflow-companion.md) | Write a workflow's sibling `.md` (purpose, at-a-glance, Mermaid flowchart) | — |
| [`validation-docs`](../.claude/agents/validation-docs.md) | Validate docs quality (judgment half; scripts do structure) | `/validate-docs` |
| [`validation-llm`](../.claude/agents/validation-llm.md) | Test docs effectiveness on a fresh LLM; Triage Eval Mode scores feature-map routing | — |
| [`issue-writer`](../.claude/agents/issue-writer.md) | GitHub issue creation with the right type, labels and estimate | — |

> `agent-name.template.md` in `.claude/agents/` is the blueprint for a new
> agent, not an agent.

**Last Updated:** 2026-08-26
