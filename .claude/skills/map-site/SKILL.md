---
name: map-site
description: Start a discovery session to map a web application. Reads the current page in Chrome, suggests elements to catalog, and builds YAML page maps through conversation with the user.
disable-model-invocation: true
argument-hint: [site-name]
arguments: [site]
allowed-tools: Bash(mkdir *) Read Write Edit Glob Grep
---

Follow the instructions in `docs/skills/map-site.md`.

Site argument: $site
