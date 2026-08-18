# Code Over LLMs

> **Do everything that can be done in code, in code. Reach for a script wherever
> one can do the job.**

It is faster, it is deterministic, it costs no tokens, it runs on every host, and
it does not break when a UI changes.

This is the third governing principle, alongside `INFORMATION_MINIMALISM.md`
(*whether* to write something down) and `KNOWLEDGE_PLACEMENT.md` (*where* it
goes). This one answers **who executes**.

## The boundary

The rule is not "never use an LLM". An LLM is genuinely required for:

- **Human-in-the-loop discovery** — `/map-site`. The user's corrections and the
  gotchas they volunteer cannot be derived from a DOM.
- **Judgement and branching** — a `verify` step that decides, anything marked
  `mode: agentic`.
- **Ambiguous resolution** — matching a person by partial name, deciding whether
  two issues are "similar".
- **Free-text formatting** — turning structured findings into prose someone reads.

Everything else — extraction, aggregation, enumeration, verification, reporting,
file-shuffling — is code.

**Without this boundary the rule does damage.** Someone eventually tries to
mechanise `/map-site`, and produces maps generated from the DOM with no human
correction and no gotchas — losing the one surface
`INFORMATION_MINIMALISM.md` calls primary.

## The ratchet: explore agentically, then mechanise

New work starts `agentic` because nobody knows the shape yet. Once it stabilises,
promote the mechanical parts into a script and downgrade the `mode`.

The repo's worked example: `get_gateway_status_table.py` states that it
"replaces the DOM scrape of admin-gateway-monitoring". The gateway sweep was
explored by an agent driving the UI, then became an API call. Same answer,
without a browser.

Record the promotion in the workflow's companion `.md`, so the next person can
see the path rather than re-deriving it.

## Worked examples in this repo

| Was | Became | Why it was the right move |
|---|---|---|
| Agent scraping the gateway-monitoring DOM | `get_gateway_status_table.py` | Whole fleet in one API call; survives UI redesigns |
| Agent walking an org chart page by page | a `subtree.js` helper | Graph traversal is an algorithm, not a judgement |
| `/list-workflows` parsing 14 YAMLs per question | `scripts/inventory.py` → `docs/inventory.md` | Enumeration is mechanical; the skill now presents a generated answer |
| Reading every doc to find drift | `scripts/check.py` | 7 of 9 findings in the 2026-08-05 audit were mechanically detectable |

## Prefer a script over fan-out

Where work is mechanical, a script beats parallel sub-agents on every axis: it is
faster, it costs nothing, and it runs identically on a host with no sub-agent
concept. Reach for fan-out only when each item genuinely needs judgement.

## This is the same lever as host-independence

A script runs identically under Claude, Codex, or a plain Python host. **Every
task moved out of agent reasoning and into code is also a task that stops
depending on which agent you brought.** Code-over-LLM and harness-independence
are not competing constraints — they pull the same direction.

## Applying it

- Writing a workflow step? If the data is reachable from the site's API, use
  `action: script` (`schema/workflow.yaml`).
- Writing a skill? If a step is "read all X and summarise", ask whether a script
  should produce the summary and the skill should present it.
- Adding a check? A check that can fail mechanically belongs in a script that
  exits non-zero — not in a doc asking someone to remember.
- Building a sub-agent? Confirm a script could not do it first
  (`subagents/README.md`).

## See also

- [INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) — whether to document
- [KNOWLEDGE_PLACEMENT.md](KNOWLEDGE_PLACEMENT.md) — where a fact belongs
- [INTERFACE.md](INTERFACE.md) — `mode`, and who executes a workflow
