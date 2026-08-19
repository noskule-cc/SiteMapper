# Jobs

Runnable tasks for keeping the repo healthy. This is the central registry —
check here to see what is available before writing something new. Adopted from
the aiDocs framework (`docs/tools/JOBS.md`).

Per [CODE_OVER_LLM.md](CODE_OVER_LLM.md): a job that can run mechanically is a
script; only jobs needing judgement are skills or sub-agents.

## Available Jobs

| Job | Command | Output | Executor |
|-----|---------|--------|----------|
| Consistency checks | `python scripts/check.py` | pass/fail per check, non-zero exit on failure | script |
| Regenerate views | `python scripts/inventory.py` | `docs/inventory.md` + `docs/overview.html` | script |
| Staleness check | `python scripts/inventory.py --check` | non-zero exit when a generated view is stale | script |
| Headless workflow run | `python scripts/run.py <workflow> --param k=v` | a `result` object (`--json` for machine-readable) | script |
| Map drift check | `/verify-map <site>` | FOUND / MISSING per element | skill ([verify-map.md](skills/verify-map.md)) |
| Deterministic UI test | `/test <workflow>` | a `result` object + `results/` record | skill ([test.md](skills/test.md)) |
| LLM docs test | invoke `validation-llm` | knowledge-test report | sub-agent ([subagents/validation-llm.md](subagents/validation-llm.md)) |

`check.py` and `inventory.py` accept `--root <path>` to run against a separate
map repository.

## When to Run

| After... | Run... |
|----------|--------|
| Any change, before committing | `python scripts/check.py` |
| Adding/removing a site, page, workflow or project | `python scripts/inventory.py` (then `check.py`) |
| A workflow step fails to find a mapped element | `/verify-map` on that site |
| Changing a deterministic workflow | `/test` it |
| Restructuring the documentation | `validation-llm` |

---

**Last Updated:** 2026-08-19
