# INDEX.md — Documentation Map

UPPERCASE = framework files, kept as-is across projects.
lowercase = this project's own content.

## Entry Point

- [AGENTS.md](AGENTS.md) — start here (situational references, available skills)
- [guardrails.md](guardrails.md) — standing rules every session follows

## Getting Started

- [USAGE.md](../USAGE.md) — how to map sites, write workflows, run them
- [config.yaml](../config.yaml) — global settings (contact, default policy)

## Product

- [PRD.md](../PRD.md) — product requirements
- [Concept.md](../Concept.md) — original design rationale
- [INTERFACE.md](INTERFACE.md) — how a host invokes SiteMapper and consumes its results; the bindings model
- [HOST_BINDINGS.md](HOST_BINDINGS.md) — capability → tool mapping per host

## Skills

- [map-site.md](skills/map-site.md) — discovery session for mapping a site
- [run-workflow.md](skills/run-workflow.md) — execute a named workflow
- [test.md](skills/test.md) — execute a deterministic test workflow, emit a result
- [list-workflows.md](skills/list-workflows.md) — list available workflows
- [verify-map.md](skills/verify-map.md) — drift check for mapped sites

## Schemas

- [page.yaml](../schema/page.yaml) — page map format
- [site.yaml](../schema/site.yaml) — site configuration format
- [workflow.yaml](../schema/workflow.yaml) — workflow definition format
- [project.yaml](../schema/project.yaml) — cross-site project format
- [settings.yaml](../schema/settings.yaml) — layered settings (contact, policy, form defaults)
- [result.yaml](../schema/result.yaml) — the neutral result object a run emits

## Tooling

- [scripts/lint.py](../scripts/lint.py) — validate all repo YAML parses

## Guidelines

- [INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) — when and what to document
- [KNOWLEDGE_PLACEMENT.md](KNOWLEDGE_PLACEMENT.md) — where a fact belongs: repo vs. agent memory
- [GUARDRAILS.template.md](GUARDRAILS.template.md) — framework template behind `guardrails.md`
- [issue-tracker.md](issue-tracker.md) — issue conventions; where open decisions live

## Proposals

Proposals and open decisions live in **GitHub Issues**, not in this repo — see
[issue-tracker.md](issue-tracker.md) for the conventions.
