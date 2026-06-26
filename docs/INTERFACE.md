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

## Two hosts, one contract

The same three verbs and the same `result` shape serve both kinds of host:

- **LLM host** — the verbs are tools/skills. Today: `/list-workflows`, `/run`, `/test`. The agent introspects via `describe`, runs, gets the `result`, then routes it using its own tools (e.g. an Azure DevOps tool).
- **Python host** — the verbs are a JSON-emitting CLI / importable function, e.g. `sitemapper run <ref> --params '{...}' --json` → the same `result` object, routed with the host's own Azure DevOps SDK.

A clean way to expose both at once is an **MCP server** (the three verbs as MCP tools) that is also runnable as a CLI — MCP is consumed natively by LLM hosts and is just a process a Python host can call.

## Who executes the steps

Whether a host needs an LLM at run time depends on the workflow's `mode`:

| `mode` | Steps | Executor |
|---|---|---|
| `deterministic` | navigate, click, input, read, `assert`, wait | A plain engine (Playwright/Selenium) — **no LLM**. Runs headless in CI. |
| `agentic` | also includes judgement steps (`verify` that decides/branches, free-text formatting) | **Needs an LLM** in the loop. |

UI test workflows should be `deterministic` so they run headless and feed a host (e.g. a DevOps test run) without an agent.

## Out of scope

Routing results into Azure DevOps / Jira / a page / a database, and any cross-system orchestration, are the **host's** responsibility — not SiteMapper's. SiteMapper's job ends at returning a valid `result`.
