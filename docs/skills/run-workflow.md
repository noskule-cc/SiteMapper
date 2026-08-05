# Run Workflow

Execute a named workflow from a mapped site. Reads the workflow YAML, prompts for parameters, then executes each step using the site map and Chrome browser tools.

## Steps

1. **Find the workflow** — search both `sites/*/workflows/<workflow>.yaml` and `projects/*/workflows/<workflow>.yaml` for the workflow definition. If not found, list available workflows and ask the user to choose.

2. **Load the workflow YAML** and identify:
   - Which site(s) it belongs to (check both `site` and `sites` fields)
   - Its `mode` — `deterministic` (every step is mechanical) or `agentic` (one or
     more steps need judgement, so an LLM must execute it)
   - Required `parameters` and pinned `fixtures`
   - Whether it has `setup` / `teardown` phases
   - The step sequence

   A `mode: deterministic` workflow with `assert` steps is a test — run it with
   `/test` instead, which evaluates assertions and emits a structured result.

3. **Load site config(s)** from `sites/<site>/site.yaml` for base URL and auth notes. For cross-site workflows, load all referenced sites.

4. **Collect parameters**:
   - For `type: select` parameters — present the predefined options and ask the user to choose.
   - For `type: text` parameters — ask the user to provide a value.
   - Apply defaults where available.
   - **`fixtures` are not prompted** — they are pinned data. When they are keyed
     by an environment (`fixtures.common` plus one block per environment), a
     `$name` resolves against `fixtures.<selected value>` first, then falls back
     to `fixtures.common`.

4b. **Run `setup` first** if the workflow has one — navigate, reset sticky UI
   state (grouping, sort), clear filters. Setup steps are not assertions; if one
   cannot complete, stop and report that the run could not start. Some UI state
   persists per user across sessions, so without setup a run inherits whatever
   the last one left.

5. **Execute steps** in order. For each step:
   - Determine which site this step runs on (from `step.site` or `workflow.site`)
   - Load the referenced page YAML from `sites/<site>/pages/<page>.yaml`
   - Find the referenced element and its locator
   - Perform the action using the host's capabilities (`docs/HOST_BINDINGS.md`
     maps each to a concrete tool):
     - `navigate` → **navigate** (prefix a relative `value` path with the site's
       `base_url`; substitute `$` references first)
     - `click` → **find** + **click**
     - `input` → **type**. For a text field this types `value`; for a
       select/combobox it picks the option whose text equals `value`
     - `read` → **read page** / **read text**
     - `key` → **press key** (`value` is the key, e.g. `Escape`, `Enter`) — used
       to dismiss a dropdown without changing state
     - `script` → **run script**: run the named script from
       `sites/<site>/scripts/` with `value` as its CLI arguments, and store its
       parsed stdout under `capture` (JSON when run with `--json`). Prefer this
       whenever the data is reachable from the site's API — it is faster,
       headless, and does not break when the UI changes
     - `verify` → check that expected elements/text exist on the page
     - `wait` → pause briefly for page transitions
   - Substitute parameter values where `$param_name` appears in step values
   - Substitute captured variables where `$captured_var` appears in step values
   - If step has `capture` field, store the step output in the named variable
   - Report what happened at each step

5b. **Run `teardown` last** if the workflow has one, best-effort even if a step
   failed, so a mutating run leaves the environment as it found it. A teardown
   step must locate its target by identity, never by screen position — see
   `docs/guardrails.md`.

6. **Verify outcomes** — check each item in the workflow's `verify` list.

7. **Report results** — summarize what was done and whether verification passed.
   For a run worth keeping as history, write it to
   `results/<workflow>.<YYYY-MM-DD>.md` next to the workflow (see the `results/`
   READMEs). Routine runs need not be committed.

## Cross-Site Execution

When a step switches to a different site than the previous step:
- Navigate to the new site's base URL
- Ensure authentication context is correct (check site's `auth_notes`)
- Captured variables from the previous site remain available

## Error Handling

- If an element can't be found, take a screenshot and report the issue. Don't retry blindly.
- If a page doesn't match expectations, run a quick drift check on that page's map.
- Ask the user before continuing if a step fails.
