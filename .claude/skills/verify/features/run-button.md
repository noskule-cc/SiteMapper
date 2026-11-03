# Run button

Each deterministic process row has a `▶ run` button. It asks the server to run the workflow through the permission gate. A read-only workflow runs at once. A mutating one asks first, and a denied one is refused. The row's result box then shows the outcome, one line per assertion, and the class of a failure. The button reads `running…` while the run lasts. An agentic workflow shows a `/run <name>` button that copies the command instead.

## Sub-features

- `run-read` runs a read-only workflow and shows `<workflow>: passed (<n>/<n> assertions passed)` with a `PASS` line per assertion.
- `run-record` writes the run's record under the tree's `runs/`.
- `run-ask` asks before a mutating run, and shows `not run: consent declined` when the person says no.
- `run-agentic` offers `/run <name>` to copy for an agentic workflow, with no run.

## How to get to it (user POV)

- Choose `▶ run` on a process row of the served dashboard.

## Driving it with verify.py

Preconditions:

- A copy of the framework checkout. `doctor` says `Run buttons: allowed`.
- Chrome or Edge installed, and network access to github.com (the demo site is a public GitHub repository).

- **Run.** Run `verify.py drive goto:/ within:search-issues shot:run-before "click:button:▶ run" "await:search-issues: passed" shot:run-after`. `run-after.txt` shows `search-issues: passed (5/5 assertions passed)` and five `PASS` lines.
- **Record.** Before `down`, list `<copy>/runs/SiteMapper/sitemapper-demo/`. It holds one `search-issues.<time>...` folder whose `result.json` says `passed` with `{'total': 5, 'passed': 5}`.
- **Server.** `server.log` has a `POST /api/run/search-issues` line with `200` and no traceback.
- **Agentic.** Run `verify.py drive goto:/ within:smart-issue "expect:/run smart-issue" shot:run-agentic`. The row has no `▶ run`.

## Gotchas

- A run takes about a minute. Use `await:`, not `expect:`.
- The demo site is the real github.com. A run can fail at `step 1/10` when GitHub is slow, and the page then shows `refused: step 1/10: ...` while `server.log` has a `500`. Retry once on a fresh `up` before suspecting the code. A failure that repeats is real.
- The result box replaces the button's text only while the run lasts. A `shot` taken right after the click shows `running…`.
- Before the fix that shipped with this map, the runner's output reached `serve.py` in the Windows code page. The server crashed decoding it, and the button never showed a result, although the run passed and wrote its record. A run that passes in `runs/` but not on the page is that class of bug. Read `server.log`.
- `run-ask` cannot be driven: the demo maps have no deterministic mutating workflow, and Playwright declines every confirm dialog anyway.
- On a `--from` copy, `drive` refuses the click before the browser sees it. That refusal is the safety rule, not a failure of the page.
