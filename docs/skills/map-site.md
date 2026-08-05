# Map Site: Discovery Session

Start a discovery session to map a web application. Reads the current page in Chrome, suggests elements to catalog, and builds YAML page maps through conversation with the user.

## Setup

1. Open a browser session and navigate to the target URL
   (`docs/HOST_BINDINGS.md` maps these capabilities to concrete tools):
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
2. **Analyze the page** and suggest:
   - Page name and purpose
   - Key interactive elements (buttons, inputs, links, selects) with semantic locators
   - Preferred locator strategy (data-testid > aria-label > text > role > css)
3. **Present suggestions** to the user and ask them to confirm, correct, or remove each one.
4. **Ask about gotchas** — non-obvious behavior, edge cases, things that might trip up
   automation. Anything the user tells you here that is true of the *page* goes into
   this YAML's `gotchas`, not into agent memory — see `docs/KNOWLEDGE_PLACEMENT.md`.
   Watch in particular for **per-user sticky UI state** (a layout toggle, a grouping, a
   saved filter): it survives across sessions, so a later run inherits whatever the last
   one left, and elements that only exist in one state will simply be missing. Record the
   state *and* which elements depend on it.
5. **Write the page YAML** to `sites/<site>/pages/<page-name>.yaml` following the schema.
5b. **Capture a reference screenshot** to `sites/<site>/screenshots/<page-name>.png`
   and record it in the page's `screenshot:` field. It gives `/verify-map` a
   baseline for visual drift that element-existence checks cannot detect.
6. **Ask**: "Navigate to the next page you want to map, or say 'done' to finish."

## When Done

1. Update or create `sites/<site>/site.yaml` with the site config and list of mapped pages.
2. Summarize what was mapped: pages, element count, gotchas captured.
3. Suggest workflows that could be built based on the discovered pages.

## Guidelines

- Prefer semantic locators: `data-testid` > `aria-label` > visible text > `role` > CSS selector.
- Keep element names short and descriptive (e.g., "submit-button", "search-input", "issues-table").
- Capture states when relevant (enabled/disabled/hidden).
- Don't catalog every element — focus on actionable ones the user would interact with.
- Ask targeted questions, don't overwhelm with too many suggestions at once.
- For sidebar/accordion navs, use the chevron (>) to expand submenus — clicking the text navigates away.
- Navigate via direct URL when possible to save time instead of clicking through menus.
- Some pages redirect to dashboard when in a partner context — note these in gotchas.
- Use `children` property on nav elements to document submenu items inline.
- Group page files by section (dienste-, kontakt-, shop-, admin-, einstellungen-) for clarity.
- Document the URL pattern as actually observed (may differ from sidebar label).
- Everything you learn during discovery belongs in the map, not in agent memory. If you catch yourself about to remember a page's behavior, write it as a gotcha instead — that is what makes it survive for the next session and the next person (`docs/KNOWLEDGE_PLACEMENT.md`).
