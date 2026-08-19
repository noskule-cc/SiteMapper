# INDEX.md — Documentation Map

UPPERCASE = framework files, kept as-is across projects.
lowercase = this project's own content.

## Entry Point

- [AGENTS.md](AGENTS.md) — start here (situational references, available skills)
- [GUARDRAILS.template.md](GUARDRAILS.template.md) — how to write the standing rules a deployment follows
- [../data/](../data/) — copyable skeleton for your own private map repository

## Getting Started

- [USAGE.md](../USAGE.md) — how to map sites, write workflows, run them
- [config.yaml](../config.yaml) — global settings (contact, default policy)

## Product

- [PRD.md](../PRD.md) — product requirements
- [Concept.md](../Concept.md) — original design rationale
- [INTERFACE.md](INTERFACE.md) — how a host invokes SiteMapper and consumes its results; the bindings model
- [HOST_BINDINGS.md](HOST_BINDINGS.md) — capability → tool mapping per host

## Skills and Sub-Agents

- [subagents/README.md](subagents/README.md) — skills vs. sub-agents; how to add one
- [subagents/workflow-companion.md](subagents/workflow-companion.md) — writes a workflow's companion `.md`
- [subagents/validation-llm.md](subagents/validation-llm.md) — tests the docs on a fresh LLM
- [map-site.md](skills/map-site.md) — discovery session for mapping a site
- [run-workflow.md](skills/run-workflow.md) — execute a named workflow
- [test.md](skills/test.md) — execute a deterministic test workflow, emit a result
- [list-workflows.md](skills/list-workflows.md) — list available workflows
- [verify-map.md](skills/verify-map.md) — drift check for mapped sites
- [repair.md](skills/repair.md) — fix the map after a headless runner failure

## Schemas

- [page.yaml](../schema/page.yaml) — page map format
- [site.yaml](../schema/site.yaml) — site configuration format
- [workflow.yaml](../schema/workflow.yaml) — workflow definition format
- [project.yaml](../schema/project.yaml) — cross-site project format
- [settings.yaml](../schema/settings.yaml) — layered settings (contact, policy, form defaults)
- [result.yaml](../schema/result.yaml) — the neutral result object a run emits

## Tooling

- [scripts/check.py](../scripts/check.py) — all mechanical consistency checks; non-zero exit on failure
- [scripts/run.py](../scripts/run.py) — headless deterministic workflow runner (Playwright, no LLM in the loop)
- [scripts/inventory.py](../scripts/inventory.py) — generate both views below; `--check` fails when either is stale
- [scripts/overview.py](../scripts/overview.py) — the HTML renderer, reading `inventory.py`'s collectors
- [inventory.md](inventory.md) — **generated**: every site, project and workflow
- [overview.html](overview.html) — **generated**: the same, browsable — open it in a browser

## Guidelines

- [INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) — whether to document at all
- [KNOWLEDGE_PLACEMENT.md](KNOWLEDGE_PLACEMENT.md) — where a fact belongs: repo vs. agent memory
- [DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md) — which level it goes on: artifact, `docs/`, or wiki
- [CODE_OVER_LLM.md](CODE_OVER_LLM.md) — who executes: prefer a script over an LLM
- [PERMISSIONS.md](PERMISSIONS.md) — what a run may do: action classes × allow/ask/deny
- [JOBS.md](JOBS.md) — registry of runnable maintenance jobs
- [wiki.md](wiki.md) — where the wiki lives; how SiteMapper *functions* is documented there
- a deployment's own `docs/guardrails.md` lives with its maps, in its own repository — never here
- [issue-tracker.md](issue-tracker.md) — issue conventions; where open decisions live

## Proposals

Proposals and open decisions live in **GitHub Issues**, not in this repo — see
[issue-tracker.md](issue-tracker.md) for the conventions.
