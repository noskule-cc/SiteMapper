---
name: test
description: Run a deterministic UI test workflow against its mapped site and emit a structured result (per-assertion PASS/FAIL + overall status). Reads the workflow YAML, executes navigate/click/input/read/assert steps via the site map and the host's browser capabilities.
disable-model-invocation: true
argument-hint: [workflow-name]
arguments: [workflow]
allowed-tools: Read Glob Grep
---

# Run Test Workflow

Execute a `mode: deterministic` test workflow and emit a structured `result`
(see `schema/result.yaml`). This is the test-oriented sibling of `/run`: instead
of just performing a task, it evaluates `assert` steps and reports PASS/FAIL.

Workflow argument: $workflow

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

4b. **Run `setup` first.** Execute the `setup` steps to put the page into a
   known state (navigate, reset sticky grouping/sort, clear filters) before any
   assertion. Setup steps are not assertions — if one cannot complete, stop and
   return `result.status = error` (the test could not start). This is essential:
   grouping and sort persist per user across sessions, so without setup a run
   inherits whatever state a previous session left.

5. **Execute steps in order.** For each step, load the referenced
   `sites/<site>/pages/<page>.yaml`, find the element's locator, and use the
   host's capabilities (`docs/host-bindings.md` maps each to a concrete tool):
   - `navigate` → **navigate** (prefix relative `value`
     paths with the site `base_url`; substitute `$` references first)
   - `click` → **find** + **click**
   - `input` → **type**
   - `read` → **read page** / **read text**; store under the step's `capture`.
     With `row` and `column`, read one table cell: the header matching
     `column` by text gives the position, counting hidden header cells, and the
     one body row containing `row` gives the cell. Zero or several such rows,
     or no single matching header, fail the step
   - `key` → **press key** (`value` is the key, e.g. `Escape`) — dismisses a
     dropdown without changing state
   - `script` → **run script** declared by the step's site, this workflow's
     project or the site's app (in that order), `value` carrying its CLI
     arguments and `capture` storing its parsed stdout. Preferred over driving
     the browser wherever the data is reachable from the site's API. A step
     with a `shape` checks the output against it (`schema/workflow.yaml`); a
     mismatch is drift: record `scripts.<capture>: mismatch` and stop the run
   - `assert` → locate the element and evaluate `expect` (see below). Record one
     entry in `result.assertions` with `{ id, page, element, expect, actual,
     pass }`. **Do not abort on a failed assertion** — continue so the run
     reports every assertion.
   - `wait` → brief pause for transitions
   - `human` → **hand to a person**: stop here. If every assertion so far
     passed, the result is `status: waiting` with `waiting_for: {step, label,
     reason}` (`step` is the 1-based position across `setup`, `snapshot` and
     `steps`, `label` the step's `description`), and `teardown` is skipped. If
     an assertion already failed, the result is `failed` and `teardown` runs

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
   `element: issue-row, value: "Broken link in README", expect: visible`
   asserts a row containing that text exists; with `expect: absent` it asserts
   none does. This is how a test checks that a filter kept or removed a specific
   row without depending on volatile counts.

   **Clearing inputs.** Clear a search/filter field by clicking its mapped
   clear control (the X button, e.g. `search-clear`) rather than typing an
   empty string — browser form-input cannot reliably submit a truly empty value.

6b. **Run `teardown` last.** After the `steps` (whether they passed or failed),
   execute the `teardown` steps to restore anything the test mutated (uncheck a
   toggle, delete a created record). Run these best-effort even on failure so a
   mutating test leaves the environment clean; note any teardown step that could
   not complete in the result.

7. **Build the result** (`schema/result.yaml`):
   - `status`: `error` if a non-assert step could not complete (element missing,
     navigation/timeout); else `failed` if any assertion failed; else `waiting`
     if the run stopped at a `human` step; else `passed`.
   - Fill `captures`, `assertions`, `parameters`, `fixtures`, and `counts`.
   - Optionally capture a screenshot into `evidence` on failure/error.

8. **Return the result** as JSON and print a short PASS/FAIL summary. Do **not**
   send it anywhere — routing the result (e.g. to a tracker page) is the calling
   host's job, not this skill's.

9. **Record a reference run.** For a run worth keeping as history, write a run
   folder to the runs store (`schema/run.yaml`:
   `runs/SiteMapper/<owner>/<workflow>.<timestamp>.<tier>.<instance>.<suffix>/`): `run.yaml`,
   `result.json` with the per-assertion results, findings, and the evidence
   (screenshots, logs) under `evidence/`, referenced from the result's
   `evidence` list. Never inside the tree: nothing a run wrote is committed, and
   `check.py` fails a `results/` folder. The folder lives one day unless the
   project's `keep:` says longer; a wiki page that cites the run is what keeps
   it (`docs/tools/jobs.md` → Runs retention).

## Safety

- A test run may submit forms only where the scope's policy allows the `write`
  class (`settings.policy.permissions.write: allow` — or the legacy
  `safe_to_submit_forms: true`; see `docs/permissions.md`). Otherwise treat
  submit controls as read-only and assert on them without clicking.
