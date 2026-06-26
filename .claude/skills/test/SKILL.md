---
name: test
description: Run a deterministic UI test workflow against its mapped site and emit a structured result (per-assertion PASS/FAIL + overall status). Reads the workflow YAML, executes navigate/click/input/read/assert steps via the site map and Chrome browser tools.
disable-model-invocation: true
argument-hint: [workflow-name]
arguments: [workflow]
allowed-tools: Read Glob Grep
---

Follow the instructions in `docs/skills/test.md`.

Workflow argument: $workflow
