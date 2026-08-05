# Guardrails — SiteMapper

SiteMapper's standing rules, followed by every session whichever agent is
driving. The reusable structure behind this file — the categories, and how to
write rules that hold — is in [GUARDRAILS.template.md](GUARDRAILS.template.md).

Deliberately **not** named `SECURITY.md`: GitHub claims that filename (in root,
`.github/` *and* `docs/`) for vulnerability-disclosure policy, which this is not.

**These are behavioural rules, not enforced ones.** The tools an agent holds —
MCP servers, file permissions — are configured globally, per user, not per
project. Nothing here can be enforced from inside this repo. That is exactly why
it is written down: the rule is the enforcement.

## Azure DevOps (`ado` MCP) access

The `ado` MCP server authenticates as the user, with their full identity. Hard
enforcement would require Azure DevOps-side permissions or a scoped PAT; until
then, check the target project against this table before **any** `ado` call.

| Project | Access |
|---|---|
| **GGplus Anleitungen** (`d04b7d15-f740-4269-8b29-cb70ba3d8c25`) | Full — all tools |
| **GGplus** (`76635751-9628-423b-85eb-33acb0404796`) | **WIKI ONLY** — `wiki_*` / `search_wiki`. Never repos, pipelines, work items, test plans, or any non-wiki write |
| All others (GGplus Order, Opten Libraries, GehrigGroup Connect, …) | None, unless the user authorizes it that session |

## Credentials are a human action

Never type a password, MFA code, or API secret — not into a login form, not into
a script, not into a file. If a site needs auth, confirm the user is logged in
and continue from their session.

No committed file may contain a password or token. A persona/context file
references a live session or a run-time secret (`credential_ref: env:…`), never
the secret itself (#9).

## Form submission is gated by `settings.policy.safe_to_submit_forms`

The machine-readable authorization for writing through a UI. Resolved through the
layered `settings:` block (`config.yaml` → `site.yaml` → page).

- `true` — the agent may fill and submit forms on that scope without asking.
- `false` or absent — **ask first**, every time.

Do not flip it to `true` to unblock a workflow. It is set per scope for a reason;
flipping it at the site level silently authorizes submission on every page of
that site for every future run. `sites/connect-ggplus-ch/site.yaml` carries a
worked example of why it stays `false` on production.

## Production writes

Some "staging" environments are not sandboxes. The BRITA iQ integration is the
known case: prod and stg resolve to **one shared BRITA device record**, so a
cartridge change committed on stg writes production data. Details and evidence
live with the fact, in `sites/connect-ggplus-ch/site.yaml` and
`projects/brita-iq-sync/project.yaml` — not duplicated here.

Before a workflow writes anything on a production scope, confirm that run with
the user, even if a policy flag would allow it.

## Destructive actions, especially in teardown

A test may only delete what that same run created. Never delete a record because
it looks like the one the test made.

This rule exists because of a real incident (2026-07-03): a coordinate-based
click in a teardown step deleted a **pre-existing** Partner-Gruppierung the test
had not created. It was recovered by luck. Teardown runs best-effort after
failures, which is precisely when the page is least likely to be in the state the
step assumed — so a teardown step must locate its target by identity, never by
position.

## What may be committed

**This repository is public.** Anything committed is published permanently: going
private later does not scrub git history, forks, or third-party caches.

Already excluded in `.gitignore`, on privacy grounds — keep it that way:

- `sites/app-hibob-com/results/` — named-employee data (reporting lines, titles)
- `sites/outlook-cloud-microsoft/results/` — third-party correspondence

**Open decision (2026-08-05):** committed `projects/gateway-audit/results/`
currently carries GEHRIG customer names tied to gateway serials, IMSI/IMEI, and
customer locations; `config.yaml` carries personal contact data. That is customer
and personal data in a public repo, and it has not been decided whether to
exclude it, keep it, or make the repo private. Until it is settled, **do not add
new fleet-run results, customer names, or SIM identifiers to committed files.**

Note the tension to resolve: `projects/gateway-audit/results/README.md` requires
full, unabbreviated Seriennummer / Vertragsnummer / IMSI / IMEI in every result —
correct for an internal worklist someone must paste into a ticket, wrong for a
public repo. One of the two rules has to give.

Maps, schemas, workflows and scripts are reusable and belong in the repo. Run
*outputs* are where the customer data is.

## See also

- [KNOWLEDGE_PLACEMENT.md](KNOWLEDGE_PLACEMENT.md) — where a fact belongs
- [issue-tracker.md](issue-tracker.md) — open decisions live as issues
