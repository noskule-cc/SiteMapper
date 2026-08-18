# `sites/` — one directory per mapped application

```
sites/<site>/
  site.yaml            base URL, auth notes, page + workflow listings, scripts
  pages/<page>.yaml    elements with semantic locators, and the gotchas
  workflows/           single-site workflows: <name>.yaml + <name>.md companion
  scripts/             deterministic helpers, when an API beats driving the UI
  results/             run outputs — gitignored, see the repo's .gitignore
  screenshots/         reference captures for drift checks
```

Formats are defined in the framework repo: `schema/site.yaml`, `schema/page.yaml`,
`schema/workflow.yaml`. `sites/sitemapper-demo` there is a complete worked example.

Two things that are easy to get wrong:

- **Every workflow YAML needs a sibling `.md`** with a Mermaid flowchart. The
  framework's `scripts/check.py` fails the build without it.
- **A page map records behaviour, not just structure.** The locators save an
  agent a DOM crawl; the `gotchas` are what save it from a wrong answer.
