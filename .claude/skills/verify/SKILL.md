---
name: verify
description: Drive SiteMapper's own dashboard (scripts/serve.py, the live docs/overview.html) in a real browser against a disposable copy of the maps, and keep screenshots, ARIA snapshots and page text as proof. Use after changing scripts/serve.py, scripts/overview.py or anything the dashboard shows, before calling such a change done, and to reproduce a dashboard bug. Not for testing a mapped site: that is /test and /verify-map.
---

# Verify the SiteMapper dashboard

SiteMapper's own user surface is the dashboard. `scripts/serve.py` serves it on localhost with working run and deploy buttons. `docs/overview.html` is the same page as a static file. `check.py` proves the static file is current, and nothing else proves the page works. This skill starts the server on a scratch copy of the maps, drives the page through Playwright, and keeps the evidence.

Everything runs through one helper, from the SiteMapper checkout:

```bash
python .claude/skills/verify/scripts/verify.py <up|doctor|drive|down> ...
```

It needs Python and Playwright (`pip install playwright`), the same Playwright the headless runner uses. It drives the installed Chrome, else Edge, so there is no browser download. Below, `verify.py` stands for the whole command.

## Safety

The server is never started on a real map repository. `up` copies `sites/`, `apps/`, `projects/`, `schema/` and `config.yaml` into `%TEMP%/sitemapper-verify/<stamp>/maps` and serves that copy.

- **No `.runner/`** in the copy: no saved logins, so no run can sign in anywhere.
- **No `runs/` history**, and an empty `runs/` inside the copy, so every record a run writes stays in scratch.
- **Run buttons only on the framework's maps.** By default `up` copies this checkout, whose only site is the public demo repository. With `--from <map repository>` the copy serves for viewing, and `drive` refuses any button whose name contains `run`. Those maps point at real sites.
- **Confirm dialogs are declined.** Playwright dismisses every `confirm()`, so an ask (a mutating run, a deploy build) ends as `consent declined`. No step can accept one.
- `down` compares the source's maps, `runs/` and `.runner/` before and after, and prints `CHANGED during the run` when anything moved. Treat that as a failed run.

Never point a browser at a server this skill did not start, and never start a second one. `up` refuses while one runs.

## Launch

```bash
verify.py up                                # the framework's own maps (demo site only)
verify.py up --from <map repository>        # a private map repository, view only
verify.py up --port 8790
```

`up` picks a free port unless `--port` is given. It waits until `/api/meta` answers and prints:

```
ready: http://127.0.0.1:<port>/  copy <copy dir>  evidence <evidence dir>
```

## Doctor

```bash
verify.py doctor
```

This check is read-only. It prints `OK` or `FAIL` for five facts: the process runs, the API answers, the server's tree is the scratch copy, runs land inside the copy, and the copy holds no saved logins. It also says whether Run buttons are allowed. It exits 1 when any check fails. The server's output is in `<evidence dir>/server.log`. Read it whenever a button hangs, because a server-side exception shows there and nowhere in the page.

## Drive

```bash
verify.py drive <step> [<step> ...]
```

One `drive` call is one fresh browser (en-US, 1280x900). Steps run in order:

| Step | Does |
|---|---|
| `goto:<path>` | open a dashboard path (`goto:/`), or a full URL (`goto:file:///.../docs/overview.html`) |
| `within:<name>` | scope later steps to the process row with a link of exactly this name, else to the card whose heading contains it. `within:` alone scopes back to the page. |
| `click:<role>:<name>` | click by ARIA role and exact accessible name |
| `fill:<label>:<text>` | type into the first field whose label or placeholder contains `<label>` (empty text clears it) |
| `expect:<text>` | `FAIL` unless the scope shows this text within 5 s |
| `await:<text>` | the same, waiting up to 10 min, for a run's result |
| `absent:<text>` | `FAIL` if the scope shows this text |
| `wait:<seconds>` | wait |
| `shot:<label>` | save `<label>.png` (full page), `<label>.aria.yaml` and `<label>.txt` |

Each step prints `PASS` or `FAIL`. A locator that finds nothing prints `FAIL <step>: <reason>` and ends the call. The call exits 1 if any step failed.

Stable handles on the page are the search box (placeholder `Search sites, processes, pages — press /`), the filter buttons `all`, `workflow`, `script`, `agentic` and `deterministic`, the counter `<n> cards` or `<shown> of <n> cards`, the button `deploy (private)` (the copy is always served as a map repository), and per process row the buttons `▶ run` and `copy`. An agentic workflow shows a `/run <name>` button instead. On Windows, type non-ASCII names such as `▶ run` from a UTF-8 shell, or scope with `within:` and match ASCII text instead. Recipes per feature are in [features/README.md](features/README.md).

## Evidence

Evidence goes to `%TEMP%/sitemapper-verify/evidence/<stamp>/`, with `server.log` beside the shots. `down` keeps it. Proof standards:

- Drive the control a person uses (the search box, a filter, a row's `▶ run`), not the API with a script.
- Take a `shot` before and after the action.
- For a run, also read the record it wrote under `<copy>/runs/` before `down` deletes the copy. The page's result box and the record must agree.
- Evidence from a `--from` copy holds that repository's maps. Keep it out of this public repository's PRs and issues.

## Cleanup

```bash
verify.py down
```

`down` stops the process tree that `up` started (by its pid, never by name), deletes the copy and the state file, and prints where the evidence stays. Run it after every attempt, failed ones too.

## Not covered

- **Accepting an ask.** Confirm dialogs are always declined, so a consented mutating run or a deploy build is not driven. Prove those paths with `tests/test_preflight.py` and by hand.
- **Publishing.** `/deploy-dashboard` publishes an artifact, which needs an interactive session. Out of scope here.

[features/README.md](features/README.md) is the feature map. Keep it current with `/maintain-verification-skill`.
