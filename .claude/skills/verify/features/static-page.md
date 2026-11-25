# Static page

`docs/overview.html` is the same dashboard, rendered by `scripts/overview.py` and written by `scripts/inventory.py`. Opened from disk, the page finds no API and says `local copy — this machine only`. It shows the same cards, search and filters. Where the served page has `▶ run` and `copy`, each deterministic workflow has one copy button with its command (`python scripts/run.py <workflow> --record`). It has no deploy button and no artifact chip.

## Sub-features

- `st-render` shows the cards and counts without a server.
- `st-no-run` shows no `▶ run` and no `deploy (private)` button, because the page cannot run or build anything.
- `st-search` searches and filters as on the served page.

## How to get to it (user POV)

- Open `docs/overview.html` in a browser.

## Driving it with verify.py

Preconditions:

- `docs/overview.html` is current (`python scripts/check.py` passes). A server is not needed, but `drive` needs the state file, so `up` must have run.

- **Render.** Run `verify.py drive "goto:file:///<checkout>/docs/overview.html" "expect:local copy — this machine only" "expect:4 cards" "absent:▶ run" "absent:deploy (private)" within:search-issues "expect:python scripts/run.py search-issues --record" within: shot:st-render`, with `<checkout>` as an absolute path using forward slashes.
- **Search and filter.** In the same call, add `"fill:Search sites:smart-issue" "expect:1 of 4 cards" "fill:Search sites:" "click:button:agentic" "expect:1 of 4 cards" shot:st-search`.

## Gotchas

- This is the committed file, not the copy. After changing `scripts/overview.py`, regenerate it with `python scripts/inventory.py` first, or the recipe tests the old page.
- File links (`../sites/...`) open the checkout's files, not the copy's.
