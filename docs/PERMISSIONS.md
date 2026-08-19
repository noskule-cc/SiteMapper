# Permissions

The machine-readable authorization model: **action classes × allow/ask/deny,
checked up front.** Host-independent — every executor (an LLM host, the
headless runner, anything else) enforces the same policy; only the `ask`
channel differs.

## Action classes

| Class | Covers | Default |
|-------|--------|---------|
| `read` | navigate, read, assert — changes nothing on the site | `allow` |
| `write` | creating/editing data; form submission included | `ask` |
| `auth` | logging in without a human (persona `automated`) | `ask` |
| `destructive` | deleting/overwriting data the run did not create | `deny` |

A workflow declares what it does via `effect:` (`schema/workflow.yaml`):
`read-only → read`, `mutating → write`, `destructive → destructive`. Declared,
not inferred — a runner cannot judge whether a click mutates.

## Policy

`settings.policy.permissions` in the layered settings model
(`config.yaml` → `site.yaml` → page — see `schema/settings.yaml`), typically
keyed by environment at the site scope:

```yaml
# a staging site's site.yaml
settings:
  policy:
    environment: staging
    permissions: { write: allow, auth: allow, destructive: ask }
# production stays at the global defaults: write ask, auth ask, destructive deny
```

`safe_to_submit_forms` is the legacy alias: `true` acts as `write: allow` on
that scope when `permissions.write` is unset.

## Enforcement rules

- **Up front, fail fast.** The gate runs before the browser opens; a denied
  run names the class, the policy source and the environment. Never mid-flow.
- **Strictest wins.** Cross-site workflows are gated against every involved
  site.
- **`ask` needs a human.** LLM host: ask in the conversation. Headless runner:
  TTY prompt, or an explicit `--yes-write` / `--yes-destructive` flag.
  Non-interactive (CI): **`ask` degrades to `deny`.**
- **In the live dashboard, the button is the ask channel.** `scripts/serve.py`
  keeps the gate server-side (the browser is untrusted UI): a `read-only` run
  just runs; where policy says `ask`, the server returns the question and the
  page's confirmation click sends consent **for that one run only** — a
  browser click can never widen policy, and `deny` is refused server-side no
  matter what the page sends.
- **`trust: verified` grants nothing.** Verified means proven to run, never
  allowed to write. The two axes stay independent.

This is the structural fix for the 2026-07-03 incident class: a destructive
teardown can no longer run blind in an environment whose policy says
`ask`/`deny`.

---

**Last Updated:** 2026-08-19
