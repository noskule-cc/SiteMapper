# Extending SiteMapper

How to add each kind of building block. **Patterns only, never instances** —
the moment this file describes what a specific skill does, it duplicates that
skill's own doc and starts to drift (`KNOWLEDGE_PLACEMENT.md`). Every pattern
here ends the same way: register the new thing, then run
`python scripts/check.py` — most steps below are enforced by a check, and the
check failing is the reminder working.

Before building anything, `CODE_OVER_LLM.md`: if a script can do it, it is a
script, not a skill or an agent.

## Add a skill

1. Write the neutral instructions: `docs/skills/<name>.md` — steps in terms of
   *capabilities* (navigate, read DOM, click…), never host tool names; those
   live only in `HOST_BINDINGS.md`.
2. Add the thin binding: `.claude/skills/<name>/SKILL.md` — frontmatter plus
   "Follow the instructions in `docs/skills/<name>.md`". **A binding contains
   no instructions.** Keep `disable-model-invocation: true` unless the skill
   was deliberately chosen to auto-trigger (see the taxonomy note in
   `subagents/README.md`).
3. Register: a situational row in `AGENTS.md`, its skills table, and
   `INDEX.md`; a `JOBS.md` row if it is a runnable job.

A skill is the right unit for *interactive* work an operator initiates. A
repeatable step sequence against a mapped site is a **workflow**, not a skill.

## Add a sub-agent

The generic half (skills vs. sub-agents, naming, wrapper format, when to
build one) is `subagents/README.md` — start there. The SiteMapper additions:
reference doc in `docs/subagents/<name>.md`, binding in `.claude/agents/`,
rows in the README table and `AGENTS.md`. State required capabilities as
requirements; a `tools:` allowlist is that requirement in host syntax.

## Add a workflow action

1. `schema/workflow.yaml` — the action in the `steps` comment block, with its
   semantics (what `value`, `capture`, `expect` mean for it).
2. Both skill docs that execute steps: `docs/skills/run-workflow.md` and
   `docs/skills/test.md`.
3. `HOST_BINDINGS.md` — which capability implements it per host.
4. The headless runner: a `do_<action>` method in `scripts/run.py`.

`key` and `script` shipped without steps 2–3 once and went undocumented for
weeks — that is the failure mode this list exists for.

## Add a schema key

1. Add it to the `schema/*.yaml` template **with its comment** — the schemas
   are commented templates, and the comment is the documentation.
2. `check.py`'s schema check is a key-set diff, so the template update *is*
   the check update. A key used by files but missing from the template fails;
   a template key no file uses yet is only a note.
3. If an executor must act on the key (runner, skills), update it in the same
   change — a key nobody reads is documentation-shaped decoration.

## Add a site script

1. `sites/<site>/scripts/<name>` (+ a `scripts/README.md` beside it for auth
   notes and parked-code rationale).
2. Declare it in that site's `site.yaml` `scripts:` list — declaration is what
   makes it addressable from `action: script` steps.
3. Prefer `--json` output so step `capture` gets structured data.

---

**Last Updated:** 2026-08-20
