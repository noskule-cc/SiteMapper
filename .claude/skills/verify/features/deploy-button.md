# Deploy button

The header's deploy button prepares the dashboard's shareable build for `/deploy-dashboard`. On a map repository it is labelled `deploy (private)` and asks first, because that repository's dashboard stays local by default. A no shows `not built: consent declined` for a moment and builds nothing. On the framework tree it builds at once for the standing artifact.

## Sub-features

- `dep-ask` asks before building a map repository's dashboard.
- `dep-decline` shows `not built: consent declined` and writes no build.
- `dep-build` writes `.runner/deploy/dashboard-artifact.html` and names `/deploy-dashboard` (not drivable here).

## How to get to it (user POV)

- Choose the deploy button in the header of the served dashboard.

## Driving it with verify.py

Preconditions:

- Any copy. The copy is always served as a map repository.

- **Decline.** Run `verify.py drive goto:/ shot:dep-before "click:button:deploy (private)" wait:1 "expect:not built: consent declined" shot:dep-after`.
- **Nothing built.** Before `down`, check that `<copy>/.runner/deploy/` does not exist.

## Gotchas

- The label returns to `deploy (private)` after 2.5 s. Check within a second of the click.
- Playwright declines every confirm dialog, so `dep-build` on a map repository cannot be driven. The framework-tree branch needs the real checkout as the root, which this skill never serves.
