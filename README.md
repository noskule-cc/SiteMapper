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
schema/          # YAML schema definitions
  page.yaml      # Schema for individual page maps
  site.yaml      # Schema for site-level metadata
  workflow.yaml  # Schema for multi-page task flows
sites/           # One directory per mapped site
  iot-portal/    # Example: IoT admin portal
```

## Quick Start

1. Create a directory under `sites/` for your target app
2. Run the discovery agent against the site
3. Review and commit the generated YAML maps
4. Load the maps as context in future browser automation sessions

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
