# PRD: SiteMapper

## Problem

LLM browser agents re-explore the same web applications from scratch every session. Each interaction starts with redundant DOM discovery, screenshot-heavy navigation, and re-learning of page layouts, elements, and task flows. There is no persistent, structured memory of how a site works.

## Solution

A collaborative site-mapping system where Claude and a human walk through a web application together, producing a versioned, reloadable map of pages, elements, flows, and gotchas. The map is stored as YAML and reference screenshots, committed to a git repo, and reused across sessions.

### Two Operating Modes

**Workflow Mode** — Named, predefined sequences that execute against the saved map.
- Example: "check for login change requests" triggers a defined series of steps: navigate to issues, filter by tag, review results, report back.
- Parameters are presented as dropdown selections when options are predefined, or the LLM prompts interactively for open-ended inputs.
- Triggered via command (e.g., `/run check-login-issues`).

**Manual Mode** — User describes what to do in natural language or uses ad-hoc commands. Claude uses the loaded site map to navigate efficiently without re-discovering the DOM.

## Discovery Phase

1. User opens the target site in Chrome alongside Claude chat.
2. User invokes `/map-site`.
3. The discovery agent reads the current page DOM and takes a reference screenshot.
4. Agent suggests elements and actions to catalog.
5. User confirms, corrects, or removes suggestions.
6. Agent asks targeted questions about gotchas, edge cases, and non-obvious behavior.
7. Process repeats page by page until the site is mapped.
8. Output is committed to the repo.

## Storage Structure

```
sites/
  issue-tracker/
    site.yaml                  # base URL, auth notes, site-level config
    screenshots/               # reference screenshots per page
      dashboard.png
      issues-list.png
    pages/
      dashboard.yaml
      issues-list.yaml
      issue-detail.yaml
    workflows/
      check-login-issues.yaml
      move-to-folder.yaml
  iot-portal/
    site.yaml
    screenshots/
    pages/
    workflows/
```

## Map Format (per page YAML)

Each page file captures:
- Page purpose and URL pattern
- Key elements with semantic locators (text, aria-label, role, `data-testid`)
- Gotchas and non-obvious behavior (e.g., "Save button stays active when form is invalid", "Delete is soft-delete only")
- Reference screenshot path

## Workflow Format (per workflow YAML)

Each workflow file defines:
- Name and description
- Trigger command
- Ordered steps referencing page elements from the map
- Parameters — with predefined options (dropdown) or free-text (LLM prompts the user)
- Expected outcomes and verification checks

## Skills & Commands

### General-purpose (all sites)

| Command | Description |
|---------|-------------|
| `/map-site` | Start a discovery session for the current site |
| `/verify-map` | On-demand drift check for the loaded map |
| `/run <workflow>` | Execute a named workflow |
| `/list-workflows` | Show available workflows for the current site |

### Site-specific

Defined in each site's `workflows/` folder. Loaded when the user activates a site context.

## Screenshots

- Captured during discovery as reference artifacts.
- Used by the LLM for visual drift detection (compare saved screenshot vs. current page).
- Provide layout context that YAML alone cannot capture.

## Drift & Verification

- On-demand only (no automatic checks).
- Triggered via `/verify-map` or implicitly when a workflow step fails to find an expected element.
- Element-existence checks against saved locators.
- Screenshot comparison for visual changes.

## Locator Strategy

- Prefer semantic anchors: text content, `aria-label`, `role`, `data-testid`.
- Avoid brittle CSS selectors and XPath.
- Since the user has admin access to target sites, adding `data-testid` attributes is the gold standard for stability.

## Pilot Targets

- **Issue tracker** — ticket management, filtering, tagging, replying.
- **IoT portal** — device and user management.
- Both are admin-controlled internal tools with stable DOM and the ability to add `data-testid` attributes.

## MVP Scope

1. Define YAML schema for pages and workflows (separate task).
2. Build discovery skill (`/map-site`) as a Claude Code skill/subagent.
3. Build workflow runner (`/run`) with dropdown parameter selection.
4. Map one pilot site (issue-tracker) end-to-end.
5. Capture reference screenshots during discovery.

## Cross-Site Workflows

Workflows can span multiple mapped sites. For example: read device status from the IoT portal, then create a ticket in an issue tracker with the results.

### How It Works

- The `sites` field lists all sites involved in the workflow.
- Each step has a `site` field indicating which site it runs on.
- The `capture` field on a step stores its output in a named variable.
- Captured variables are referenced as `$variable_name` in subsequent steps, even across sites.

### Data Passing

Steps can capture data using the `capture` field:
```yaml
- action: read
  site: iot-portal
  page: admin-gateway-monitoring
  element: gateway-table
  capture: offline_devices

- action: input
  site: issue-tracker
  page: new-issue
  element: description-field
  value: "Offline devices: $offline_devices"
```

The workflow runner holds captured variables in memory and substitutes them into step values. For select-type parameters, options are presented as dropdowns; for captured data, the LLM formats it appropriately for the target field.

## Architecture

Claude Code is the orchestration layer. It has both:
- **File system access** — reads/writes site maps, workflows, and screenshots from this repo.
- **Browser control** — via the Claude-in-Chrome MCP extension tools (DOM reading, clicking, form input, navigation, screenshots).

The user interacts through Claude Code (CLI, desktop app, or web app) while the target site is open in Chrome with the MCP extension installed.

## Future Vision

A dedicated desktop application (e.g., Electron) that bundles everything into a single window:
- Embedded browser for the target site
- Chat/CLI panel for commands and conversation
- Controls panel — workflow dropdowns, site selector, map status, verification buttons
- Live map view — current page's mapped elements highlighted in the browser

This replaces the current multi-window setup with a purpose-built workstation for site automation.

## Out of Scope (v1)

- Automatic or scheduled drift detection.
- Cross-site reusable workflow templates (cross-site workflows are supported; reusable templates are not).
- Map versioning beyond git history.
- CI/CD integration.
- Dedicated desktop application (see Future Vision).
