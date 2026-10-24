# SiteMapper Interface

How a host — an LLM agent (Claude Code, Codex, …) or a plain Python program — invokes SiteMapper and consumes its output. SiteMapper is a **sub-unit**: it drives mapped sites and returns structured results. It does not decide what to do with those results.

## Boundary

| Inside SiteMapper | Outside (host OS) |
|---|---|
| Maps + workflows (site-level and cross-site) | Choosing which workflow to run, supplying parameters |
| Executing steps / driving the browser | Routing the `result` to a sink (DevOps, Jira, file, DB) |
| Emitting a neutral `result` object | Pass/fail policy, run history, requirement linking |
| Auth for the **mapped site** | Credentials for **external systems** + cross-system orchestration |

SiteMapper **returns** the result; it never **pushes** it. Swap the destination by changing only the host's adapter — never the workflow. This is what keeps SiteMapper reusable.

## The contract: three verbs

```
list_workflows(site?)        -> [ { name, site(s), mode, summary } ]
describe_workflow(ref)       -> { parameters, fixtures, mode, output_schema }
run_workflow(ref, params)    -> result        # schema/result.yaml
```

`describe_workflow` exposes the input schema (parameters/fixtures) and the output schema so any caller can introspect a workflow without a human reading the YAML.

- **Input** = the workflow's `parameters` (+ pinned `fixtures`) — see `schema/workflow.yaml`.
- **Output** = the `result` object — see `schema/result.yaml`.

## Failure classes

Every result carries `class` and `next` beside `status`. `class` says what the outcome means for the map. `next` names the one step that addresses it. Both are additive, so a host that reads only `status` and the exit code keeps working.

| `class` | Means | `next`, for example | Sets `trust: broken` |
|---|---|---|---|
| `ok` | passed or waiting, no drift | empty | no |
| `input` | a parameter, persona, context or workflow name is missing or wrong | `run nap again with --param size=...` | no |
| `refused` | policy or the runner refused the run | `pass --yes-write to consent to this one run` | no |
| `auth` | no session: missing or expired saved state, a missing secret, a rejected login | `refresh the persona's session: ...` | no |
| `drift` | the page is not what the map says | `/repair <workflow>` | yes |
| `assert` | an assertion failed | `compare assertion <id> with the live page before you patch the map` | yes |
| `error` | anything else, such as a script that exited non-zero | fix script 'x.py' (its stderr is in `error`), then run &lt;workflow&gt; again | no |

Before a `drift` or `assert` class breaks trust, the runner replays the run once with the workflow's fixtures as known-good inputs: each parameter that has a fixture of its name is set to that fixture. The replay goes through the same `gate`. When it passes, the map is fine and the caller's arguments found no data, so the class becomes `input` and trust stays. Any other replay outcome keeps the class. Only a `read-only` workflow without a `human` step replays, and only when its fixtures differ from the run's own arguments. The replay is `failure.replay` in the same result (`schema/result.yaml`), so `--record` writes one run record.

The table is `CLASSES` in `scripts/run.py`. A run refused before its first step still prints a result with `--json`, with `status: error`, exit code 2 and no run record. The run record's `run.yaml` and index line gain no keys. The class is in `result.json`.

## Two hosts, one contract

The same three verbs and the same `result` shape serve both kinds of host:

- **LLM host** — the verbs are tools/skills. Today: `/list-workflows`, `/run`, `/test`. The agent introspects via `describe`, runs, gets the `result`, then routes it using its own tools (e.g. an Azure DevOps tool).
- **Python host** — the verbs are a JSON-emitting CLI / importable function, e.g. `sitemapper run <ref> --params '{...}' --json` → the same `result` object, routed with the host's own Azure DevOps SDK.

Both meet in the **MCP server**, `scripts/mcp_server.py`: LLM hosts consume MCP natively, and for a Python host it is one process to start.

## The MCP server

```
python scripts/mcp_server.py [--root PATH] [--projects PATH] [--runs PATH] [--run-timeout SECONDS]
```

A stdio server (the `mcp` package, 2.x). It reads the tree at start, so a host starts one session per run. Its tools:

| Tool | Does | `readOnlyHint` / `destructiveHint` | `_meta` |
|---|---|---|---|
| `list_workflows` | every workflow: name, owner, sites, mode, effect, summary, its run tool | true / false | none |
| `describe_workflow(name)` | parameters as a JSON schema, mode, effect, and each step's number, phase, action and label | true / false | none |
| `preflight(name, params?, persona?, consent?)` | the [preflight](permissions.md#enforcement-rules): each class's decision and rule file, `needs_consent`, outcome, lock key. Starts nothing | true / false | none |
| `run_workflow(name, params?, persona?, consent?, timeout_s?)` | runs any workflow | false / true, the strictest, since it can run anything | none: its lock key is the preflight's |
| `finish_run(run_id, status, by)` | ends a `waiting` run at a person's answer: `passed` after an approval, `failed` after a rejection, with who answered. The same answer again changes nothing; a run that is not waiting is refused | false / false, `idempotentHint` true | none |
| `run-<workflow>(params?, persona?, consent?, timeout_s?)` | runs that workflow; one per `mode: deterministic` workflow with a declared effect and fixed sites | from its `effect`: `read-only` true / false, `mutating` false / false, `destructive` false / true | `teamos/lock`: its lock key at default parameters |

A run is `run.py <workflow> --json --record --trigger ui` in a child process, so the gate and the run record are the runner's own. Before it starts, the server runs the preflight:

- `deny` returns `status: denied`, `class: refused` and a `next`, and starts nothing.
- An `ask` that `consent` does not answer returns `status: needs-consent` with `needs_consent`, `class: refused` and a `next`, and starts nothing.
- Otherwise the run starts, with `--yes-<class>` only for the classes the preflight reported as `ask`. Consent covers this one run, never the policy.

Each step sends a progress notification (`step N/M: label` on the runner's stderr). The result is `{run_id, status, class, next, waiting_for, error, replay, record}`, with `replay` the result's `failure.replay` or null; a run that reaches a `human` step returns `status: waiting`. A runner error before the first step, such as a missing parameter, is a result with `status: error`, its class and no `run_id`. A run tool exists only where the lock key is known before the run: a workflow with `tiers`, or with a site given as `$name`, takes its sites from the run's parameters or context, so it has no `run-<workflow>` tool and runs through `run_workflow`, whose lock key is the preflight's.

These are tool errors, each naming the cause:

- A parameter the workflow does not declare. Nothing starts.
- Runner output that is not a result with a `status`, with the last output lines.
- A run longer than its timeout, which is then stopped. The timeout is `timeout_s` when the call gives it, else `--run-timeout`, default 1800 seconds. The workflow schema has no run-time key, so a host such as TeamOS sets `timeout_s` and its own read timeout above it.
- A child the server cannot place in its Job Object. It is stopped before it runs.

Cancelling the call, or closing the session, kills the run and everything it started: on Windows the child runs in its own Job Object, elsewhere in its own process group. A process that the run started and that outlives it is killed when `run.py` exits, so the result never waits on it. A host's read timeout must exceed the run's timeout, because progress does not reset it.

## Who executes the steps

Whether a host needs an LLM at run time depends on the workflow's `mode`:

| `mode` | Steps | Executor |
|---|---|---|
| `deterministic` | navigate, click, input, read, `assert`, wait | A plain engine (Playwright/Selenium) — **no LLM**. Runs headless in CI. |
| `agentic` | also includes judgement steps (`verify` that decides/branches, free-text formatting) | **Needs an LLM** in the loop. |

UI test workflows should be `deterministic` so they run headless and feed a host (e.g. a DevOps test run) without an agent.

## Bindings

The three verbs are the contract. **How** a host exposes and executes them is a
binding, and bindings are replaceable.

| Layer | Where it lives | How a host consumes it |
|---|---|---|
| Skills | `.claude/skills/<name>/SKILL.md` — frontmatter + the full instructions | Claude Code registers it as a slash command; every other tool reads the same file and follows it inline |
| Agents | `.claude/agents/<name>.md` — frontmatter + the full instructions | Claude Code runs it forked; every other tool reads the file inline |
| Registry | [skills-and-agents.md](skills-and-agents.md) | the routing table any tool starts from |
| Capabilities | named in the skill (navigate, click, …) | mapped to tools in [host-bindings.md](host-bindings.md) |
| Entry point | `docs/AGENTS.md` | root `AGENTS.md` points at it (as do `CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`) |

**One capability, one file.** Instructions live in exactly one place and are
written in capability terms, never host tool names — that is what keeps them
portable. A second copy per host is the thing to avoid: it diverges silently,
because it still works on the machine where it was written. (`.claude/` is a
directory name, not a dependency; nothing inside it may name a host's tools.)

### Agents are an execution strategy, never part of the contract

An agent is one way to *carry out* `run_workflow`. It is not one of the verbs.
Every workflow must produce an identical `result` on a host with no sub-agent
concept at all — fan-out buys speed and context isolation, never behaviour.

If a workflow's outcome depends on parallelism, that is a defect in the workflow.
Where the work is mechanical, prefer a **script** (`action: script`): it is
faster than fan-out *and* runs on every host.

Neutral means **portable, not minimal**. A host with more capability should use
it fully; the neutral layer is never written down to the weakest host.

## Out of scope

Routing results into Azure DevOps / Jira / a page / a database, and any cross-system orchestration, are the **host's** responsibility — not SiteMapper's. SiteMapper's job ends at returning a valid `result`.
