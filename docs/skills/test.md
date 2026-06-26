# Run Test Workflow

Execute a `mode: deterministic` test workflow and emit a structured `result`
(see `schema/result.yaml`). This is the test-oriented sibling of `/run`: instead
of just performing a task, it evaluates `assert` steps and reports PASS/FAIL.

## Steps

1. **Find the workflow** — search `sites/*/workflows/<workflow>.yaml` and
   `projects/*/workflows/<workflow>.yaml`. If not found, list available
   workflows and ask the user to choose.

2. **Load the workflow YAML** and confirm `mode: deterministic`. (An `agentic`
   workflow can still be run, but note that its judgement steps need an LLM.)

3. **Load site config(s)** from `sites/<site>/site.yaml` for `base_url`,
   `auth_notes`, and `settings`.

4. **Resolve inputs** — apply `fixtures` and any `parameters` (prompt for
   parameters not satisfied by defaults). Build a substitution map for
   `$fixture`, `$param`, and `$captured_var` references.

5. **Execute steps in order.** For each step, load the referenced
   `sites/<site>/pages/<page>.yaml`, find the element's locator, and:
   - `navigate` → `mcp__claude-in-chrome__navigate` (prefix relative `value`
     paths with the site `base_url`; substitute `$` references first)
   - `click` → `mcp__claude-in-chrome__find` + `computer` click
   - `input` → `mcp__claude-in-chrome__form_input`
   - `read` → `read_page` / `get_page_text`; store under the step's `capture`
   - `assert` → locate the element and evaluate `expect` (see below). Record one
     entry in `result.assertions` with `{ id, page, element, expect, actual,
     pass }`. **Do not abort on a failed assertion** — continue so the run
     reports every assertion.
   - `wait` → brief pause for transitions

6. **Evaluate `expect`** for `assert` steps:
   - `visible` → element present and visible
   - `absent` → element NOT present (use `find`; pass when nothing matches)
   - `enabled` / `disabled` → element present and (not) interactive
   - `{ contains: t }` / `{ equals: t }` → element text contains / equals `t`
   - `{ value: t }` → input/select current value equals `t`
   - `{ count: n }` → number of matching elements equals `n`
   - `{ url_matches: p }` → current tab URL matches pattern `p` (element is ignored)

   **Value scoping.** When an `assert` (or `click`/`read`) step has a `value`,
   scope to the descendant of `element` whose text contains `value` — e.g.
   `element: device-row, value: "Diverse Kaffee Mastrena", expect: visible`
   asserts a row containing that text exists; with `expect: absent` it asserts
   none does. This is how a test checks that a filter kept/removed a specific
   row without depending on volatile counts.

   **Clearing inputs.** Clear a search/filter field by clicking its mapped
   clear control (the X button, e.g. `device-filter-clear`) rather than typing an
   empty string - browser form-input cannot reliably submit a truly empty value.

7. **Build the result** (`schema/result.yaml`):
   - `status`: `error` if a non-assert step could not complete (element missing,
     navigation/timeout); else `failed` if any assertion failed; else `passed`.
   - Fill `captures`, `assertions`, `parameters`, `fixtures`, and `counts`.
   - Optionally capture a screenshot into `evidence` on failure/error.

8. **Return the result** as JSON and print a short PASS/FAIL summary. Do **not**
   send it anywhere — routing the result (e.g. to a DevOps page) is the calling
   host's job, not this skill's.

## Safety

- A test run may submit forms only where `settings.policy.safe_to_submit_forms`
  is true for that scope (e.g. dev). Otherwise treat submit controls as
  read-only and assert on them without clicking.
