# Knowledge Placement — where a fact belongs

`INFORMATION_MINIMALISM.md` answers **whether** to write something down.
This answers **where it goes**, so the same fact does not end up in three places
disagreeing with itself.

The rule is one line:

> **A fact that is true of the project belongs in the repo. A fact that is true of
> one machine or one person belongs in the agent's own memory store. Nothing
> belongs in both.**

## The decision

Ask: *would this still be true for a different person, on a different machine,
cloning this repo tomorrow?*

**Yes → repo.** Pick the most specific home that already exists:

| The fact is about… | It goes in… |
|---|---|
| How one page behaves; a trap that breaks automation | `sites/<site>/pages/<page>.yaml` → `gotchas` |
| An element that exists, and when it doesn't | that page's `elements` (+ `states: [capability-dependent]`) |
| An API, its auth, why a path is blocked or parked | `sites/<site>/scripts/README.md` |
| Base URL, auth model, which scripts a site has | `sites/<site>/site.yaml` |
| Contact data, environment, form-submission authorization | layered `settings:` — `config.yaml` → `site.yaml` → page |
| What a workflow does and why its branches differ | the workflow's sibling `<workflow>.md` |
| The shape of a YAML file | the relevant `schema/*.yaml`, as comments |
| A standing rule every session must follow | the deployment's `docs/guardrails.md` |
| A decision not yet made | a **GitHub issue** — see `issue-tracker.md` |
| What a run found | `results/<workflow>.<YYYY-MM-DD>.md` |

**No → the host agent's private memory store**, outside the repo (Claude Code
keeps one under `~/.claude/…/memory/`; other hosts have their own). That means:
install paths, local auth state, OS quirks of *your* setup, and "where we left
off".

**Unsure → repo.** A fact in the repo is reviewable and gets corrected. A fact in
memory is invisible to everyone else and rots quietly.

## Why memory is the weaker home

- **It is not shared.** Memory is keyed to the machine, the launch directory and
  the specific agent. A teammate — or you from a different directory, or the same
  work under a different agent — never sees it.
- **It cannot be pointed at the repo.** Hosts deliberately refuse to let a
  checked-in config redirect the memory directory (Claude Code ignores
  `autoMemoryDirectory` in `.claude/settings.json`), because memory auto-loads
  into context and a repo that could redirect it could plant standing
  instructions in any agent that clones it. Committing a memory folder does not
  make it load for anyone.
- **It is not reviewed.** No diff, no PR, no lint.
- **It duplicates silently.** Every fact promoted here started as a memory that had
  already drifted from the repo copy.

Memory is a **staging area**, not a destination. When a memory turns out to be true
of the project, promote it and delete the memory — do not leave both.

## For agents

1. **Read the repo before answering from memory.** A recalled memory reflects what
   was true when it was written. If it names a file, flag, or element, verify it still
   exists.
2. **When the repo and a memory disagree, the repo wins.** Then fix the memory.
3. **Before saving a memory, run the table above.** If a row fits, write it there
   instead — that is not extra work, it is the work.
4. **Never split one fact across both.** Either the repo states it, or memory does.

## Worked examples

| Fact | Home | Why |
|---|---|---|
| A detail page has an "Enable new design" toggle; with it off, the mapped tabs do not exist | that page's `gotchas` | Breaks any workflow, for anyone |
| Headless auth is blocked three ways, so the readout runs browser-driven | that site's `scripts/README.md` | Site-wide constraint + a parked-code rationale |
| Dev forms may be submitted with the standard contact | `settings.policy.safe_to_submit_forms` | Machine-readable beats prose |
| `ado` is installed at user scope with `--authentication azcli`; `az` must be on the Machine PATH | memory | True of this machine only |
| An MCP server may touch one project's wiki only | the deployment's `docs/guardrails.md` | A standing rule for every session, on every host |

## See also

- [INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md) — whether to document at all
- [AGENTS.md](AGENTS.md) — entry point and situational references
- [GUARDRAILS.template.md](GUARDRAILS.template.md) — how to write the standing safety rules
- [issue-tracker.md](issue-tracker.md) — open decisions live as issues
