# Documentation Index

Quick navigation to all docs. Read only what you need, when you need it.


## LLM Entry Point

**[AGENTS.md](AGENTS.md)** - Start here

- Mandatory reading order (with reading-order diagram)
- Situational References
- Skills and Agents (full listing: [skills-and-agents.md](skills-and-agents.md), template: `skills-and-agents.template.md`)

**[README.md](README.md)** - Human entry point: orientation routing table (fixed; identity lives in the root README, wiki location in `wiki.md`)


## Development Process

**[coding-guidelines.md](coding-guidelines.md)** - Development workflow (template: `coding-guidelines.template.md`)

- Development Workflow (10 steps)
- Data Persistence

**[DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md)** - What/where to document

- Information Minimalism Test
- Documentation Levels (Code, /docs, Wiki)
- Doc-System Layer Model (content axes, layers, verification diagram)
- Diagrams (Mermaid conventions, when to use, placement)
- Documenting in Code
- Documenting in /docs (File Tree)
- Documenting in Wiki


## Reference

**[CREATING_AGENTS.md](CREATING_AGENTS.md)** - Creating specialized AI skills and agents

- Skills vs. Agents
- Agent File Format
- Creating and registering

**[INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md)** - 3-question test

- The Test (3 questions)
- Examples
- When to Document


## Design

**[design-sync.md](design-sync.md)** - Bidirectional design ↔ code sync (template: `design-sync.template.md`)

- File Map (Pencil frames → source files)
- Token Translation Tables (colors, typography, shapes)
- Component Mapping (frame → UI element parameters)
- Sync Rules (design→code, code→design, tokens)


## Tools

**[tools/jobs.md](tools/jobs.md)** - Runnable jobs registry (template: `tools/jobs.template.md`)

- Available jobs with commands and trigger classes (per-change / cycle-end)
- Cycle-end binding; `/maintain` dispatches from this table

**[tools/evals.md](tools/evals.md)** - Triage eval cases (template: `tools/evals.template.md`)

- Bug-report-phrased questions with expected entry points; run by `validation-llm`


## Platform Specific

**[installation.md](installation.md)** - First time setup

**[architecture-rules.md](architecture-rules.md)** - Enforceable design principles

- Layer Boundaries, Reuse Rules, Anti-Patterns, Extension Points

**[development.md](development.md)** - Writing code

- Tech Stack, Architecture, Code Patterns, File Organization
- Data Retention, Build Commands, Common Tasks

**[feature-map.md](feature-map.md)** - Feature → code routing for triage (template: `feature-map.template.md`)

- Per feature: entry point, gotchas, failure-mode hints; behavior links to the wiki

**[testing.md](testing.md)** - Running/writing tests

**[release.md](release.md)** - Publishing


## Project Management

**[issue-tracker.md](issue-tracker.md)** - GitHub Issues and Projects v2 (template: `issue-tracker.template.md`)

- Conventions (types, labels, sub-issues, project, estimates)
- Issue Structure (required sections per type)
- Wiki Mapping

**[changelog.md](changelog.md)** - Release history → GitHub Releases (template: `changelog.template.md`)


## Wiki (External)

**[wiki.md](wiki.md)** - Wiki location and access (template: `wiki.template.md`)

**Wiki** - What software does

- Fundamentals (domain concepts)
- Architecture (system design)
- Features (user-facing functionality)
- Devices (hardware-specific findings)


## Project-Specific Additions

**[project-index.md](project-index.md)** - Docs beyond the standard set (create when needed)


**This index is a fixed standard file — do not edit.** It covers the standard docs by their standardized names. List additional project docs in `project-index.md`; skills and agents belong in `skills-and-agents.md`.
