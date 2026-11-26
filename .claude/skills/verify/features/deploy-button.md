# Deploy button

The header's deploy button prepares the dashboard's shareable build for `/deploy-dashboard`. On a map repository it is labelled `deploy (private)` and asks first, because that repository's dashboard stays local by default. A no shows `not built: consent declined` for 2.5 s and builds nothing. The button exists only on the served page. On the framework tree it builds at once for the standing artifact.

## Sub-features

- `dep-ask` asks before building a map repository's dashboard.
- `dep-decline` shows `not built: consent declined` and writes no build.
- `dep-build` writes `.runner/deploy/dashboard-artifact.html` and names `/deploy-dashboard` (not drivable here).

## How to get to it (user POV)

- Choose the deploy button in the header of the served dashboard.

## Driving it with verify.py

Preconditions:

- Any copy. The copy is always served as a map repository.

- **Decline.** Run `verify.py drive goto:/ shot:dep-before "click:button:deploy (private)" "expect:not built: consent declined" shot:dep-after wait:3 "expect:deploy (private)" "absent:build ready"`.
- **Nothing built.** Before `down`, check that `<copy>/.runner/deploy/` does not exist. Also check that `server.log` has exactly one `POST /api/deploy`, with `409` (the ask). A decline sends no second request.

## Gotchas

- The label returns to `deploy (private)` after 2.5 s. Check it right after the click.
- Playwright declines every confirm dialog, so `dep-build` on a map repository cannot be driven. The framework-tree branch needs the real checkout as the root, which this skill never serves.
