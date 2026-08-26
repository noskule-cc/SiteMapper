---
name: coding-workflow
description: Tracks the 10-step development workflow when implementing features or making code changes. Auto-triggers when a development task starts.
user-invocable: false
---

Track the development workflow for every code change. The step details live in `docs/coding-guidelines.md` — read it first; this skill only enforces progress through it.

## Step Tracking

When a development task starts, create a task for each step using your task system:

1. Create feature branch
2. Implement code
3. Write tests
4. Run tests
5. Report to user for review
6. User manually tests and reviews
7. Capture technical discoveries
8. Write documentation
8.5 Run maintenance (`/maintain change`, diff-scoped)
9. Create pull request
10. User merges PR

## Rules

- Announce step transitions briefly ("Step 4: running tests")
- Not every step applies to every change — mark inapplicable steps completed immediately, stating why (e.g. docs-only change → no tests)
- Before advancing, check prior steps are completed or explicitly marked not applicable; if one was skipped silently, ask the user before proceeding
- Steps 6 and 10 are the user's — stop and wait, don't perform them

## Full reference

`docs/coding-guidelines.md` — what each step involves, when to ask the user before proceeding, PR format

> No project-specific configuration needed — activate by renaming to `SKILL.md`.
