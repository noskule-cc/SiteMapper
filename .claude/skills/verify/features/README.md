# SiteMapper dashboard verification map

This directory is the maintained source for verifying what a person sees on SiteMapper's dashboard. Read this index before driving the dashboard, then use the matching feature file as the recipe.

## Baseline preconditions

- A server started by `verify.py up` in this session, and nothing else.
- `verify.py doctor` prints five `OK` lines.
- Unless a recipe says otherwise, the copy is of the framework checkout. Its maps are the demo app: the sites `sitemapper-demo` (with the workflows `search-issues` and `smart-issue`) and `sitemapper-demo-dev` (no workflows), the app `sitemapper-demo`, and the project `demo-checks`. That makes 4 cards.

## Driving conventions

- Start every recipe with `goto:/`.
- Scope with `within:<workflow>` before clicking a row's button. Every row has its own `▶ run` and `copy`.
- The demo maps change when someone edits them. If a count below no longer matches, read the actual one from a `shot` and fix this map in the same PR.
- Never write a private map repository's site or workflow names into this map.

## Proof and skip reporting

- A proof is a `shot` before the action, the action, a `shot` after it, and a look at `server.log`.
- Report an unreachable path with the step that failed and the precondition that was missing.
- Do not report a path as verified through a different one. A call to `/api/run` with a script does not prove the button.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order: `Sub-features`, `How to get to it (user POV)`, `Driving it with verify.py`, `Gotchas`.

## Features

- [Overview](./overview.md) covers the header counts, the landscape graph and the Projects, Apps and Sites sections.
- [Search and filter](./search-and-filter.md) covers the search box, the kind and mode filters and the card counter.
- [Run button](./run-button.md) covers running a read-only demo workflow from its row and reading the result.
- [Deploy button](./deploy-button.md) covers the deploy ask on a map repository and its declined state.
- [Static page](./static-page.md) covers `docs/overview.html` opened as a file, without run buttons.
