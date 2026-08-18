# List Workflows

Show what workflows exist, across all sites and projects or for one site.

## Steps

1. **Refresh the inventory** — run `python scripts/inventory.py`. It walks every
   `sites/*/workflows/*.yaml` and `projects/*/workflows/*.yaml` and regenerates
   `docs/inventory.md`. It is fast, deterministic, and costs no tokens.

2. **Read `docs/inventory.md`** and present its Workflows table.

3. **If a site was named**, filter to rows whose owner is that site, plus any
   project workflow whose `Sites` column includes it — a cross-site workflow is
   relevant to every site it touches, not just the project that owns it.

4. **If nothing matches**, say so and suggest `/map-site <site>` to map a site
   first, or point at an existing site from the Sites table.

## Why this reads a generated file

Enumerating workflows is mechanical, so parsing 14 YAML files with an LLM every
time someone asks what exists is the wrong executor — see
`docs/CODE_OVER_LLM.md`. The script is the source of the answer; this skill
presents it.

Do not hand-edit `docs/inventory.md`. `python scripts/inventory.py --check`
fails when it is stale, which is what stops the generated copy from drifting
away from the YAML.

## Worth reporting

The inventory exposes gaps that are easy to miss when reading files one at a
time. Mention them if they show up:

- a workflow with **no `mode`** — a runner cannot tell whether it needs an LLM
- a workflow with **no companion `.md`** (`Doc` column shows `—`), which
  `USAGE.md` and `schema/workflow.yaml` both require
- a site whose `Verified` column is empty or long stale → suggest `/verify-map`
