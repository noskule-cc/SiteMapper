---
name: deploy-dashboard
description: Publish THIS map repository's dashboard to its own private Claude artifact — the publish half of the dashboard's deploy (private) button. Never the framework's standing URL, never shared.
disable-model-invocation: true
---

Publish **this map repository's** dashboard (not the framework's). Follow the
map-repository half of the framework's skill instructions —
`../SiteMapper/docs/skills/deploy-dashboard.md` — with this repo as the tree:

- The build is `.runner/deploy/dashboard-artifact.html` in THIS repo, prepared
  by the dashboard's deploy button (consent already given there); otherwise
  build it: `python ../SiteMapper/scripts/overview.py --root . --links github --fragment --out .runner/deploy/dashboard-artifact.html`
  — but a missing build usually means the consent click did not happen; ask
  before building one out of thin air.
- Verify the page title is THIS repo's, links point into THIS repo's GitHub,
  and no contact/mailbox values from `config.yaml` leak into the page.
- Publish to the artifact registered in this repo's `config.yaml`
  (`dashboard: artifact_url:`); none registered = first publish, create one
  titled after this repo and write the URL back.
- Record `published_hash` + `published_at` (from
  `.runner/deploy/build-info.json`) in `config.yaml` on every publish — the
  dashboard's staleness chip compares against them.
- The artifact is **private to the operator's account and is never shared**
  (`docs/guardrails.md`, "The dashboard artifact stays private").
