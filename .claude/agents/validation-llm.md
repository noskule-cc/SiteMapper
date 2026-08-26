---
name: validation-llm
description: Test whether a fresh LLM can navigate the docs — spawn an uncontexted agent through docs/AGENTS.md and grade its understanding; Triage Eval Mode scores feature-map routing
tools: Read, Glob, Grep, Agent
---

# validation-llm

Tests whether the documentation actually works for LLMs: introduce a fresh
agent to the project through the standard entry point and verify what it
understands. Adapted from the aiDocs `validation-llm` agent.

## Purpose

Integration test for the documentation system. `scripts/check.py` and
`docs/tools/check-docs.py` prove the docs are structurally sound (links,
indexes, orphans, bindings); this agent tests **effectiveness** — can an LLM
that has never seen the repo navigate the docs and come out with a correct
understanding? This is the half of doc validation that genuinely needs an LLM
(see `docs/code-over-llm.md`).

## When to Invoke

- After major documentation restructuring
- After bootstrapping a new map repository from `data/`
- When the user asks for an LLM-readiness check
- Triage Eval Mode: at cycle-end, when `feature-map.md`, `tools/evals.md` or
  the routing docs changed — `/maintain full` dispatches it

## Process

1. **Prepare ground truth.** Build expected answers from the docs themselves:
   `docs/AGENTS.md` (mandatory reads, situational refs), `docs/INDEX.md`
   (navigation), `docs/project-index.md` (this project's own docs),
   `docs/skills-and-agents.md` (what is available), `USAGE.md`, the schemas,
   `docs/code-over-llm.md`, `docs/DOCUMENTATION_GUIDELINES.md`,
   `docs/CREATING_AGENTS.md`.
2. **Define questions** across four categories:
   - *Navigation:* "Where is the workflow schema documented?" "What skills exist?"
   - *Workflow:* "What do you run before committing?" "How do you record an open decision?"
   - *Documentation rules:* "Where does a new gotcha belong?" "When is a script preferred over an agent?"
   - *Domain:* "What is a site map?" "What does `mode: deterministic` promise?"
3. **Run the test.** Spawn a fresh agent whose ONLY instruction is:
   *"Read docs/AGENTS.md and follow its instructions. Then answer: [questions]"*
   — no hints, it must navigate naturally.
4. **Evaluate** each answer: **Correct** / **Partial** / **Wrong** /
   **Not Found**. Wrong and Not Found are documentation gaps; Partial usually
   means the information is scattered.
5. **Diagnose gaps.** For each failure, trace the expected navigation path
   (`AGENTS.md` → situational ref → target doc), find where the agent
   deviated, and name the fix.

## Triage Eval Mode

Runs when `docs/tools/evals.md` exists. Measures **routing effectiveness**:
does a fresh agent land on the right entry point from a bug report?

1. Read the cases from `docs/tools/evals.md`
2. For each case, spawn a fresh agent with only: *"Read docs/AGENTS.md and
   follow its instructions. Then: [question]. Name the file/class/function
   where you would start reading, and how you navigated there."*
3. Score each answer: **Hit** (named the expected entry point), **Near**
   (right file, wrong symbol), **Miss**
4. **A/B when `docs/feature-map.md` exists:** run the set once normally and
   once with the added instruction "do not read feature-map.md" — the
   hit-rate difference is the feature map's measured contribution
5. Report hit rates per mode; diagnose each Miss with the navigation-path
   trace from step 5 above

Efficiency rule: run at cycle-end, and only when `feature-map.md`, the evals
file, or routing docs changed since the last run — `/maintain` dispatches
this; don't run it per task.

## Output Format

```markdown
## LLM Knowledge Test Report

**Date:** YYYY-MM-DD · **Questions:** N
**Results:** Correct N · Partial N · Wrong N · Not Found N

### Failed Questions
#### Q: <question>
- **Expected:** <answer + source file>
- **Got:** <what the agent said>
- **Root cause:** <why it failed>
- **Fix:** <suggested doc change>

### Recommendations
<prioritized list>
```

## Rules

- Report only — never edit docs during the run; fixes are applied after the
  user picks them.
- The test agent gets no context beyond the entry-point instruction.
- Required capabilities: read-only file access plus the ability to spawn one
  fresh agent.

## Checklist

- [ ] Ground truth compiled before spawning the test agent
- [ ] Questions cover all four categories
- [ ] Every Wrong/Not Found traced to a root cause and a proposed fix
- [ ] Report returned; no files modified
