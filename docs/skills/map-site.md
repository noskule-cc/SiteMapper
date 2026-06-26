# Map Site: Discovery Session

Start a discovery session to map a web application. Reads the current page in Chrome, suggests elements to catalog, and builds YAML page maps through conversation with the user.

## Setup

1. Create the site directory if it doesn't exist:
   - `sites/<site>/pages/`
   - `sites/<site>/workflows/`
   - `sites/<site>/screenshots/`

2. Read the schema files for reference:
   - `schema/page.yaml` — page map format
   - `schema/site.yaml` — site config format

3. Check if `sites/<site>/site.yaml` already exists. If not, create one.

## Discovery Loop

For each page the user wants to map:

1. **Read the current page** using `mcp__claude-in-chrome__read_page` to get the DOM structure.
2. **Analyze the page** and suggest:
   - Page name and purpose
   - Key interactive elements (buttons, inputs, links, selects) with semantic locators
   - Preferred locator strategy (data-testid > aria-label > text > role > css)
3. **Present suggestions** to the user and ask them to confirm, correct, or remove each one.
4. **Ask about gotchas** — non-obvious behavior, edge cases, things that might trip up automation.
5. **Write the page YAML** to `sites/<site>/pages/<page-name>.yaml` following the schema.
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
- Screenshots are optional — skip unless the user specifically requests them or visual drift detection is needed.
