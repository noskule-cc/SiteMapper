# Project Brief: LLM-Assisted Site Mapping for Web Automation

## Goal
Build a system that lets Claude (in Chrome or similar agent) navigate conventional, non-AI-optimized web apps quickly — by pre-analyzing them once with human-in-the-loop discovery, then reusing the resulting map across sessions. Eliminates redundant DOM exploration and screenshot-heavy navigation.

## Core Concept
A **collaborative discovery phase** where LLM + human walk through a site together, producing a versioned, reloadable map of pages, elements, flows, and gotchas. Conceptually a modern Page Object Model, but built through guided conversation rather than hand-coded by an engineer.

## Key Design Decisions

**Map format**: YAML per page/app, capturing:
- Page purpose and URL
- Key elements with semantic locators (text, aria-label, role, `data-testid`)
- Named flows (sequences of steps for common tasks)
- Gotchas and non-obvious behavior (e.g. "Save stays active when form invalid", "Delete is soft-delete only")

**Locator strategy**: Prefer semantic anchors over CSS paths. Since user has admin access to target sites, sprinkling `data-testid` attributes is the gold standard for stability.

**Verification step**: Before trusting a saved map in a new session, do a quick "does element X still exist on page Y" sanity check to catch drift.

**Philosophy alignment**: Fits existing Information Minimalism approach — capture intent, rationale, and traps; skip mechanics the LLM can re-derive.

## Repo & Storage
Lives in **its own dedicated repo** (separate from `aiDocs`). One repo for site maps as a standalone project — likely one YAML file per target app, plus shared schema and tooling.

## Workflow
1. Discovery subagent walks site with user, asks targeted questions
2. User annotates and corrects in real time
3. Output: `site_map.yaml` per app, committed to the site-maps repo
4. Reload as a skill or paste at session start
5. Updates handled as PRs — same hygiene as other docs

## Sweet Spot vs. Limits
- **Best fit**: Stable internal admin tools where user controls the codebase
- **Poor fit**: Public consumer sites that A/B test their DOM frequently
- Maintenance is real — selectors drift, but admin-controlled sites stay stable

## Open Tooling Questions
- GitHub connector in claude.ai chat is attach-files only (not agentic). For autonomous read/write of the map repo, Claude Code + GitHub MCP is the right path — already part of existing Claude Code workflow.
- Discovery subagent could be built as a Claude Code subagent (similar to existing project manager subagent pattern).

## Suggested Next Steps
1. Define minimal viable YAML schema (1-2 example pages)
2. Pick one real admin site as pilot
3. Build discovery subagent prompt (questions to ask user during walkthrough)
4. Decide loader format: skill, paste-in context, or fetched from repo
