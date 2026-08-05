# Verify Map

On-demand drift check for a mapped site. Verifies that mapped elements still exist on their pages.

## Steps

1. **Load site config** from `sites/<site>/site.yaml`. If not found, list available sites.

2. **For each mapped page** in `sites/<site>/pages/`:
   a. Read the page YAML to get the URL pattern and element list.
   b. **navigate** to the page.
   c. For each element, check if it still exists on the page:
      - **find** it by its mapped locator.
      - Mark as FOUND or MISSING.
   d. If the page map has a `screenshot:`, capture the current page and compare
      it against the stored reference for layout drift that element checks
      cannot see. Report visual differences alongside the element table.

   Capability names map to concrete tools in `docs/HOST_BINDINGS.md`. This work
   is read-only and independent per page, so a host that can fan out may check
   pages in parallel — the report must be identical either way.

3. **Report results** as a table:

| Page | Elements | Found | Missing |
|------|----------|-------|---------|
| ... | ... | ... | ... |

4. For any missing elements, suggest the user run `/map-site <site>` to update the affected pages.

5. Update `verified_at:` in `sites/<site>/site.yaml` with today's date.
