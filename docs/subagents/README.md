# Sub-Agents

Specialised instruction sets for self-contained work. Same layering as skills:
the reference doc here is neutral and authoritative, the host binding is a thin
pointer.

```
docs/subagents/<name>.md     the instructions — read by any host
.claude/agents/<name>.md     Claude binding: frontmatter + a pointer, no instructions
```

**A binding contains no instructions.** The moment one does, that host's
behaviour diverges from every other host's — silently, because it still works on
the machine where it was written.

## Skills vs. sub-agents

| | Skills (`docs/skills/`) | Sub-agents (`docs/subagents/`) |
|---|---|---|
| Context | inline, in the conversation | isolated (forked) |
| Trigger | slash command / description match | invoked explicitly for a task |
| Best for | interactive work, lightweight rules | verbose input, self-contained output, many at once |
| Overhead | minimal | significant per invocation — not worth it for a one-file edit |

Interactive work stays a skill. A sub-agent cannot ask the user anything, so
anything requiring confirmation — `/map-site`'s whole discovery loop — must not
become one.

## The rule that keeps them optional

**A sub-agent is an execution strategy, never part of the contract.** Every
workflow must produce an identical `result` on a host with no sub-agent concept.
Fan-out buys speed and context isolation, never behaviour. See
`INTERFACE.md` → Bindings.

Where work is mechanical, **prefer a script**: faster than fan-out, and it runs
on every host. See `CODE_OVER_LLM.md`.

## Fan-out safety

Browser tools are tab-scoped, so parallel agents can each own a tab. The *session*
behind those tabs is not: cookies, the active partner (Partnerwechsel) and sticky
UI state (grouping, sort, filters) are shared across every tab in the profile.

So fan out only over work that is **read-only and session-neutral**. Anything
that switches partner or changes sticky state runs serially, or concurrent agents
silently read another tenant's data.

## Available

| Agent | Use when |
|-------|----------|
| `workflow-companion` | A workflow YAML has no sibling `.md` |
| `validation-llm` | The docs were restructured — test them on a fresh LLM |

## Adding one

1. Write `docs/subagents/<name>.md` — purpose, responsibilities, required
   capabilities, output format, rules, checklist, what to return.
2. Add the binding `.claude/agents/<name>.md` — frontmatter plus a pointer.
3. Add a row to the table above and to `AGENTS.md`.
4. State required capabilities as *requirements* ("read-only; may write only
   under `sites/<site>/`"). A `tools:` allowlist is that requirement in
   host-specific syntax — the rule belongs in `guardrails.md`.
