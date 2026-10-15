# `apps/` — one application, several tier sites

prod, stg and dev of one application are mapped as separate sites on purpose:
they rarely carry the same feature set and each needs its own page maps. An
app is the one place that says those sites belong together.

```
apps/<app>/
  app.yaml             tier -> site, the page-map parity rule with declared gaps, scripts
  scripts/             scripts that take a tier argument (login, API client, a comparison)
```

Format: `schema/app.yaml` in the framework repo; worked example
`apps/sitemapper-demo` there.

What the app gives you: a project workflow can declare on which tiers it must
exist and pass (`tiers:` in `schema/workflow.yaml`), the framework's `parity`
check reports a page mapped on one tier and not another unless the difference
is declared here with a reason, and a script that knows every tier has an honest
home instead of whichever tier was mapped first.

An app holds no workflows.
