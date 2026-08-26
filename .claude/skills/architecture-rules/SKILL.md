---
name: architecture-rules
description: Enforces architecture principles when implementing features or writing new code. Prevents code duplication and layer violations.
user-invocable: false
---

## Before Writing Code

1. **Read** `docs/architecture-rules.md`
2. **Search before implementing** — check the Reuse Rules tables for the existing loader, resolver, policy gate, collector or check. If the function you need exists, use it.
3. **Verify layer boundaries** — schema comments only; data references keys; scripts return a `result` and never route it; skills and agents name capabilities, never host tools
4. **Check extension points** — adding a skill, agent, workflow action, schema key, site script or host follows the pattern in `docs/extending.md`, ending in a registration step `scripts/check.py` enforces
5. **Check anti-patterns** — review the anti-patterns table to avoid common mistakes
6. **Never hard-code a deployment fact** — tenant names, hostnames, contacts and identifiers are referenced by key from layered `settings:`, never written into a map, a skill or a doc

## After Completing Your Task

Spawn a background subagent to scan for architecture violations. Use the **Task tool** with these exact parameters:

- `subagent_type`: `Explore`
- `run_in_background`: `true`
- `prompt`: (include the file list and instructions below)

```
Review these files for architecture rule violations against docs/architecture-rules.md:
[list the files you read/modified]

For each file, check:
- Layer boundary violations (wrong imports across layers)
- Deployment-specific values (tenant names, hostnames, contacts) written in instead of referenced by key
- Duplicated logic that exists in the Reuse Rules table
- Anti-patterns from the anti-patterns table

Output a concise violation report. Group by severity:
- **Must fix** — active violations that cause bugs or inconsistency
- **Should fix** — technical debt worth addressing
- **Note** — minor style issues

If no violations found, report "No violations detected."
```
