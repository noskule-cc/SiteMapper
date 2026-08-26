# Coding Guidelines

Scope: Applies to all changes in this repository — Python, schemas, maps and docs.

> **Companion skill:** `.claude/skills/coding-workflow/SKILL.md` auto-triggers when a development task starts and tracks progress through the steps below.

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/descriptive-name
```

Never commit directly to `main`.

### 2. Implement Code

- Read [architecture-rules.md](architecture-rules.md) first — the Reuse Rules
  tables say where the loader, resolver, policy gate and collectors already live.
- Keep changes focused and atomic; flag problematic patterns in existing code to
  the user rather than silently working around them.

**Ask before proceeding when:**

- There is an architecture decision, or several valid approaches
- Requirements are unclear or ambiguous
- The change breaks a contract (`schema/*.yaml`, the `result` object, the three
  verbs in [interface.md](interface.md)) or adds a dependency
- A permission, trust or guardrail rule would have to bend to make it work —
  that is the signal to stop, not the workaround

### 3. Write Tests

There is no unit-test suite (see [project-index.md](project-index.md) for why).
Coverage here means **mechanical checks and a real run**:

- A new class of drift → a check in `scripts/check.py` that exits non-zero
- A new schema key → the commented template entry, which *is* the check
- A runner or workflow change → a real headless run of the acceptance workflow
- Documentation-only changes → no tests

### 4. Run the Checks

```bash
python scripts/check.py            # eight consistency checks
python docs/tools/check-docs.py    # doc structure
python scripts/run.py search-issues --json   # the acceptance run, if the runner changed
```

Registry of everything runnable: [tools/jobs.md](tools/jobs.md).

### 5. Report to User for Review

State what was implemented, what the checks reported, what to try by hand, and
the expected behaviour.

### 6. User Manually Tests and Reviews

The user's step — stop and wait.

### 7. Capture Technical Discoveries

Run the placement table in [knowledge-placement.md](knowledge-placement.md).
A discovery about a *site* becomes a page gotcha; about the *framework*, a wiki
page or a doc here; about *your machine*, agent memory and nowhere else.

### 8. Write Documentation

Per [DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md) and the
3-question test. Update the wiki when behaviour changed
([wiki.md](wiki.md)); regenerate the views if the estate changed
(`python scripts/inventory.py`).

### 8.5 Run Maintenance (diff-scoped)

`/maintain change` — dispatches only the checks the branch diff triggers
(registry: [tools/jobs.md](tools/jobs.md)). Fix what it reports before creating
the PR. This is the workflow's single maintenance reference; individual checks
are never listed here.

### 9. Create Pull Request

```bash
gh pr create --title "Descriptive title" --body "$(cat <<'EOF'
## Summary
- [What was implemented]
- [Key changes]

## Verification
- [Checks run and their results]

## Documentation
- [Docs / wiki updated]

-- Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 10. User Merges PR

The user reviews and merges, then says "PR merged, continue".

## Python Conventions

- **Standard library first.** `scripts/serve.py` is stdlib-only on purpose, and
  the framework as a whole needs only PyYAML; Playwright is required by the
  headless runner alone. A new third-party dependency needs a reason in the PR.
- **Comment the *why*.** Every check in `check.py` exists because the thing it
  catches actually happened — the docstring says which. Keep that habit.
- **Two roots.** Anything that walks a tree must respect `--root`: schemas and
  instructions come from the framework, data from the checked tree. See
  [architecture-rules.md](architecture-rules.md).

## Data and Secrets

A credential never enters the repository — not in a map, not in a persona, not
in a saved browser state (`.runner/state/` is gitignored). Identity values are
referenced by key from layered `settings:` and resolved from private config.
Standing rules for a deployment live in its own `docs/guardrails.md`; how to
write them is [guardrails-template.md](guardrails-template.md).

**Last Updated:** 2026-08-26
