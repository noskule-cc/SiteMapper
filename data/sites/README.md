# `sites/` — one directory per mapped application tier

```
sites/<site>/
  site.yaml            base URL, auth notes, page + workflow listings, scripts
  pages/<page>.yaml    elements with semantic locators, and the gotchas
  workflows/           building blocks of this one site: <name>.yaml + <name>.md companion
  scripts/             deterministic helpers about THIS site only
  screenshots/         reference captures for drift checks
```

Formats are defined in the framework repo: `schema/site.yaml`, `schema/page.yaml`,
`schema/workflow.yaml`. `sites/sitemapper-demo` there is a complete worked example.

Three things that are easy to get wrong:

- **Every workflow YAML needs a sibling `.md`** with a Mermaid flowchart. The
  framework's `scripts/check.py` fails the build without it.
- **A page map records behaviour, not just structure.** The locators save an
  agent a DOM crawl; the `gotchas` are what save it from a wrong answer.
- **A site's workflows are building blocks.** A test, a producer, anything with
  a reason to be run on its own, is a project workflow (`../projects/`). The
  tiers of one application are separate sites, bound together by an app
  (`../apps/`); a script that takes a tier argument belongs to the app.
