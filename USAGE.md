# Usage Guide

## Prerequisites

- Claude Code (CLI, desktop app, or web app)
- Chrome with the Claude-in-Chrome MCP extension installed
- Target site open in Chrome

## Mapping a Site

1. Open the target site in Chrome.
2. In Claude Code, run `/map-site <site-name>` (e.g., `/map-site issue-tracker`).
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
  name: switch-partner
  description: Switch to a different partner account
  site: iot-portal

  parameters:
    - name: partner_name
      type: text
      description: Partner to switch to
      required: true

  steps:
    - action: click
      page: dashboard
      element: hamburger-menu
      description: Open sidebar

    - action: input
      page: partner-wechseln
      element: search-field
      value: "$partner_name"
      description: Search for partner

  verify:
    - "Red banner shows partner name"
```

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
  name: Device Monitoring
  description: Monitor IoT devices and report issues to the tracker
  sites: [iot-portal, issue-tracker]
  workflows:
    - check-offline-report.yaml
```

**Cross-site workflow with capture variables:**

```yaml
workflow:
  name: check-offline-report
  description: Find offline devices and create an issue
  sites: [iot-portal, issue-tracker]

  steps:
    - action: read
      site: iot-portal
      page: admin-gateway-monitoring
      element: gateway-table
      capture: offline_devices
      description: Read offline device list

    - action: input
      site: issue-tracker
      page: new-issue
      element: description-field
      value: "Offline devices: $offline_devices"
      description: Create issue with captured data

  verify:
    - "Issue created with device list"
```

The `capture` field stores a step's output in a named variable. Later steps reference it with `$variable_name`, even across sites.

## Running Workflows

```
/run <workflow-name>
```

The runner searches both `sites/*/workflows/` and `projects/*/workflows/`. It collects parameters (dropdown for select, prompt for text), executes steps via Chrome MCP tools, and reports results.

## Listing Workflows

```
/list-workflows              # all workflows
/list-workflows iot-portal   # site-specific only
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
