# Creating Skills and Agents

How to create and register specialized AI instructions for your project. Everything lives in `.claude/` as the single source of truth; `docs/skills-and-agents.md` is the registry that routes every AI tool there.


## Skills vs. Agents

Both are specialized instructions. Choose based on weight and trigger style:

| | Skills (`.claude/skills/<name>/SKILL.md`) | Agents (`.claude/agents/<name>.md`) |
|---|---|---|
| **Context** | Runs inline in conversation | Runs in isolated context (forked) |
| **Trigger** | Auto-triggered by description match, or slash command | Explicitly invoked |
| **Best for** | Lightweight rules, quick jobs, knowledge injection | Heavy computation, verbose output, multi-step workflows |
| **Other AI tools** | Read the SKILL.md and follow it inline | Read the agent file and follow it inline |

**When to create which:**

- **Skill** — simple rule enforcement, slash command for a tool, lightweight knowledge
- **Agent** — produces long output, needs full isolation, requires many tool calls
- **Both** — an agent whose triggering should be automatic gets a thin companion skill that invokes it

Full instructions live **in the skill or agent file itself** — never split "trigger here, knowledge elsewhere". One capability, one file, one registry row.


## Agent File Format

Each `.claude/agents/<name>.md` carries YAML frontmatter plus its complete instructions (see `agent-name.template.md` for the blueprint):

```markdown
---
name: agent-name
description: One line — when to invoke this agent
tools: Read, Grep, Glob
---

# agent-name

One-line description.

## Purpose
## When to Invoke
## Before Starting        (prerequisite reads)
## Responsibilities
## Key Files
## Patterns               (code patterns and examples)
## Checklist
## Related Agents
## References
```

Omit a section only when it genuinely doesn't apply.


## Creating a New Skill or Agent

1. Identify a repeatable task area (skip one-offs and things an existing skill/agent covers)
2. Create the file: `.claude/skills/<name>/SKILL.md` or `.claude/agents/<name>.md` (copy `agent-name.template.md`)
3. Register it in `docs/skills-and-agents.md` (purpose, trigger, companion skill if any)
4. Test it on a real task

`docs/AGENTS.md` is a fixed standard file — never edit it; it already points every tool at the registry.


## Naming

Lowercase, hyphenated:

- `db-expert` not `DatabaseExpert`
- `unit-test` not `UnitTesting`


**Last Updated:** 2026-08-20
