# SiteMapper

Before starting any task, read `docs/AGENTS.md` for situational guidance on which docs and skills to use.

## Azure DevOps (`ado` MCP) access guardrails

The `ado` MCP server authenticates as the user (full identity), so these limits are a
**behavioral rule every session must follow** — they are not, and cannot be, enforced by
the MCP server or Claude Code permissions (both are global, not per-project). Hard
enforcement requires Azure DevOps-side permissions or a scoped PAT.

- **GGplus Anleitungen** (`d04b7d15-f740-4269-8b29-cb70ba3d8c25`): full access, all tools.
- **GGplus** (`76635751-9628-423b-85eb-33acb0404796`): **WIKI ONLY** — only `wiki_*` /
  `search_wiki`. Never repos, pipelines, work items, test plans, or any non-wiki write.
- **All other projects** (GGplus Order, Opten Libraries, GehrigGroup Connect, …): no
  access unless the user explicitly authorizes it that session.

Before any `ado` call, check the target project against these rules.
