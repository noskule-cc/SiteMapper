# Overview

The dashboard shows one page for the whole map tree: a header with the tree's name, its live state and counts, a landscape graph of projects and the sites they span, and one card per project, app and site. Each site card lists its workflows and scripts as process rows, with links to their YAML and flowcharts.

## Sub-features

- `ov-header` names the tree, says `live — localhost only`, and counts sites, projects, processes, workflows, scripts and mapped pages.
- `ov-graph` draws the landscape with one link per project and site node.
- `ov-cards` shows the sections `Projects`, `Apps` and `Sites` with one card each.
- `ov-links` links each card and row to its YAML and flowchart files, served from the tree.

## How to get to it (user POV)

- Run `python scripts/serve.py` and open the printed address.

## Driving it with verify.py

Preconditions:

- A copy of the framework checkout.

- **Header.** Run `verify.py drive goto:/ "expect:live" "expect:1 agentic, 2 deterministic by mode" "expect:4 cards" shot:ov-home`. The `banner` in `ov-home.aria.yaml` holds the heading, the counts and the search box. Each count is a number and a label in separate elements, so read them in `ov-home.txt` (`2` above `SITES`), not with `expect:2 sites`.
- **Graph and sections.** In `ov-home.aria.yaml`, find `img "projects and the sites they span"` with links to `#p-demo-checks`, `#s-sitemapper-demo` and `#s-sitemapper-demo-dev`, and the headings `Landscape`, `Projects`, `Apps` and `Sites`.
- **File links.** Run `verify.py drive goto:/ "click:link:site.yaml" "expect:SiteMapper Demo" shot:ov-file`. The URL ends in `/sites/sitemapper-demo/site.yaml`, and the body is the YAML text.

## Gotchas

- The header's heading also contains the deploy button's label, so its accessible name changes after a deploy click.
- The header counts come from the collectors at request time. A count that disagrees with `docs/inventory.md` points at a collector bug, not the renderer (see `docs/feature-map.md`).
- `click:link:site.yaml` takes the first of two `site.yaml` links. Scope with `within:sitemapper-demo-dev` to reach the other one.
