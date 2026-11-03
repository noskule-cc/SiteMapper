# Static page

`docs/overview.html` is the same dashboard written to a file by `scripts/inventory.py`. Opened from disk (or published as an artifact), the page finds no API. It shows the same cards, search and filters, with copy-paste commands where the served page has buttons that run.

## Sub-features

- `st-render` shows the cards and counts without a server.
- `st-no-run` shows no `▶ run` button, because the page cannot run anything.
- `st-search` searches and filters as on the served page.

## How to get to it (user POV)

- Open `docs/overview.html` in a browser.

## Driving it with verify.py

Preconditions:

- `docs/overview.html` is current (`python scripts/check.py` passes). A server is not needed, but `drive` needs the state file, so `up` must have run.

- **Render.** Run `verify.py drive "goto:file:///<checkout>/docs/overview.html" "expect:4 cards" "absent:▶ run" shot:st-render`, with `<checkout>` as an absolute path using forward slashes.
- **Search.** In the same call, add `"fill:Search sites:smart-issue" "expect:1 of 4 cards"`.

## Gotchas

- This is the committed file, not the copy. After changing `scripts/overview.py`, regenerate it with `python scripts/inventory.py` first, or the recipe tests the old page.
- File links (`../sites/...`) open the checkout's files, not the copy's.
