---
name: update-aidocs
description: Update this project's aiDocs standard files from the upstream aiDocs repository. Use when the user asks to update aiDocs or pull the latest standard.
argument-hint: "[git ref, default: upstream main HEAD]"
---

Pull upstream changes of the aiDocs standard into this project without touching anything the project owns.

## Ownership Contract

Only shipped paths participate at all: `docs/`, `.claude/`, and the root wrapper templates (`AGENTS.md.template`, `CLAUDE.md.template`, `.cursorrules.template`, `.github/copilot-instructions.md.template`). Everything else in the upstream repo is repo-only (its own `README.md`, `AGENTS.md`, CI config, lint config) — never copy it.

Every shipped file classifies into exactly one of:

| Class | Files | On update |
|-------|-------|-----------|
| **Upstream-owned** | UPPERCASE `.md` in `docs/` (incl. `README.md`), `*.template.md` / `*.template`, upstream-shipped files under `.claude/` | apply changes |
| **Project-owned** | Filled template copies (`coding-guidelines.md`, `issue-tracker.md`, `wiki.md`, `skills-and-agents.md`, `tools/jobs.md`, ...), `docs/project-index.md`, project's own docs/skills/agents, `docs/.aidocs-version` | never touch |

**Shipped-active skills** (e.g. `documentation`, `validate-docs`) are upstream-owned, but projects may customize them (platform wording, extra rules). That's allowed — the 3-way check below turns upstream changes to a customized skill into a conflict for manual merge instead of an overwrite.

## Procedure

1. **Read the stamp** — `docs/.aidocs-version` holds the adopted upstream commit and source URL:

   ```text
   commit: <full sha>
   source: https://github.com/noskule/aiDocs
   updated: YYYY-MM-DD
   ```

2. **No stamp? Reconstruct the baseline with the blob-history probe.** For each shipped file in the project, hash it EOL-normalized and search upstream history for that exact content:

   ```bash
   h=$(sed 's/\r$//' <file> | git hash-object --stdin)
   git log --all --find-object=$h --format="%h %ad" --date=short   # run in the upstream clone
   ```

   A match ⇒ the file is an unmodified old upstream version (safe to auto-update). No match ⇒ locally modified or project-own. This replaces guessing; after the run, write the stamp so the fallback is never needed again.

3. **Fetch upstream** — clone the source into a temp dir (full history, needed for diffs and the probe). Old ref = stamp commit; new ref = `$ARGUMENTS` or upstream main HEAD.

4. **Apply the migration map first** (pre-2026-08 adopters). These upstream renames must be treated as lineage, not delete+add:

   | Legacy name in project | Becomes |
   |------------------------|---------|
   | `docs/CODING_GUIDELINES.md` | rename to `docs/coding-guidelines.md` — it IS the filled copy (project-owned); template added alongside |
   | `docs/SUBAGENTS.md` | replaced by `docs/CREATING_AGENTS.md` |
   | `docs/subagents/VALIDATION.md` + `.claude/agents/validation.md` | split into `.claude/agents/validation-docs.md` + `validation-llm.md` (full-bodied) |
   | `docs/tools/JOBS.md` | rename to `docs/tools/jobs.md` — filled copy; template added alongside |
   | `docs/issue-tracker.md`, `docs/wiki.md` (pre-template era) | already the filled copies — keep as-is; templates added alongside |
   | `docs/subagents/<name>.md` + thin `.claude/agents/<name>.md` wrapper | merge into one full-bodied `.claude/agents/<name>.md` (wrapper frontmatter + doc body) — applies to the project's own agents too |
   | `docs/subagents/index.md` | becomes the filled `docs/skills-and-agents.md` (project-owned registry; links point into `.claude/`) |
   | `docs/subagents/README.md` | replaced by `docs/CREATING_AGENTS.md` |
   | root `CODEX.md` | superseded by root `AGENTS.md` (agents.md spec — read natively by Codex, Cursor and others) |
   | `docs/tools/jobs.md` without trigger classes (pre-2026-08 format) | rebuild in the trigger-class format from `docs/tools/jobs.template.md` (per-change / cycle-end column, Cycle-End Binding), preserving the project's own jobs — confirm with user. Not a mere drift notice: `/maintain` cannot dispatch without this format |
   | filled `docs/README.md` (project-identity page) | replaced by the fixed standard `README.md` (generic orientation routing) — identity lives in the root README, wiki location in `wiki.md`; port anything unique to those homes first, confirm with user |

5. **Compute the delta** — `git diff --name-status <old>..<new>` in the clone. Classify each path by the ownership contract.

6. **Apply, with 3-way safety** — for each upstream-owned change, compare the project copy against the OLD upstream version **ignoring line endings and trailing whitespace** (`diff --strip-trailing-cr -Z`); formatting-only drift is not a conflict:
   - Project copy matches old upstream → apply silently (copy new file / delete removed file)
   - Project copy genuinely differs → **conflict**: show both diffs (their local change, the upstream change), ask before touching
   - File doesn't exist locally → add it, **except**: never add a `*.template.md` / `*.template` whose filled equivalent exists (templates are instantiate-and-delete; drift is diffed from the upstream clone), and never re-add a file the project deliberately deleted (check the project's git history when unsure)
   - **`.claude/` is strictly additive**: never overwrite an existing file that differs — always confirm first

7. **Notify on template drift** — when a `*.template.md` changed upstream and the project has a filled copy, don't touch the copy; report the template's upstream old→new diff (from the clone — the template is not present in the project) so the user can port relevant changes manually.

8. **Verify** — run `python docs/tools/check-docs.py`; fix errors the update introduced before proceeding.

9. **Stamp and report** — write the new commit to `docs/.aidocs-version`, then summarize: updated / added / deleted / skipped (project-owned) / conflicts / template-drift notices. Recommend `/maintain full` — it surfaces the judgment-level drift (stale filled copies, unported template changes) that the update deliberately cannot touch.

## Rules

- Never modify project-owned files, ever — not even formatting
- Deletions are proposals, not actions: confirm each one
- If the ownership class of a file is ambiguous, treat it as project-owned and report it
