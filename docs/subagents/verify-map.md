# verify-map

Runs the drift check of `docs/skills/verify-map.md` as a fanned-out,
self-contained task — one agent per site (or per page set), reporting back a
single consolidated drift report.

## Purpose

`/verify-map` is interactive and serial; a deployment with many sites and
dozens of mapped pages wants the same check as a background sweep. This agent
is that execution strategy — **the behavior is defined entirely by the skill
doc**; this wrapper adds only isolation and the report contract, never new
behavior (`subagents/README.md`: an agent is an execution strategy, not part
of the contract).

## Responsibilities

- Execute the verification loop from `docs/skills/verify-map.md` for the
  site(s) it is given
- Verify page fingerprints with the same vocabulary the runner uses
  (`ok | mismatch`), so repair has one input format
- Return one consolidated report; propose nothing beyond it

## Rules

- **Read-only against the site and the repo.** No map edits — repairs are the
  repair skill's job, applied after a human picks them. (A `tools:` allowlist
  is this requirement in host syntax.)
- Fan out only over read-only, session-neutral work — see the fan-out safety
  section of `subagents/README.md`; sites behind tenant switching are checked
  serially.
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

- [ ] Skill doc read; site map loaded
- [ ] Every mapped element visited, verdict recorded
- [ ] Fingerprints checked where defined
- [ ] Report returned; zero files modified
