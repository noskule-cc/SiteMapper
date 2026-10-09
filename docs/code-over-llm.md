# Code Over LLMs

> **Do everything that can be done in code, in code. Reach for a script wherever
> one can do the job.**

It is faster, it is deterministic, it costs no tokens, it runs on every host, and
it does not break when a UI changes.

**And it keeps the LLM free to orchestrate.** Every step an LLM executes by hand
fills its context and its attention with mechanics: clicks, waits, retries,
output to re-read. That is attention it no longer has for the parts only it can
do: noticing a wrong assumption, weighing a decision, asking the human the right
question. The less manual work an LLM carries, the better it orchestrates.

Evidence (2026-09-15, a helpdesk triage run in a deployment's map repository):
closing ~30 tickets by hand took ~30 near-identical browser calls, most of the
session's context. The mistakes of that run were in the manual parts (guessed
locators, a misread DOM value, an overstated check), while the decisions that
needed judgement fit into a handful of messages.

This is SiteMapper's third governing principle, alongside
[INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) (*whether* to write
something down) and [knowledge-placement.md](knowledge-placement.md) (*where* it
goes). This one answers **who executes**. It is a project rule, not part of the
aiDocs standard — the standard's nearest neighbour is the layer model's
"derivable content is generated, non-derivable content is curated"
([DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md)), which says the same
thing about documentation only. Here it governs the work itself.

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
[INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) calls primary.

## The ratchet: explore agentically, then mechanise

New work starts `agentic` because nobody knows the shape yet. Once it stabilises,
promote the mechanical parts into a script and downgrade the `mode`.

**The trigger is repetition, not a feeling that the work has settled.** The LLM
may do something by hand the first time, to find its shape: a script written
before the first run is built on guesses. From the second time the same
manual sequence comes up (the second record in a loop, the second run of a
workflow) it is a script, and the LLM calls the script and handles only what
the script reports as a deviation. Explore and decide by LLM; repeat by code.

The mechanism is `action: script` (`schema/workflow.yaml`): a step declares a
script from `sites/<site>/scripts/`, the runner executes it and captures its
`--json` stdout. A DOM sweep an agent explored by hand becomes one API call —
same answer, without a browser, and it survives the next UI redesign.

Record the promotion in the workflow's companion `.md`, so the next person can
see the path rather than re-deriving it.

## Worked examples in this repo

| Was | Became | Why it was the right move |
|---|---|---|
| Agent walking a hierarchy page by page | a site script doing the traversal | Graph traversal is an algorithm, not a judgement |
| `/list-workflows` parsing every workflow YAML per question | `scripts/inventory.py` → `docs/inventory.md` | Enumeration is mechanical; the skill now presents a generated answer |
| Reading every doc to find drift | `scripts/check.py` | 7 of 9 findings in the 2026-08-05 audit were mechanically detectable |
| An LLM deciding whether a mapped page still matches | the runner's fingerprint watch (`scripts/run.py`) | A URL pattern plus one anchor element is a comparison, not a judgement |

## Prefer a script over fan-out

Where work is mechanical, a script beats parallel agents on every axis: it is
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
- Building an agent? Confirm a script could not do it first
  ([extending.md](extending.md)).

## See also

- [INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) — whether to document
- [knowledge-placement.md](knowledge-placement.md) — where a fact belongs
- [interface.md](interface.md) — `mode`, and who executes a workflow
