# Project Index

Project-specific docs and situational references beyond the aiDocs standard set
(see [INDEX.md](INDEX.md)). SiteMapper is a framework with its own domain
vocabulary, so this index carries more than most projects.

## Situational References

Read these **when you reach that situation**, in addition to the standard table
in [AGENTS.md](AGENTS.md):

| When you're... | Read... |
|----------------|---------|
| Mapping a site, running a workflow, checking drift, repairing a map | the skill: `.claude/skills/<name>/SKILL.md` (registry: [skills-and-agents.md](skills-and-agents.md)) |
| Looking up which host tool does what | [host-bindings.md](host-bindings.md) |
| Being called by another system, or emitting/consuming a run result | [interface.md](interface.md) |
| Deciding what a run may do | [permissions.md](permissions.md) |
| Deciding script vs. LLM for a task | [code-over-llm.md](code-over-llm.md) |
| Deciding **where** a fact belongs — repo or agent memory | [knowledge-placement.md](knowledge-placement.md) |
| About to save something to agent memory | [knowledge-placement.md](knowledge-placement.md) **first** |
| Adding a skill, agent, workflow action, schema key, site script or host | [extending.md](extending.md) |
| Writing the standing rules a deployment follows | [guardrails-template.md](guardrails-template.md) |
| Asking what exists in the repo right now | [inventory.md](inventory.md) (generated) |
| Showing a **human** what exists | [overview.html](overview.html) (generated) — open in a browser |
| Writing a new workflow YAML | `schema/workflow.yaml` (+ a sibling `<workflow>.md` with a Mermaid flowchart) |
| Finding drift a script could catch | add a check to `scripts/check.py` |

## Key Concepts — and where each is defined

Routing, not restatement. The wiki owns behaviour and rationale; the schemas own
format; this table says which to open.

| Concept | Defined in |
|---------|-----------|
| **Site map** — YAML per page template: elements with semantic locators, gotchas, a fingerprint | `schema/page.yaml`, `schema/site.yaml` · wiki: [Site maps](https://github.com/noskule-cc/SiteMapper/wiki/concepts-site-map) |
| **Workflow** — a named step sequence with a sibling `<workflow>.md` companion | `schema/workflow.yaml` · wiki: [Workflows](https://github.com/noskule-cc/SiteMapper/wiki/concepts-workflow) |
| **Cross-site workflow** — lives in `projects/<project>/workflows/`, spans sites via capture variables | `schema/project.yaml` |
| **`mode`** — `deterministic` (runnable with no LLM) or `agentic` (needs judgement); tests should be deterministic | [interface.md](interface.md) · [code-over-llm.md](code-over-llm.md) |
| **`effect` and `trust`** — what a run does to the site, and whether it has been proven; independent axes | `schema/workflow.yaml` · [permissions.md](permissions.md) |
| **Layered settings** — `config.yaml` → `site.yaml` → page, merged most-specific-wins; `policy.permissions` gates what a run may do | `schema/settings.yaml` · [permissions.md](permissions.md) |
| **Persona and context** — who is logged in, and which tenant with which data | `schema/persona.yaml`, `schema/context.yaml` |
| **Result** — the neutral object every run emits, whoever executed it | `schema/result.yaml` · [interface.md](interface.md) |
| **Prefer a script over the browser** — `action: script` where the data is reachable from an API | [code-over-llm.md](code-over-llm.md) |
| **The repo is the source of truth; agent memory is a staging area** | [knowledge-placement.md](knowledge-placement.md) |
| **Open decisions are GitHub issues**, never files in this repo | [issue-tracker.md](issue-tracker.md) |

## Schemas

Commented YAML templates — the format's source of truth, and the comment *is*
the documentation.

| File | Defines |
|------|---------|
| `../schema/page.yaml` | page map: purpose, `url_pattern`, elements, gotchas, fingerprint |
| `../schema/site.yaml` | site config: base URL, auth notes, page/workflow/script listings |
| `../schema/workflow.yaml` | workflow: parameters, fixtures, steps, `mode`, `effect`, `trust`, `requires` |
| `../schema/project.yaml` | cross-site project |
| `../schema/settings.yaml` | layered settings: contact, policy/permissions, form defaults |
| `../schema/result.yaml` | the neutral result object a run emits |
| `../schema/persona.yaml` | who is logged in: auth method, never a credential |
| `../schema/context.yaml` | which tenant + which data fill a workflow's roles |

## Tooling

| Script | Does |
|--------|------|
| `../scripts/check.py` | all mechanical consistency checks; non-zero exit on failure |
| `../scripts/run.py` | headless deterministic workflow runner (Playwright, no LLM in the loop) |
| `../scripts/serve.py` | serves the overview live on localhost; run buttons become real, gated by [permissions.md](permissions.md) |
| `../scripts/inventory.py` | generates both views below; `--check` fails when either is stale |
| `../scripts/overview.py` | the HTML renderer, reading `inventory.py`'s collectors |

Working on these: [development.md](development.md). What to run when:
[tools/jobs.md](tools/jobs.md).

## Principles (this project's own)

**[code-over-llm.md](code-over-llm.md)** — who executes: prefer a script over an LLM

- The boundary (what genuinely needs an LLM), the agentic → deterministic ratchet
- Why this is the same lever as host-independence

**[knowledge-placement.md](knowledge-placement.md)** — where a fact belongs: repo vs. agent memory

- The per-file placement table (gotchas, site.yaml, settings, companion `.md`, issues)
- Why memory is the weaker home

## Contract and operation

**[interface.md](interface.md)** — how a host invokes SiteMapper and consumes its results

- The three verbs, the two host kinds, who executes a workflow's steps
- Bindings: instructions live in `.claude/`, tool names only in `host-bindings.md`

**[host-bindings.md](host-bindings.md)** — capability → tool mapping per host

**[permissions.md](permissions.md)** — what a run may do: action classes × allow/ask/deny

- Enforcement rules, the `ask` channel per host, dashboard deploy gating

**[extending.md](extending.md)** — how to add a skill, agent, workflow action, schema key, site script or host

- Fan-out safety; why every SiteMapper skill is slash-only

**[guardrails-template.md](guardrails-template.md)** — how to write the standing rules a
deployment follows. The rules themselves are deployment-specific and live with
that deployment's own maps (`data/docs/guardrails.md` is the starter), never here.

## Generated views

**[inventory.md](inventory.md)** — every site, project and workflow. Generated by
`scripts/inventory.py`; never hand-edited.

**[overview.html](overview.html)** — the same estate, browsable, with run
commands and trust/effect badges. Generated by `scripts/overview.py`; served
live by `scripts/serve.py`.

## Product docs at the repo root

**[../USAGE.md](../USAGE.md)** — setup, mapping sites, writing workflows, running them

**[../PRD.md](../PRD.md)** — product requirements · **[../Concept.md](../Concept.md)** — original design rationale

**[../config.yaml](../config.yaml)** — global settings: environment + permission defaults

**[../data/](../data/)** — copyable skeleton for your own private map repository
(README, `config.yaml` to fill in, a guardrails starter, a `.gitignore` that
excludes run outputs as a class, and its own `/deploy-dashboard` wrapper)

## Standard docs this project declined

Not stubs, decisions. `check-docs.py` reports links to them as warnings, and
`scripts/check.py` as notes — that is the gap reading as a decision.

| Declined | Why |
|----------|-----|
| `installation.md` | Setup is two `pip install` lines; it lives in [../USAGE.md](../USAGE.md) with the rest of getting started. A separate page would duplicate it. |
| `testing.md` | There is no unit-test suite. The repo's test surface is `scripts/check.py`, `docs/tools/check-docs.py` and the CI runner smoke test — all registered as jobs in [tools/jobs.md](tools/jobs.md). `/test` runs UI test workflows against mapped sites and is documented in its own skill. |
| `release.md` | Nothing is released. There are no tags, no packages and no GitHub releases; the dashboard artifact deploys itself on push (see [tools/jobs.md](tools/jobs.md)). |
| `changelog.md` | No release history to keep. Closed issues plus `git log` are the record. |
| `design-sync.md` | No design files. The one rendered surface, `overview.html`, is generated from code. |

**Maintain this index:** list project docs here as they are added — never edit
`INDEX.md` or `AGENTS.md`.
