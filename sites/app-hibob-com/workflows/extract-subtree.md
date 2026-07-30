# extract-subtree

List every employee below a defined person in the HiBob reporting hierarchy — their
full org subtree, resolved to name / title / department / location.

**At a glance** — Site: app-hibob-com · Mode: agentic · In: `$root_person` (name or
email), `$max_depth?`, `$output?` → Out: `subtree` (`{root, totalDescendants,
directReports, tree, flat}`)

## How it works

The reporting edges live only in the Organigramm, but the underlying data is a clean
JSON API. `hibob_subtree.js` runs **in the logged-in browser tab** (HiBob's `/api` is
cookie-authed — no token, no headless mode), reads all 143 employees from
`/api/employees/essentials`, walks `work.reportsTo` edges down from the chosen root,
and resolves title/department ids via `/api/company/metadata/lists/`. The node count is
cross-checked against the org chart's own "total · direct" pill.

## Flow
```mermaid
flowchart TD
  A["Navigate to /people/org?tab=org-chart"] --> B{"Logged in?<br/>(Organigramm visible)"}
  B -- no --> B0["Stop — ask user to sign in<br/>(never enter credentials)"]
  B -- yes --> C["Inject hibob_subtree.js →<br/>await hibobSubtree($root_person, {maxDepth})"]
  C --> D{"ok?"}
  D -- "no match" --> E["Report error, ask for a<br/>different name/email → retry"]
  D -- "ambiguous" --> F["Show candidates, ask which<br/>person → retry"]
  D -- yes --> G["Verify totalDescendants · directReports<br/>vs org-chart count pill"]
  G --> H{"$output"}
  H -- tree --> I["Print indented tree<br/>Name — Title · Site"]
  H -- flat-table --> J["Print table<br/>Name | Title | Department | Site"]
  H -- result-file --> K["Write results/&lt;root-slug&gt;-worker-tree.&lt;date&gt;.md"]
```

## See also

- Script: [`../scripts/hibob_subtree.js`](../scripts/hibob_subtree.js)
- Page map: [`../pages/mitarbeitende-organigramm.yaml`](../pages/mitarbeitende-organigramm.yaml)
- Example output: `results/<root-slug>-worker-tree.<date>.md` — run outputs are **not
  committed** (they are lists of named employees); they stay local. See `.gitignore`.
