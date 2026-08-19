# SiteMapper

Persistent, structured site maps for LLM browser agents. Map a web app once with human-in-the-loop discovery, then reuse the map across sessions — no redundant DOM exploration or screenshot-heavy navigation. The governing idea: **LLM for decisions, code for work.**

## How It Works

Three roles, each given to the executor that is good at it:

1. **Discovery (LLM + human).** An agent walks through a site with you, asking targeted questions; you annotate and correct in real time. The output is YAML: pages, elements, workflows, and the gotchas only a human can contribute.
2. **Execution (code, or an LLM following the map).** Workflows run against the map. `mode: deterministic` workflows run **headless with no LLM at all** (`scripts/run.py`, Playwright driving your installed Chrome), gated by a machine-readable [permission model](docs/PERMISSIONS.md). Agentic workflows run in an LLM session.
3. **Repair (LLM, on demand).** When the site drifts, runs degrade the workflow's `trust` and emit a structured failure report; the repair skill patches the map and execution is fast again.

A generated [dashboard](docs/overview.html) shows the whole estate — servable locally with real run buttons (`scripts/serve.py`).

See [docs/INDEX.md](docs/INDEX.md) for all documentation, the [wiki](https://github.com/noskule-cc/SiteMapper/wiki) for how it functions, and [PRD.md](PRD.md) for the product requirements.

## What is in this repository

**The framework, and one worked example.** The schema, the docs every agent
reads, the consistency checks, and `sites/sitemapper-demo` — a small issue
tracker mapped end to end so the format has something concrete to point at.

**Your maps do not belong here.** A map of a real application describes somebody's
internal systems: page structure, API endpoints, account identifiers, the gotchas
that only show up in production. Keep them in your own repository, private,
alongside the run outputs they produce.

[`data/`](data/) is that repository as a copyable skeleton — README, a
`config.yaml` to fill in, a guardrails starter, and a `.gitignore` that excludes
run outputs as a class:

```bash
cp -r data ../my-maps && cd ../my-maps
mv gitignore.template .gitignore
git init -b main && git add -A && git commit -m "Initial map repository"
gh repo create <owner>/my-maps --private --source . --push
```

The layout mirrors this repo, so nothing about the format changes.

Two things follow from that split, and both are in the schema rather than left to
discipline. Identity values — a contact, a mailbox — are referenced by key from a
map and resolved from private config, so a map never contains an address. And run
outputs are excluded wholesale by `.gitignore` rather than directory by directory,
so a new project's results are private by default instead of after review.

## Project Structure

```
schema/                              # Commented YAML templates — the format's source of truth
  page.yaml site.yaml workflow.yaml  #   Maps and workflows (incl. fingerprint/trust/effect)
  project.yaml settings.yaml         #   Cross-site projects; layered settings + permissions
  result.yaml persona.yaml           #   The neutral run result; who is logged in

docs/                                # Everything agents and maintainers read — start at docs/INDEX.md
  skills/  subagents/                #   Neutral instructions; .claude/ holds the thin bindings

scripts/
  check.py                           #   All mechanical consistency checks (also in CI)
  inventory.py                       #   Generates docs/inventory.md + docs/overview.html
  run.py                             #   Headless deterministic workflow runner
  serve.py                           #   Serves the dashboard live with a run API

sites/sitemapper-demo/               # The worked example: pages/, workflows/, results/
projects/                            # Cross-site projects (none in the framework repo)
config.yaml                          # Global settings: environment + permission defaults
data/                                # Copyable skeleton for your private map repository
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

[SiteMapper.demo](https://github.com/noskule-cc/SiteMapper.demo) — a GitHub repo the worked example maps end to end. Its two workflows show the two execution modes: `search-issues` (deterministic, `trust: verified`, runs headless in CI as the runner's smoke test) and `smart-issue` (agentic — judges similarity and asks before creating).

## Best Fit

- Internal admin tools and dashboards you control
- Stable applications where the DOM doesn't change frequently
- Sites where you can add `data-testid` attributes for rock-solid selectors

## License

Private project.
