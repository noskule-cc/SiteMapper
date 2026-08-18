# workflow-companion

Write the sibling `<workflow>.md` for a workflow YAML — the at-a-glance view a
human reads instead of the YAML.

## Purpose

`USAGE.md`, `schema/workflow.yaml` and `AGENTS.md` all require every workflow
YAML to have a companion `.md` with a Mermaid flowchart. Producing one is
self-contained: read one YAML, write one Markdown file. Nothing else in the repo
is touched, so several can run at once.

## Responsibilities

- Read exactly one workflow YAML.
- Write exactly one `.md` beside it, same basename.
- Change nothing else. Never edit the YAML — if the workflow looks wrong, say so
  in the return value and leave it alone.

## Required capabilities

Read and write files, scoped to the target workflow's folder. **No browser, no
network, no shell.** If a host grants this agent more than that, the extra
capability is unused.

## Output format

```markdown
# <workflow-name>

<one-line purpose, lifted from the YAML description>

**At a glance** — Site(s): `a`, `b` · Mode: deterministic · In: $param, $fixture → Out: capture_x

## Flow
```mermaid
flowchart TD
  A["Open page"] --> B["Do the thing"] --> C["Assert result"]
```

## See also
- [`<workflow>.yaml`](<workflow>.yaml)
- latest result, if one exists
```

## Rules that make the diagram worth having

- **Draw the shape, not the transcript.** A 51-step workflow does not become 51
  boxes. Group consecutive steps into the phase they accomplish ("fill the four
  wizard steps"), and show the branch/loop structure, which is the part the YAML
  hides.
- **`setup` and `teardown` are phases**, not footnotes — show them, since they
  are where hermeticity and cleanup live.
- **Group cross-site workflows with `subgraph` per site.** Which site a step runs
  on is the thing a reader most needs and the YAML expresses least clearly.
- **Show branches and loops** — `$environment` selecting fixtures, a `verify`
  step that decides, per-item iteration.
- **Node ids must be word characters only.** Hyphens in Mermaid ids break the
  diagram; use `A`, `B1`, `step_2`.
- **Quote every label**: `A["Text"]`. Labels with `(`, `:` or `/` break unquoted.

## Do not

- Restate every step in prose. The YAML is the source of truth; this is the map.
- Invent behaviour the YAML does not describe. If a step is unclear, describe
  what it does and flag the ambiguity in your return value.
- Copy gotchas out of page maps. Link the page instead — see
  `KNOWLEDGE_PLACEMENT.md`.

## Checklist

- [ ] Filename matches the YAML basename exactly
- [ ] Mode and site(s) match the YAML
- [ ] Parameters, fixtures and captures named as the YAML names them
- [ ] Mermaid fence present, ids are word-chars, labels quoted
- [ ] `See also` links resolve relative to the file

## Return value

The path written, plus anything noticed about the workflow that a human should
act on (a missing `mode`, a step referencing a page that does not exist, an
unreachable branch). Do not fix those — report them.
