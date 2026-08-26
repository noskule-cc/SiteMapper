---
name: verify-map
description: Background drift check of a mapped site — every element gets FOUND/MISSING/UNREACHABLE, fingerprints checked, one consolidated report, zero edits
tools: Read, Glob, Grep, ToolSearch
---

# verify-map

Runs the drift check of `.claude/skills/verify-map/SKILL.md` as a fanned-out,
self-contained task — one agent per site (or per page set), reporting back a
single consolidated drift report.

## Purpose

`/verify-map` is interactive and serial; a deployment with many sites and
dozens of mapped pages wants the same check as a background sweep. This agent
is that execution strategy — **the behavior is defined entirely by the skill**;
this wrapper adds only isolation and the report contract, never new behavior
(an agent is an execution strategy, not part of the contract — see
`docs/interface.md` → Bindings).

## Before Starting

Read `.claude/skills/verify-map/SKILL.md` — it defines the loop. Browser
access: load the host's browser tools via ToolSearch as `docs/host-bindings.md`
maps them.

## Responsibilities

- Execute the verification loop from the skill for the site(s) it is given
- Verify page fingerprints with the same vocabulary the runner uses
  (`ok | mismatch`), so repair has one input format
- Return one consolidated report; propose nothing beyond it

## Rules

- **Read-only against the site and the repo.** No map edits — repairs are the
  repair skill's job, applied after a human picks them. (A `tools:` allowlist
  is this requirement in host syntax.)
- Fan out only over read-only, session-neutral work — see "Fan-out safety" in
  `docs/extending.md`; sites behind tenant switching are checked serially.
- Every element gets a verdict; an element the agent could not reach is
  `UNREACHABLE (why)`, never silently skipped.

## Output format

```markdown
## Drift report — <site> (<date>)
- pages checked: N · elements: FOUND n / MISSING n / UNREACHABLE n
- fingerprints: ok n / mismatch n

### <page>
| element | verdict | note |
|---|---|---|
```

## Checklist

- [ ] Skill read; site map loaded
- [ ] Every mapped element visited, verdict recorded
- [ ] Fingerprints checked where defined
- [ ] Report returned; zero files modified

## Related

- Skill: `.claude/skills/verify-map/SKILL.md` · Repair:
  `.claude/skills/repair/SKILL.md`
