# List Workflows

List all available workflows across all mapped sites, or for a specific site.

## Steps

1. If a site name is provided, look in `sites/<site>/workflows/`. Otherwise, search all `sites/*/workflows/`.
2. Read each workflow YAML file found.
3. Present a table:

| Site | Workflow | Description |
|------|----------|-------------|
| ... | ... | ... |

4. If no workflows are found, suggest running `/map-site` first to map a site, then defining workflows.
