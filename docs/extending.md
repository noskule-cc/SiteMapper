# Extending SiteMapper

How to add each kind of building block. **Patterns only, never instances** —
the moment this file describes what a specific skill does, it duplicates that
skill's own file and starts to drift ([knowledge-placement.md](knowledge-placement.md)).
Every pattern here ends the same way: register the new thing, then run
`python scripts/check.py` — most steps below are enforced by a check, and the
check failing is the reminder working.

Before building anything, [code-over-llm.md](code-over-llm.md): if a script can
do it, it is a script, not a skill or an agent.

The generic half — skills vs. agents, file format, naming, registration — is
[CREATING_AGENTS.md](CREATING_AGENTS.md). This file carries only the SiteMapper
additions.

## Add a skill

1. Write `.claude/skills/<name>/SKILL.md`: frontmatter plus the **complete**
   instructions. Steps are stated in terms of *capabilities* (navigate, read
   DOM, click…), never host tool names; those live only in
   [host-bindings.md](host-bindings.md). Other AI tools read this same file
   inline — that is what keeps the instructions host-neutral even though the
   directory is named after one host.
2. Keep `disable-model-invocation: true` unless the skill was deliberately
   chosen to auto-trigger (see "All skills are slash-only" below).
3. Register: a row in [skills-and-agents.md](skills-and-agents.md), and a
   [tools/jobs.md](tools/jobs.md) row if it is a runnable job.

A skill is the right unit for *interactive* work an operator initiates. A
repeatable step sequence against a mapped site is a **workflow**, not a skill.

### All skills are slash-only

Every SiteMapper skill drives a browser against a real site or edits maps; that
is operator-initiated work, and auto-triggering on a description match would
sidestep the intent behind [permissions.md](permissions.md). A future skill that
is pure knowledge injection may opt in to auto-triggering; say so in its file
when it does. (The aiDocs standard skills shipped in `.claude/skills/` follow
their own upstream trigger settings.)

## Add an agent

1. Write `.claude/agents/<name>.md`: frontmatter plus the complete instructions
   (blueprint: `.claude/agents/agent-name.template.md`).
2. Add a row to [skills-and-agents.md](skills-and-agents.md).
3. State required capabilities as *requirements* ("read-only; may write only
   under `sites/<site>/`"). A `tools:` allowlist is that requirement in
   host-specific syntax — the standing rule itself belongs in the deployment's
   `docs/guardrails.md`.

An agent is an **execution strategy, never part of the contract** — every
workflow must produce an identical `result` on a host with no sub-agent concept
at all. See [interface.md](interface.md) → Bindings.

### Fan-out safety

Browser tools are tab-scoped, so parallel agents can each own a tab. The
*session* behind those tabs is not: cookies, the active tenant and sticky UI
state (grouping, sort, filters) are shared across every tab in the profile.

So fan out only over work that is **read-only and session-neutral**. Anything
that switches tenant or changes sticky state runs serially, or concurrent agents
silently read another tenant's data.

Interactive work stays a skill. An agent cannot ask the user anything, so
anything requiring confirmation — `/map-site`'s whole discovery loop — must not
become one.

## Add a workflow action

1. `schema/workflow.yaml` — the action in the `steps` comment block, with its
   semantics (what `value`, `capture`, `expect` mean for it).
2. Both skills that execute steps: `.claude/skills/run/SKILL.md` and
   `.claude/skills/test/SKILL.md`.
3. [host-bindings.md](host-bindings.md) — which capability implements it per host.
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

1. `sites/<site>/scripts/<name>` — or `projects/<project>/scripts/<name>` when the script
   serves no single site (+ a `scripts/README.md` beside it for auth
   notes and parked-code rationale).
2. Declare it in that site's `site.yaml` `scripts:` list — declaration is what
   makes it addressable from `action: script` steps.
3. Prefer `--json` output so step `capture` gets structured data.

## Add a host

1. Add a column to the tables in [host-bindings.md](host-bindings.md) with that
   host's tool names.
2. Add a pointer file at the repo root that the host reads on startup (see
   `AGENTS.md`, `CLAUDE.md`, `.cursorrules`,
   `.github/copilot-instructions.md`) — it must do nothing but point at
   `docs/AGENTS.md`.
3. If the host has its own skill/agent registry, register the files in
   `.claude/` there. Never copy instructions into a second location.
4. Verify against `sites/sitemapper-demo` — the one mapped site with no
   deployment-specific auth.

---

**Last Updated:** 2026-08-26
