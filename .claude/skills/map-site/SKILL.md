---
name: map-site
description: Start a discovery session to map a web application. Reads the current page in the browser, suggests elements to catalog, and builds YAML page maps through conversation with the user.
disable-model-invocation: true
argument-hint: [site-name]
arguments: [site]
allowed-tools: Bash(mkdir *) Read Write Edit Glob Grep
---

# Map Site: Discovery Session

Start a discovery session to map a web application. Reads the current page in the browser, suggests elements to catalog, and builds YAML page maps through conversation with the user.

Site argument: $site

## Setup

1. Open a browser session and navigate to the target URL
   (`docs/host-bindings.md` maps these capabilities to concrete tools):
   - **open session** to get or create the agent's own tab — the agent opens its
     own tab, the user does not open it by hand.
   - **navigate** that tab to the start URL the user gives you.
   - If the site needs auth, confirm the user is logged in first; never enter
     credentials yourself.

2. Create the site directory if it doesn't exist:
   - `sites/<site>/pages/`
   - `sites/<site>/workflows/`
   - `sites/<site>/screenshots/`

3. Read the schema files for reference:
   - `schema/page.yaml` — page map format
   - `schema/site.yaml` — site config format

4. Check if `sites/<site>/site.yaml` already exists. If not, create one.

## Discovery Loop

For each page the user wants to map:

1. **read page** to get the DOM structure of the current page.
1b. **read network** to list the requests the page made, so you can propose the
   API endpoints behind it. If the host lacks the capability
   (`docs/host-bindings.md`), tell the user in one line that endpoints are skipped
   on this host, and go on to step 2. Otherwise keep only candidate API calls:
   - drop assets: documents, scripts, stylesheets, images, fonts, media, favicons,
     manifests;
   - drop analytics, telemetry and beacons: ping requests, and requests to
     collector, stats, telemetry or tracking hosts;
   - keep requests that return data (usually JSON) from the site or its API host.

   Draft one entry per candidate per `schema/page.yaml` `endpoints`: a snake_case
   `name`, the URL with a `{placeholder}` for every record id and every query value,
   the elements whose values appear in it as `inputs`, and the top-level keys of a
   JSON response as `returns`. An entry has no description: the name and the page's
   `purpose` carry the meaning. The listing carries the user's session, so never
   copy a header, a cookie, a token or a query value into the draft, the
   conversation or a file. This rule is the guard. `check.py` backs it up but cannot
   see a percent-encoded value or a short id written into prose.
2. **Analyze the page** and suggest:
   - Page name and purpose
   - Key interactive elements (buttons, inputs, links, selects) with semantic locators
   - Preferred locator strategy (data-testid > aria-label > text > role > css)
3. **Present suggestions** to the user and ask them to confirm, correct, or remove each one.
   Present the endpoint candidates from step 1b the same way, each with its method,
   `url_pattern`, `inputs` and `returns`, and ask the user to confirm, rename or reject
   it and to declare its `effect` (`read-only`, `mutating`, `destructive`). Never infer
   the effect from the method.
4. **Ask about gotchas** — non-obvious behavior, edge cases, things that might trip up
   automation. Anything the user tells you here that is true of the *page* goes into
   this YAML's `gotchas`, not into agent memory — see `docs/knowledge-placement.md`.
   Watch in particular for **per-user sticky UI state** (a layout toggle, a grouping, a
   saved filter): it survives across sessions, so a later run inherits whatever the last
   one left, and elements that only exist in one state will simply be missing. Record the
   state *and* which elements depend on it.
5. **Write the page YAML** to `sites/<site>/pages/<page-name>.yaml` following the schema.
   Write only the endpoints the user confirmed, under the names they gave.
5b. **Capture a reference screenshot** to `sites/<site>/screenshots/<page-name>.png`
   and record it in the page's `screenshot:` field. It gives `/verify-map` a
   baseline for visual drift that element-existence checks cannot detect.
6. **Ask**: "Navigate to the next page you want to map, or say 'done' to finish."

## Persist Corrections

A user correction is a lesson the map must keep — that is the entire value of
human-in-the-loop discovery. When the user:

- **corrects a click target** ("the chevron, not the text") → write it as a
  gotcha on that page, phrased as the rule, not the incident;
- **rejects suggested elements** ("skip the footer links") → deprioritize
  that element class for the rest of THIS site's session, and note it in
  `site.yaml` if it is site-wide;
- **rejects or renames a proposed endpoint** → write only what they confirmed,
  under their name, and write the reason for a rejection as a gotcha on the page
  ("`views.json` loads saved views, not issues; do not propose it"), so
  the next session does not propose it again. Name the request by its path and
  say why, never by a value: no header, cookie, token or query value goes into
  the gotcha either;
- **hands you a direct URL** instead of navigating → record it as the page's
  `url_pattern` — direct navigation is preferred by every executor;
- **names a fact you almost put in memory** → it goes in the map
  (`docs/knowledge-placement.md`), never in the host's memory store.

Persist the lesson the moment it is given, in the same session — a correction
repeated in the next session is a correction that was lost.

## When Done

1. Update or create `sites/<site>/site.yaml` with the site config and list of mapped pages.
2. Summarize what was mapped: pages, element count, gotchas captured.
3. Suggest workflows that could be built based on the discovered pages.
4. For each confirmed `read-only` endpoint, suggest one `action: script` step
   (`schema/workflow.yaml`) that calls it from a site script instead of driving
   the page. Data reachable from the site's API is a script, not a browser
   sequence (`docs/code-over-llm.md`).

## Guidelines

- Prefer semantic locators: `data-testid` > `aria-label` > visible text > `role` > CSS selector.
- Keep element names short and descriptive (e.g., "submit-button", "search-input", "issues-table").
- Capture states when relevant (enabled/disabled/hidden).
- Don't catalog every element — focus on actionable ones the user would interact with.
- Ask targeted questions, don't overwhelm with too many suggestions at once.
- For sidebar/accordion navs, use the chevron (>) to expand submenus — clicking the text navigates away.
- Navigate via direct URL when possible to save time instead of clicking through menus.
- Some pages redirect to a landing page while a tenant context is active — note these in gotchas.
- Use `children` property on nav elements to document submenu items inline.
- Group page files by the site's own navigation sections, using that section as a
  filename prefix, so a large map stays browsable.
- Document the URL pattern as actually observed (may differ from sidebar label).
- Everything you learn during discovery belongs in the map, not in agent memory. If you catch yourself about to remember a page's behavior, write it as a gotcha instead — that is what makes it survive for the next session and the next person (`docs/knowledge-placement.md`).
