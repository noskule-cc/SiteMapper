# Verify Map

On-demand drift check for a mapped site. Verifies that mapped elements still exist on their pages.

## Steps

1. **Load site config** from `sites/<site>/site.yaml`. If not found, list available sites.

2. **For each mapped page** in `sites/<site>/pages/`:
   a. Read the page YAML to get the URL pattern and element list.
   b. Navigate to the page using `mcp__claude-in-chrome__navigate`.
   c. For each element, check if it still exists on the page:
      - Use `mcp__claude-in-chrome__find` with the element's locator.
      - Mark as FOUND or MISSING.

3. **Report results** as a table:

| Page | Elements | Found | Missing |
|------|----------|-------|---------|
| ... | ... | ... | ... |

4. For any missing elements, suggest the user run `/map-site <site>` to update the affected pages.

5. Update `sites/<site>/site.yaml` with the verification timestamp.
