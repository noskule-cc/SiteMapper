# Run Workflow

Execute a named workflow from a mapped site. Reads the workflow YAML, prompts for parameters, then executes each step using the site map and Chrome browser tools.

## Steps

1. **Find the workflow** — search `sites/*/workflows/<workflow>.yaml` for the workflow definition. If not found, list available workflows and ask the user to choose.

2. **Load the workflow YAML** and identify:
   - Which site(s) it belongs to (check both `site` and `sites` fields)
   - Required parameters
   - The step sequence

3. **Load site config(s)** from `sites/<site>/site.yaml` for base URL and auth notes. For cross-site workflows, load all referenced sites.

4. **Collect parameters**:
   - For `type: select` parameters — present the predefined options and ask the user to choose.
   - For `type: text` parameters — ask the user to provide a value.
   - Apply defaults where available.

5. **Execute steps** in order. For each step:
   - Determine which site this step runs on (from `step.site` or `workflow.site`)
   - Load the referenced page YAML from `sites/<site>/pages/<page>.yaml`
   - Find the referenced element and its locator
   - Perform the action using Chrome MCP tools:
     - `navigate` → `mcp__claude-in-chrome__navigate`
     - `click` → `mcp__claude-in-chrome__computer` with action "click" or `mcp__claude-in-chrome__find` + click
     - `input` → `mcp__claude-in-chrome__form_input`
     - `read` → `mcp__claude-in-chrome__read_page` or `mcp__claude-in-chrome__get_page_text`
     - `verify` → check that expected elements/text exist on the page
     - `wait` → pause briefly for page transitions
   - Substitute parameter values where `$param_name` appears in step values
   - Substitute captured variables where `$captured_var` appears in step values
   - If step has `capture` field, store the step output in the named variable
   - Report what happened at each step

6. **Verify outcomes** — check each item in the workflow's `verify` list.

7. **Report results** — summarize what was done and whether verification passed.

## Cross-Site Execution

When a step switches to a different site than the previous step:
- Navigate to the new site's base URL
- Ensure authentication context is correct (check site's `auth_notes`)
- Captured variables from the previous site remain available

## Error Handling

- If an element can't be found, take a screenshot and report the issue. Don't retry blindly.
- If a page doesn't match expectations, run a quick drift check on that page's map.
- Ask the user before continuing if a step fails.
