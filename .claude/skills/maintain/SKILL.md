---
name: maintain
description: Dispatch maintenance jobs from the jobs registry. Use "/maintain change" before creating a PR (diff-scoped checks) and "/maintain full" at the project's cycle-end event (sprint end, milestone close, or pre-release).
argument-hint: "change | full"
---

Dispatch maintenance from the jobs registry — `docs/tools/jobs.md`, falling back to `docs/tools/jobs.template.md` in the standard repo. **Never hardcode the job list**: the registry is the single source of truth for what exists and when it fires; new maintenance elements are added there, not here. If no registry exists, say so and stop.

Report one consolidated result at the end: which jobs ran, which were skipped and why, and failures with their output. No silent skips.

## Scope: change (default from the coding workflow)

Diff-scoped, cheap, deterministic. Never run cycle-end jobs here.

1. Determine the branch diff: `git diff --name-only <default-branch>...HEAD`, plus uncommitted changes
2. From the registry, take the jobs with trigger class **per-change** whose "Runs when" condition matches the diff
3. Run them and collect results

## Scope: full (cycle-end)

The incremental battery. Invoked at the project's cycle-end event (see the Cycle-End Binding in the registry) or before a release — never per task.

1. Read the last-run stamp `docs/.maintain-last-run`; if missing, treat everything as changed (first adoption and pre-release get the full battery)
2. Compute what changed since the stamp: `git diff --name-only <stamp-commit>..HEAD`
3. From the registry, take the jobs with trigger class **cycle-end**; run each only if its inputs changed since the stamp — otherwise skip it with an explicit "inputs unchanged" line
4. Also run everything scope `change` would run, against the same range
5. When every job that ran succeeded, write the stamp:

   ```text
   commit: <current HEAD sha>
   updated: YYYY-MM-DD
   ```

6. On an unchanged repo, run nothing and say so

## Rules

- Costs stay proportional to churn: never expand scope beyond what the diff or stamp range triggers
- Never write the stamp when a job failed
- Full-repo, everything-on runs are reserved for first adoption and pre-release
