# Search and filter

The search box narrows the page to the cards and process rows whose search text contains the term. That text is built from names, titles, descriptions, URLs, modes and page file names, not from every visible tag. The `kind` buttons (`all`, `workflow`, `script`) and the `mode` buttons (`all`, `agentic`, `deterministic`) narrow it to matching processes. The counter says `<n> cards` with nothing hidden and `<shown> of <n> cards` otherwise, and an empty result shows `Nothing matches that.` instead of cards. A `Projects`, `Apps` or `Sites` section with no visible card is hidden.

## Sub-features

- `sf-search` hides every card and row that does not contain the term, and `Escape` in the box clears it.
- `sf-kind` keeps only processes of one kind.
- `sf-mode` keeps only processes of one mode, and hides cards with no matching process.
- `sf-count` keeps the counter equal to the number of visible cards.

## How to get to it (user POV)

- Type in the search box, or press `/` to focus it.
- Choose a button in the `kind` or `mode` row under the header.

## Driving it with verify.py

Preconditions:

- A copy of the framework checkout (4 cards).

- **Search.** Run `verify.py drive goto:/ "expect:4 cards" "fill:Search sites:smart-issue" shot:sf-search "expect:1 of 4 cards"`. Only the `sitemapper-demo` site card stays in `sf-search.aria.yaml`.
- **No match.** In the same call, add `"fill:Search sites:zzz-nothing" "expect:0 of 4 cards" "expect:Nothing matches that."`.
- **Clear.** Add `"fill:Search sites:" "expect:4 cards" "absent:of 4 cards"`.
- **Mode.** Add `"click:button:agentic" shot:sf-mode "expect:1 of 4 cards"`. The only row left is `smart-issue`. Add `"click:button:deterministic" "expect:2 of 4 cards"`.
- **Kind.** Add `"click:button:script" "expect:0 of 4 cards" "expect:Nothing matches that." shot:sf-kind`. The demo has no scripts.

## Gotchas

- A card that matches hides none of its rows, and a row that matches keeps its card. `search` matches 2 of 4 cards (`demo-checks` and `sitemapper-demo`). Pick terms that only one card contains.
- A site with no workflows renders a placeholder row. Before the fix that shipped with this map, the search loop crashed on that row's missing `data-search`. The cards half-hid and the counter stayed at `4 cards`. If the counter and the visible cards disagree, look for a page error.
- `all` appears twice (kind and mode), so `click:button:all` takes the kind one. Reload with `goto:/` to reset both rows.
