---
name: setup
description: Interview-form initial setup of aiDocs in a project. Use after copying the aiDocs docs/ and .claude/ folders into a new project, or when the user asks to set up / initialize aiDocs.
argument-hint: ""
---

Guide the user through the complete initial setup of aiDocs in this project. Work as an **interview**: ask one question at a time, apply each answer before moving on, and show a short summary of what you changed at the end.

## Step 0 — Preflight

Check what already exists and skip questions that are already answered:

- `docs/` copied? Git repo? GitHub remote?
- Which `*.template.md` files are still unfilled (placeholders like `[Your Project Name]`, `[Platform]`)?
- Which `.claude/skills/*/SKILL.md.template` files are not yet activated?

## Step 1 — Interview

Ask in this order (skip what preflight already answered):

1. **Project** — name and one-sentence description
2. **Platform / tech stack** — language, framework, build tool, test runner
3. **AI tools in use** — Claude Code, Copilot, Cursor, Codex? (decides which root wrapper templates to activate: `CLAUDE.md.template`, `copilot-instructions.md.template`, `.cursorrules.template`, `CODEX.md.template`)
4. **Wiki** — GitHub Wiki, docs folder, external (Confluence/Notion), or none
5. **Issue tracking** — GitHub Issues with Projects v2 board, plain issues, or none
6. **Testing** — test categories and commands (feeds `testing.md` and the test-runner skill)
7. **Feature map** — is the codebase organized by feature folders (feature→code mapping obvious from structure → decline) or by layers (instantiate `feature-map`, see `docs/feature-map.template.md`)?
8. **Cycle-end event** — which real event triggers full maintenance (`/maintain full`): sprint end, milestone close, or pre-release? (fills the Cycle-End Binding in `tools/jobs.md`)

## Step 2 — Apply

For each answer, make the corresponding change:

- Ensure the root `README.md` states the project name and description — the fixed `docs/README.md` routes humans there
- Instantiate templates by **renaming** them (drop the `.template` suffix): `coding-guidelines`, `architecture-rules`, `development`, `changelog`, `issue-tracker`, `wiki`, `skills-and-agents`, `tools/jobs`, plus `feature-map` and `tools/evals` when the user opted in — the template file must not remain next to its filled copy (the template lives upstream; `/update-aidocs` reports drift from there). Create `installation.md`, `testing.md`, `release.md` with real content where the user provided it, otherwise minimal TODO stubs. Delete shipped templates the project declines (e.g. `design-sync.template.md` when not using Pencil, `feature-map.template.md` and `tools/evals.template.md` when structure already reveals the mapping)
- Fill the instantiated `docs/wiki.md` with the chosen wiki location, or instantiate it with a "no wiki" note
- Fill the Cycle-End Binding in the instantiated `docs/tools/jobs.md` with the chosen event
- If using a Projects v2 board: fill the IDs section in `.claude/agents/issue-writer.md` (discover via `gh api graphql`); if plain issues: note that in the instantiated `docs/issue-tracker.md`
- Activate the chosen root wrapper templates (rename, point them at `docs/AGENTS.md`)
- Rename applicable `.claude/skills/*/SKILL.md.template` to `SKILL.md` and fill project specifics (test commands, architecture rules)
- Update the instantiated `docs/skills-and-agents.md` (and `docs/project-index.md` if extra docs exist) to match what actually exists now — `INDEX.md` itself is a fixed standard file
- Write the version stamp `docs/.aidocs-version` recording the adopted upstream commit:

  ```text
  commit: <full sha of the aiDocs commit these files came from>
  source: https://github.com/noskule/aiDocs
  updated: YYYY-MM-DD
  ```

  This is what `/update-aidocs` later diffs against.

## Step 3 — Validate

1. Run `/validate-docs` and fix what it reports
2. Recommend running the `validation-llm` agent to verify a fresh LLM can navigate the result
3. Summarize: files created, files filled, open TODOs

## Rules

- **Installs are additive** — when copying into an existing project (especially `.claude/`), never overwrite a file that already exists; report the collision and let the user decide
- Never overwrite content the user already customized — ask first
- Apply Information Minimalism (`docs/INFORMATION_MINIMALISM.md`) to everything you generate: stubs stay stubs until there is real content
- UPPERCASE files are the fixed standard — do not edit them during setup
