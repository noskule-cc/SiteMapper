# Guardrails — framework template

**Framework file.** Copy to `docs/guardrails.md` and fill in with your project's
real rules. Keep this template as-is; the lowercase copy is project content.

Guardrails are the standing rules every session follows, whichever agent is
driving. They are **behavioural, not enforced**: the tools an agent holds — MCP
servers, file permissions, credential stores — are configured globally per user,
not per project. Nothing in a repo can enforce them. That is precisely why they
are written down, and why they belong in the neutral doc layer that every host
reads rather than in one host's instruction file.

## Why this is not `SECURITY.md`

GitHub claims the filename `SECURITY.md` for vulnerability-disclosure policy and
picks it up from repo root, `.github/` **and** `docs/`. A guardrails file is a
different document — operating rules for agents, not a disclosure policy. Do not
name it `SECURITY.md`, in any of those three locations.

## Categories to cover

Work through each. Omit a heading only if it genuinely does not apply — an empty
section is more honest than a missing one, because a reader can tell the
difference between "no rule" and "nobody thought about it".

| Category | Answers | Typical content |
|---|---|---|
| **Privileged tool access** | Which systems may the agent touch, and how far? | Per-project/tenant scope tables for MCP servers that authenticate as the user |
| **Credentials** | What may the agent type or store? | Never enter passwords/MFA/tokens; never commit secrets (browser storage-state files included); how to reference one at run time. Automated login is an env-scoped permission (`policy.permissions.auth`), not a blanket rule — dev/staging may allow it, production stays human-supervised (`schema/persona.yaml`, `docs/PERMISSIONS.md`) |
| **Write authorization** | When may the agent change state? | The machine-readable flag that gates it, and why it stays off by default |
| **Production** | Which environments are real? | Environments that look like sandboxes but are not |
| **Destructive actions** | What may the agent delete? | Only what this run created; locate by identity, never by screen position |
| **What may be committed** | What is safe to publish? | Repo visibility, customer/personal data, run outputs vs. reusable source |

## Writing rules that hold

- **State the rule, then the reason.** A rule whose rationale is missing gets
  "optimized away" by the next person who finds it inconvenient.
- **Cite the incident.** Rules that came from a real failure should say so, with
  the date. It is the difference between a rule people follow and one they route
  around.
- **Point, do not duplicate.** If the fact lives with the thing it describes (a
  page gotcha, a site config), link it. Two copies drift, and the guardrail is
  the copy nobody updates. See `KNOWLEDGE_PLACEMENT.md`.
- **Name the tension.** Where two legitimate rules conflict, say so and mark it
  open rather than silently picking one.
- **Give the machine-readable form priority.** Where a flag encodes the rule,
  the flag is authoritative and the prose explains it.

## Integrating

1. Link it from `AGENTS.md` under Mandatory Reading — guardrails are not
   situational.
2. Add a row to the `KNOWLEDGE_PLACEMENT.md` table: *a standing rule every
   session must follow → `docs/guardrails.md`*.
3. Move any rule currently sitting in a host-specific instruction file
   (`CLAUDE.md`, `.cursorrules`, …) into it. Those files should contain nothing
   but a pointer, or the rule binds only one agent.
