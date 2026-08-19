# validation-llm

Tests whether the documentation actually works for LLMs: introduce a fresh
agent to the project through the standard entry point and verify what it
understands. Adapted from the aiDocs `VALIDATION_LLM` agent.

## Purpose

Integration test for the documentation system. `scripts/check.py` proves the
docs are structurally sound (links, indexes, orphans); this agent tests
**effectiveness** — can an LLM that has never seen the repo navigate the docs
and come out with a correct understanding? This is the half of doc validation
that genuinely needs an LLM (see `CODE_OVER_LLM.md`).

## When to Invoke

- After major documentation restructuring
- After bootstrapping a new map repository from `data/`
- When the user asks for an LLM-readiness check

## Process

1. **Prepare ground truth.** Build expected answers from the docs themselves:
   `AGENTS.md` (workflow, skills, situational refs), `INDEX.md` (navigation),
   `USAGE.md`, the schemas, `CODE_OVER_LLM.md`, `DOCUMENTATION_GUIDELINES.md`,
   `subagents/README.md`.
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
