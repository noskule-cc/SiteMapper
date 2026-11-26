# Run button

Each deterministic workflow row has a `▶ run` button and a `copy` button. It asks the server to run the workflow through the permission gate. A read-only workflow runs at once. A mutating one asks first, and a denied one is refused. The row's result box then shows a class chip (`ok` on a pass), the outcome and one line per assertion. A failed run adds `error:` and `next:` lines. A workflow with parameters first asks for each one with a prompt. The button reads `running…` while the run lasts. An agentic workflow shows a `/run <name>` button that copies the command instead.

## Sub-features

- `run-read` runs a read-only workflow and shows `ok <workflow>: passed (<n>/<n> assertions passed)` with a `PASS  <assertion id>` line per assertion.
- `run-record` writes the run's record under the tree's `runs/` and appends a line to `runs/SiteMapper/index.<machine>.jsonl`.
- `run-ask` asks before a mutating run, and shows `not run: consent declined` when the person says no.
- `run-agentic` offers `/run <name>` to copy for an agentic workflow, with no run.

## How to get to it (user POV)

- Choose `▶ run` on a process row of the served dashboard.

## Driving it with verify.py

Preconditions:

- A copy of the framework checkout. `doctor` says `Run buttons: allowed`.
- Chrome or Edge installed, and network access to github.com (the demo site is a public GitHub repository).

- **Run.** Run `verify.py drive goto:/ within:search-issues shot:run-before "click:button:▶ run" "expect:running…" "await:search-issues: passed" "absent:refused" shot:run-after`. `run-after.txt` shows `ok search-issues: passed (5/5 assertions passed)` and five `PASS` lines.
- **Record.** Before `down`, list `<copy>/runs/SiteMapper/`. It holds `index.<machine>.jsonl` and `sitemapper-demo/search-issues.<YYYY-MM-DDTHHMMSS.mmmZ>.<tier>.<machine>.<hex>/`. That folder has `run.yaml` and a `result.json` that says `passed` with `{'total': 5, 'passed': 5, 'failed': 0}`.
- **Server.** `server.log` has a `POST /api/run/search-issues` line with `200` and no traceback.
- **Agentic.** Run `verify.py drive goto:/ within:smart-issue "expect:/run smart-issue" shot:run-agentic`. The row has no `▶ run`.

## Gotchas

- A run takes about a minute. Use `await:`, not `expect:`.
- The demo site is the real github.com. When GitHub is slow, a step times out and the run ends as `<class> search-issues: error (<p>/<t> assertions passed)` with an `error: [<phase>] TimeoutError: ...` line. `server.log` still has a `200`, because the runner answered, so a `200` alone does not prove a pass. Retry once on a fresh `up` before suspecting the code. A failure that repeats is real. The page shows `refused:` with a `500` only when the runner prints no result or exceeds the server's time limit.
- The result box replaces the button's text only while the run lasts. A `shot` taken right after the click shows `running…`.
- Before the fix that shipped with this map, the runner's output reached `serve.py` in the Windows code page. The server crashed decoding it, and the button never showed a result, although the run passed and wrote its record. A run that passes in `runs/` but not on the page is that class of bug. Read `server.log`.
- `run-ask` cannot be driven: the demo maps have no deterministic mutating workflow, and Playwright declines every confirm dialog anyway.
- `search-issues-on-tier` (on the `demo-checks` card) needs the parameter `environment`, and its `▶ run` asks for it with a prompt. Playwright dismisses the prompt, so the click starts nothing and `server.log` shows no POST. It cannot be run from here.
- On a `--from` copy, `drive` refuses the click before the browser sees it. That refusal is the safety rule, not a failure of the page.
