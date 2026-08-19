# Documentation Guidelines

Where documentation lives and how each level is written. Adopted from the
aiDocs framework.

**Whether** to write something down at all is
[INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) (the 3-question test).
**Where a fact belongs** — repo vs. the host agent's memory — is
[KNOWLEDGE_PLACEMENT.md](KNOWLEDGE_PLACEMENT.md). This doc covers the levels
above that: which *kind* of place a piece of documentation goes, and the
conventions for each.

## Documentation Levels

| Location | Contains | Examples |
|----------|----------|----------|
| **In the artifact** (YAML comments, `gotchas`, `description` fields) | Intent, rationale, non-obvious behavior — read where the work happens | page `gotchas`, schema template comments, workflow step `description` |
| **`docs/` folder** | Operating the framework: skills, principles, interface, host bindings | `skills/*.md`, `CODE_OVER_LLM.md`, `INTERFACE.md` |
| **Wiki** | How SiteMapper *functions* (user perspective), architecture, domain concepts | features, the three-role architecture, the trust model |

The dividing line for the wiki: it documents how the software **functions**,
not how the framework is **operated**. "What is a site map and why does a
verified one make runs fast" is wiki; "how to run `/verify-map`" is `docs/`.

## `docs/` Folder Conventions

- **UPPERCASE** — framework files, portable across projects (`AGENTS.md`,
  `CODE_OVER_LLM.md`, this file). **lowercase** — this project's own content
  (`inventory.md`, `wiki.md`). Casing marks provenance and is load-bearing —
  see the header of [INDEX.md](INDEX.md).
- Before writing: check `INDEX.md` to avoid duplication. After writing: update
  the index. `scripts/check.py` fails on orphans and broken links.
- Framework docs carry a `**Last Updated:**` footer.

## Wiki Conventions

Location, access, and the authoritative pillar/prefix structure:
[wiki.md](wiki.md). In short: two pillars — **Content** (`concepts-`,
`features-`) and **Architecture** (`architecture-`) — and every file is named
`<prefix>-<topic>.md`.

**Index:** `_Sidebar.md` is the wiki's navigation, grouped by the two pillars.
Before writing a page, check it; after writing, update it.

### Structure: behavior first, then host

Wiki pages separate **what the feature does** (host- and deployment-agnostic)
from **how it is bound** (host- or deployment-specific):

```markdown
# Drift Detection

## What It Does
A mapped page carries a fingerprint. Every run verifies it in passing;
a mismatch degrades the page's trust and flags it for repair.

## Why It Matters
Maps rot silently. Verification as a side effect of normal work means
staleness is discovered the day it happens, not the day it breaks a run.

## Bindings
- LLM session: `/verify-map` (see docs/skills/verify-map.md)
- Headless runner: fingerprint check before each page interaction
```

If someone reads only "What It Does" and "Why It Matters", they have
everything needed to implement the behavior on any host.

Host-specific tool names never appear in wiki prose — they live in
[HOST_BINDINGS.md](HOST_BINDINGS.md), which the wiki may link.

### The wiki is public

The repo and its wiki are public. The guardrails apply: nothing
deployment-specific ever goes in — no customer names, identifiers, hostnames
or fleet data. Deployment documentation lives in that deployment's own private
map repository (`data/` skeleton).

## Diagrams

Use [Mermaid](https://mermaid.js.org/) fenced code blocks — GitHub renders
them natively in repo markdown and wiki pages. Apply the 3-question test to
diagrams too.

| Mermaid type | Use for |
|---|---|
| `flowchart` | Decision logic, workflow steps (the companion-doc convention) |
| `stateDiagram-v2` | Lifecycle — e.g. trust: draft → verified → broken |
| `sequenceDiagram` | Component interactions over time |

- Brief caption sentence before each diagram
- Keep under ~15 nodes — split or simplify if larger

## Periodic Validation

- **Structural** (links, orphans, index consistency): `scripts/check.py` —
  mechanical checks run in code, per [CODE_OVER_LLM.md](CODE_OVER_LLM.md).
- **Effectiveness** (can a fresh LLM navigate the docs?): the
  [validation-llm](subagents/validation-llm.md) sub-agent — after major
  restructuring or new project setup. This genuinely needs an LLM.

---

**Last Updated:** 2026-08-19
