# AGENTS.md — SiteMapper LLM Entry Point

## Mandatory Reading

- [docs/INDEX.md](INDEX.md) — navigation map of all documentation

## Situational References

| When you're...                          | Read...                                  |
|-----------------------------------------|------------------------------------------|
| Mapping a new site                      | `docs/skills/map-site.md`               |
| Running a workflow                      | `docs/skills/run-workflow.md`           |
| Listing available workflows             | `docs/skills/list-workflows.md`         |
| Checking a map for drift                | `docs/skills/verify-map.md`             |
| Writing a new workflow YAML             | `schema/workflow.yaml`                  |
| Creating a cross-site project           | `schema/project.yaml`                   |
| Configuring contact/behavior/defaults   | `schema/settings.yaml`, `config.yaml`   |
| Understanding the project               | `PRD.md`                                |
| Writing or updating documentation       | `docs/INFORMATION_MINIMALISM.md`        |
| Validating YAML before commit           | `scripts/lint.py`                       |

## Available Skills

| Skill            | Trigger           | Purpose                                    |
|------------------|-------------------|--------------------------------------------|
| map-site         | `/map-site`       | Start a discovery session for a site       |
| run              | `/run`            | Execute a named workflow                   |
| list-workflows   | `/list-workflows` | Show available workflows                   |
| verify-map       | `/verify-map`     | On-demand drift check for a mapped site    |

## Key Concepts

- **Site maps** are YAML files in `sites/<site-name>/pages/` describing page elements and gotchas.
- **Workflows** are YAML files in `sites/<site-name>/workflows/` defining step sequences.
- **Cross-site workflows** live in `projects/<project>/workflows/` and span multiple sites using capture variables.
- **Schemas** in `schema/` define the YAML format for pages, sites, workflows, projects, and settings.
- **Settings** are layered (`config.yaml` global → `site.yaml` → page YAML), merged most-specific-wins; `policy.safe_to_submit_forms` gates form submission.
- **Claude Code orchestrates** via file system access + Chrome MCP browser tools.
