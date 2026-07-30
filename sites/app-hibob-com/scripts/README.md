# app-hibob-com scripts

Direct API access to HiBob, so workflows read the reporting hierarchy from JSON
instead of scraping the org-chart canvas.

| Script | Purpose |
|---|---|
| `hibob_subtree.js` | Extract the full reporting subtree under a given person (name or email) → `{ root, totalDescendants, directReports, tree, flat }`. Backs the [`extract-subtree`](../workflows/extract-subtree.yaml) workflow. |

## Auth model — read this first

This is **not** like the `connect-ggplus-ch` Python scripts. Those log in headless
(password grant, token in the OS keyring). HiBob is different:

- HiBob's `/api/*` is **cookie-authed against the logged-in browser session**. There is
  no bearer token to store and no headless mode.
- So `hibob_subtree.js` **runs inside the authenticated `app.hibob.com` tab** — inject
  it with the Chrome MCP `javascript_tool`, then call the function it defines. It never
  sees or handles credentials; you must be signed in to HiBob in Chrome first.

## Usage

Evaluate the file once (defines `globalThis.hibobSubtree`), then call it:

```js
await hibobSubtree("André Senn")                  // by name (case-insensitive, contains-match)
await hibobSubtree("andre.senn@gehriggroup.ch")   // by exact work email
await hibobSubtree("André Senn", { maxDepth: 2 })  // only 2 levels below the root
```

Returns on success:

```
{ ok: true,
  root: { name, title, department, site },
  totalDescendants,          // full count, even if maxDepth caps the displayed tree
  directReports,
  tree,                      // nested { name, title, department, site, directReports, reports[] }
  flat }                     // [{ name, title, department, site, depth }] — root first, CSV-friendly
```

On no/ambiguous match: `{ ok: false, error, candidates? }`.

## Two non-obvious things

**1. Titles and departments are metadata ids, not strings.** `work.title` /
`work.department` on an employee are ids like `"262754546"`. Resolve them via
`/api/company/metadata/lists/` → `lists.title.values` / `lists.department.values`
(`[{ serverId, value, children[] }]`, recurse `children`). `work.site` is already a
plain string. The script does this for you.

**2. The `javascript_tool` safety filter blocks emails.** Returning a payload that
contains email addresses (or cookies) is blocked by the tool. `includeEmail` defaults
to **false** for that reason — keep it false when capturing through the MCP tool.

## Verification

Cross-check `totalDescendants · directReports` against the org chart's own count pill
for the chosen person ("82 · 8" for André Senn). Verified 2026-07-15 against the live
tenant: André Senn → 82 / 8, matching the pill exactly.

Run outputs land in `../results/`, which is **git-ignored** — an extracted subtree is a
list of named employees with titles and locations, so it stays on the machine that ran
it. The map, the script and this README carry no personal data beyond the example name.

## Related

- Workflow: [`../workflows/extract-subtree.yaml`](../workflows/extract-subtree.yaml) · [`.md`](../workflows/extract-subtree.md)
- Page maps: [`../pages/mitarbeitende-organigramm.yaml`](../pages/mitarbeitende-organigramm.yaml), [`../pages/mitarbeitende-verzeichnis.yaml`](../pages/mitarbeitende-verzeichnis.yaml)
