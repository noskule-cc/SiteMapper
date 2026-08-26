---
name: documentation
description: Documentation writing following Information Minimalism. Use when creating or updating docs.
argument-hint: ""
---

Follow these rules when writing or updating documentation.

## Before Writing

Run the 3-question Information Minimalism test (`docs/INFORMATION_MINIMALISM.md`):

1. Does the reader need this? (No → don't write it)
2. Is it already documented elsewhere? (Yes → reference, don't duplicate)
3. Will it go stale? (Yes → put it closer to the code)

## Placement Rules

| Content type | Location |
|-------------|----------|
| Intent, rationale, edge cases | Code comments / docstrings |
| Developer operations, platform guides | `docs/` |
| How software functions, domain concepts | Wiki |

## When Writing New Docs

1. Apply the 3-question test
2. Determine correct location using placement rules
3. Write the content
4. Update the relevant index (INDEX.md, [platform]-index.md, or wiki sidebar)
5. Add `**Last Updated:** YYYY-MM-DD` at the bottom

## When Updating Existing Docs

1. Read existing content first
2. Make targeted changes — don't rewrite surrounding text
3. Update the Last Updated date
4. Check if index entries still match

## Full reference

`docs/DOCUMENTATION_GUIDELINES.md`
