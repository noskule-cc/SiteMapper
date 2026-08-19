# Maintenance

The routine that keeps a SiteMapper tree healthy, and how to read the signals
when it is not. Registry of the runnable jobs referenced here: `JOBS.md`.

## Before every commit

`python scripts/check.py` (add `--root <maps>` in a map repository). Eight
checks, non-zero exit on failure:

| Check | Catches | On failure |
|---|---|---|
| `yaml` | a file that does not parse | fix the YAML |
| `schema` | keys used by files but absent from `schema/*.yaml` (and vice versa, as notes) | add the key to the template, with its comment |
| `listings` | `site.yaml`/`project.yaml` naming files that are not on disk, or files nobody lists | fix the listing or add the file |
| `companions` | a workflow without its sibling `.md` | run the `workflow-companion` sub-agent |
| `links` | markdown links, path refs and `screenshot:` targets that do not resolve (case-sensitively — Linux CI is the honest judge) | fix the reference, not the check |
| `bindings` | a `docs/skills|subagents/*.md` without a binding or unregistered in `AGENTS.md`/`INDEX.md` | finish the registration (framework repo only) |
| `inventory` / `overview` | generated views out of date | `python scripts/inventory.py` |

After adding/removing a site, page, workflow or project: `inventory.py`, then
`check.py`. CI runs the same checks on every push.

## Drift

Drift is discovered two ways, and both end in the same place:

- **In passing (automatic):** every headless run verifies page fingerprints;
  a mismatch or failed step downgrades the workflow's `trust:` to `broken` in
  its YAML and produces a structured failure report.
- **On demand:** `/verify-map <site>` walks a whole map. Do this when a
  workflow step fails to find a mapped element, and periodically for sites
  you do not control — a long-stale `verified_at` in `site.yaml` is the
  signal; there is no fixed cadence worth pretending to have, the honest
  trigger is "the site shipped a release" or "a run broke".

Either way the fix is the repair skill (`docs/skills/repair.md`): patch the
map, never the workflow; re-run; restore trust. `mapped_at` far behind
reality plus repeated repairs on one page means re-map the page
(`/map-site`), not another patch.

## Results retention

Commit a run when it is **evidence someone will come back to** — the record
behind a published number, the reviewed green run behind a `trust: verified`
promotion, the reproduction of a bug. Routine green runs are noise; do not
commit them. Two guards, stated once here for every project:

- **Log size:** a device that is offline all window repeats one failure with
  a full stack trace — tens of MB, a few thousand unique lines. Commit the
  sibling `.md` summary; leave raw logs local.
- **Map repositories exclude `results/` blanket-style** in `.gitignore`
  (see `data/gitignore.template`), so committing a record is a deliberate
  exception, never a default.

## Housekeeping

- Prune remote branches whose work landed (`git branch -r --merged`).
- `__pycache__/`, `.runner/`, `.$*.bkp` (draw.io backups) are gitignored —
  if one shows up in `git status`, the gitignore of that repo regressed.
- The pre-2026-08-17 history is preserved on `backup/old-main-cb46c2b`
  locally; it is not on the remote and should not return there.

---

**Last Updated:** 2026-08-20
