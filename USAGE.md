# Usage Guide

**Host-agnostic by design.** The instructions behind every command live in
`docs/skills/*.md` in terms of capabilities, not tool names; the slash
commands below are one host's *bindings* of them (`docs/INTERFACE.md`). On a
host without slash commands, read the skill doc and follow it directly —
`docs/HOST_BINDINGS.md` maps capabilities to concrete tools per host.
Deterministic workflows additionally need no agent host at all — see
"Running headless" below.

## Setup

For LLM-driven sessions, two things run side by side:

- **An agent host** (e.g. Claude Code — CLI, desktop, or web) — reads/writes site maps from this repo, runs skills and workflows
- **A browser the agent can drive** (e.g. Chrome + the Claude-in-Chrome extension) — DOM reading, clicking, form input, navigation

You type commands in the agent host; it controls the browser. The site maps live on your file system, not in the browser.

The headless runner needs only Python + PyYAML + Playwright (`pip install playwright` — it drives your installed Chrome, no browser download).

To begin, tell Claude to open a Chrome browser session (it creates its own tab via the MCP extension) and navigate to your target URL — you don't open the tab by hand. Make sure Chrome and the Claude-in-Chrome extension are running first, and that you're logged in to the target site if it requires auth (Claude won't enter credentials for you).

## Mapping a Site

1. In Claude Code, run `/map-site <site-name>` (e.g., `/map-site sitemapper-demo`).
2. Tell Claude to open a Chrome browser session and navigate to the target URL (Claude opens its own tab through the MCP extension — you don't open it by hand).
3. The discovery agent reads the page, suggests elements, and asks you to confirm or correct.
4. Walk through each page — the agent writes YAML maps as you go.
5. When done, the agent updates `sites/<site>/site.yaml` with the full page list.

The output is a directory under `sites/`:

```
sites/<site-name>/
  site.yaml           # Base URL, auth notes, list of pages and workflows
  pages/
    dashboard.yaml     # One file per page
    settings.yaml
  workflows/
    my-task.yaml       # Site-specific workflows
```

## Writing Workflows

### Site Workflows (single site)

Place in `sites/<site>/workflows/`. A workflow defines a sequence of steps against one mapped site:

```yaml
workflow:
  name: smart-issue
  description: Create a new issue with a smart title
  site: sitemapper-demo

  parameters:
    - name: issue_title
      type: text
      description: Title for the new issue
      required: true

  steps:
    - action: click
      page: issues-list
      element: new-issue-button
      description: Open new issue form

    - action: input
      page: new-issue
      element: title-field
      value: "$issue_title"
      description: Enter issue title

  verify:
    - "Issue created successfully"
```

### The keys that matter beyond name/steps

All defined, with their semantics, in `schema/workflow.yaml` — the schema
comments are the reference; this is the orientation:

- **`mode`** — `deterministic` (every step mechanical; can run headless) or
  `agentic` (a step needs judgement; needs an LLM).
- **`effect`** — `read-only | mutating | destructive`, declared. Checked up
  front against the environment's permission policy (`docs/PERMISSIONS.md`).
- **`trust` / `verified_at`** — lifecycle for headless runs: `draft` until a
  green run is reviewed, `verified` after, `broken` automatically on
  failure or fingerprint drift.
- **`parameters`** vs. **`fixtures`** — caller-supplied (prompted) vs. pinned
  test data; fixtures can be environment-keyed with a `common:` fallback.
- **`setup` / `teardown`** — force a known state before, restore it after
  (best-effort even on failure). What makes a test hermetic.
- **`assert` steps** — checkable expectations (`visible`, `absent`,
  `{contains}`, `{count}`, `{url_matches}`, …) that feed the result's
  assertion list. Prefer them over prose `verify:` bullets.
- **`action: script`** — call a site script (declared in `site.yaml`
  `scripts:`) instead of driving the browser; prefer it whenever the data is
  reachable from an API (`docs/CODE_OVER_LLM.md`).
- **`action: key`** — press a keyboard key (e.g. `Enter` to submit a search).

### Project Workflows (cross-site)

Place in `projects/<project>/workflows/`. A project groups workflows that span multiple sites:

```
projects/<project-name>/
  project.yaml         # Which sites, description
  workflows/
    my-workflow.yaml
```

**project.yaml:**

```yaml
project:
  name: Issue Tracking
  description: Manage issues using the demo issue tracker
  sites: [sitemapper-demo]
  workflows:
    - smart-issue.yaml
```

**Workflow with capture variables:**

```yaml
workflow:
  name: smart-issue
  description: Read existing issues and create a related follow-up
  site: sitemapper-demo

  steps:
    - action: read
      page: issues-list
      element: issues-table
      capture: open_issues
      description: Read current open issues

    - action: input
      page: new-issue
      element: description-field
      value: "Follow-up for: $open_issues"
      description: Create follow-up issue with captured data

  verify:
    - "Issue created with reference to existing issues"
```

The `capture` field stores a step's output in a named variable. Later steps reference it with `$variable_name`.

### Companion doc (`<workflow>.md`)

Every workflow YAML gets a sibling `<workflow>.md` in the same folder — a short,
human-readable summary so anyone can grasp the flow without reading the YAML. The
YAML stays the source of truth; the `.md` is the at-a-glance view. Keep it tight:

- **Title** (the workflow name) and a one-line purpose.
- **At a glance** — site(s), mode, key inputs (parameters/fixtures) → outputs (captures).
- **Flow** — a **Mermaid `flowchart`** of the steps (setup → steps → report). Group
  by site with `subgraph` for cross-site workflows; show loops and branches.
- **See also** — relative links to the `.yaml` and the latest result file.

Example: [`sites/sitemapper-demo/workflows/smart-issue.md`](sites/sitemapper-demo/workflows/smart-issue.md).

Skeleton (outer fence shown with `~~~` so the inner Mermaid fence is literal):

~~~markdown
# my-workflow

One-line purpose.

**At a glance** — Site: my-site · Mode: deterministic · In: $param → Out: capture_x

## Flow
```mermaid
flowchart TD
  A["Open page"] --> B["Do the thing"] --> C["Assert result"]
```
~~~

## Running Workflows

```
/run <workflow-name>          # any workflow, in an LLM session
/test <workflow-name>         # deterministic test workflows: evaluates asserts, emits a result
```

Both search `sites/*/workflows/` and `projects/*/workflows/`, collect
parameters (dropdown for select, prompt for text), execute the steps through
the host's browser tools, and report a `result` (`schema/result.yaml`).

### Running headless (no LLM)

```
python scripts/run.py <workflow> [--param key=value] [--record] [--root <maps>]
python scripts/serve.py [--root <maps>]     # the dashboard with real run buttons
```

`run.py` executes `mode: deterministic` workflows with no LLM in the loop —
auto-waiting browser automation, the full assert grammar, `--json` for a
machine-readable result with a structured failure report, `--record` to write
the `results/` record. Permission-gated up front; `--root` points at your map
repository. Test workflows run this way in CI on every push.

### Results

A run worth keeping is recorded as `results/<workflow>.<YYYY-MM-DD>.md`
beside the workflow's own directory (`sites/<site>/results/` or
`projects/<project>/results/`). Which runs are worth committing — and which
are noise — is `docs/MAINTENANCE.md` → Results retention.

## Listing Workflows

```
/list-workflows              # all workflows
/list-workflows sitemapper-demo   # site-specific only
```

## Checking for Drift

```
/verify-map <site-name>
```

Navigates to each mapped page and checks whether elements still exist. Reports found/missing per page.

## Map Format

Maps use semantic locators in order of preference:

1. `data-testid` — most stable (add to your app if you control it)
2. `aria-label` — accessibility attributes
3. `text` — visible text content
4. `role` — ARIA roles
5. `css` — last resort

Each page YAML also captures **gotchas** — non-obvious behavior that would trip up automation (e.g., "sidebar collapses after navigation", "two clicks needed to reach machine list").
