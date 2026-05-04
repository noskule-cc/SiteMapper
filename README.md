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
  sitemapper-demo/
    site.yaml                        #   Base URL, auth, page list
    pages/
      issues-list.yaml               #   Issue list page
      new-issue.yaml                 #   New issue form
    workflows/
      smart-issue.yaml               #   Create issue workflow
```

## Getting Started

See [USAGE.md](USAGE.md) for setup, mapping sites, writing workflows, and running them.

## Map Format

Maps use YAML with semantic locators (text, aria-label, role, `data-testid`) rather than brittle CSS selectors. Each page map captures:

- Page purpose and URL pattern
- Key interactive elements
- Named flows for common tasks
- Gotchas and non-obvious behavior

## Demo Site

[SiteMapper.demo](https://github.com/noskule-cc/SiteMapper.demo) — a GitHub repo for testing SiteMapper end-to-end. Map at least the readme and issues page, then create a "smart issue" workflow where it asks the user for an issue, checks for similar existing issues, presents matches, and lets the user decide whether to create it or not.

## Best Fit

- Internal admin tools and dashboards you control
- Stable applications where the DOM doesn't change frequently
- Sites where you can add `data-testid` attributes for rock-solid selectors

## License

Private project.
