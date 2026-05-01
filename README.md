# SiteMapper

Persistent, structured site maps for LLM browser agents. Map a web app once with human-in-the-loop discovery, then reuse the map across sessions — no redundant DOM exploration or screenshot-heavy navigation.

## How It Works

1. A discovery agent walks through a site with you, asking targeted questions
2. You annotate and correct in real time
3. The output is a set of YAML files describing pages, elements, flows, and gotchas
4. Future agent sessions load the map as context instead of re-exploring from scratch

See [Concept.md](Concept.md) for the full design rationale and [PRD.md](PRD.md) for the product requirements.

## Project Structure

```
schema/                              # YAML schema definitions
  page.yaml                          #   Page map format
  site.yaml                          #   Site-level metadata
  workflow.yaml                      #   Workflow format (single + cross-site)
  project.yaml                       #   Cross-site project format

sites/                               # One directory per mapped site
  iot-portal/
    site.yaml                        #   Base URL, auth, page list
    pages/
      dashboard.yaml                 #   Navigation elements + sidebar
      maschinenpark.yaml             #   Device list with drill-down
      geraet-detail.yaml             #   Device detail with 5 tabs
      admin-benutzerverwaltung.yaml  #   User management
      ...                            #   (23 pages total)
    workflows/
      switch-partner-to-maschinenpark.yaml  # Site-specific workflow

projects/                            # Cross-site workflows grouped by project
  device-monitoring/                 #   Example project
    project.yaml                     #   Sites: [iot-portal, issue-tracker]
    workflows/
      check-offline-report.yaml      #   Read IoT portal → write issue tracker
```

## Quick Start

See [USAGE.md](USAGE.md) for detailed instructions on mapping sites, writing workflows, and running them.

## Map Format

Maps use YAML with semantic locators (text, aria-label, role, `data-testid`) rather than brittle CSS selectors. Each page map captures:

- Page purpose and URL pattern
- Key interactive elements
- Named flows for common tasks
- Gotchas and non-obvious behavior

## Best Fit

- Internal admin tools and dashboards you control
- Stable applications where the DOM doesn't change frequently
- Sites where you can add `data-testid` attributes for rock-solid selectors

## License

Private project.
