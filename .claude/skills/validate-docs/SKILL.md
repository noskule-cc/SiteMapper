---
name: validate-docs
description: Validates documentation structure and consistency across docs/ and wiki/.
argument-hint: "[scope: docs|wiki|both]"
context: fork
agent: general-purpose
---

You are validating documentation quality. Follow these steps:

1. **Run** `python docs/tools/check-docs.py` — the mechanical half (links, orphans, index consistency, wrapper bindings, template hygiene). Report its errors and warnings; don't re-check what it covers.
2. **Read** `.claude/agents/validation-docs.md` for the judgment half's detailed instructions
3. **Determine scope:** validate `docs/`, `wiki/`, or both (check $ARGUMENTS, default to `docs/`)
4. **Run the judgment checklist:**
   - Duplicate content detection
   - Content staleness (claims vs. reality, unreviewed drift)
   - Wiki behavior-first structure check
   - File length and focus
5. **Output** a report: mechanical results + judgment findings with issues to fix
6. **Ask** the user: fix now, save report, or create GitHub issues?
