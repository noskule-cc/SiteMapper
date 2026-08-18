---
name: run
description: Execute a named workflow from a mapped site. Reads the workflow YAML, prompts for parameters, then executes each step using the site map and Chrome browser tools.
disable-model-invocation: true
argument-hint: [workflow-name]
arguments: [workflow]
allowed-tools: Read Glob Grep
---

Follow the instructions in `docs/skills/run-workflow.md`.

Workflow argument: $workflow
