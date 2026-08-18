# Host Bindings

The skill docs describe what to do in terms of **capabilities** — navigate, read
the page, click, type. This file maps those capabilities onto the concrete tools
a given host provides. It is the only place tool names appear.

That split is what makes the skills portable: a host without Claude-in-Chrome
follows the identical instructions and substitutes its own column here.

## Browser capabilities

| Capability | What it must do | Claude Code (`claude-in-chrome` MCP) |
|---|---|---|
| **open session** | Get or create the agent's own tab — never reuse a tab the user is working in | `tabs_context_mcp` (`createIfEmpty: true`), `tabs_create_mcp`, `tabs_close_mcp` |
| **navigate** | Go to a URL in that tab | `navigate` |
| **read page** | Structured DOM/accessibility tree of the current page | `read_page` |
| **read text** | Visible text content, for reading values and tables | `get_page_text` |
| **find** | Locate elements by a semantic locator, returning matches | `find` |
| **click** | Click a located element | `find` + `computer` (`click`) |
| **type** | Enter a value into an input or select an option | `form_input` |
| **press key** | Send a keyboard key (`Escape`, `Enter`) without changing field state | `computer` (`key`) |
| **screenshot** | Capture the viewport as an image | `computer` (`screenshot`) |
| **read console** | Read browser console output, for diagnosing a failed step | `read_console_messages` |

## Non-browser capabilities

| Capability | What it must do | Claude Code |
|---|---|---|
| **run script** | Execute a site script from `sites/<site>/scripts/`, capture stdout (JSON with `--json`) | `Bash` / `PowerShell` |
| **read/write files** | Read and write maps, workflows and results | `Read`, `Write`, `Edit`, `Glob`, `Grep` |
| **fan out** | Run independent read-only work in parallel *(optional — see below)* | `Agent` / subagents |

## Optional capabilities

**Fan-out is an optimization, never a requirement.** A host with no subagent
concept runs the same work sequentially and must produce an identical `result`.
If a workflow's correctness ever depends on parallelism, that is a bug in the
workflow, not a missing host feature. See `INTERFACE.md` → Bindings.

Where work is mechanical, prefer a **script** over fan-out: it is faster than
subagents and runs on every host.

## Adding a host

1. Add a column to the tables above with that host's tool names.
2. Add a pointer file at the repo root that the host reads on startup (see
   `CLAUDE.md`, `CODEX.md`, `.cursorrules`, `.github/copilot-instructions.md`) —
   it must do nothing but point at `docs/AGENTS.md`.
3. If the host has a skill/agent registry, add thin bindings that point at
   `docs/skills/` and `docs/subagents/`. Never copy instructions into them.
4. Verify against `sites/sitemapper-demo` — the one mapped site with no
   deployment-specific auth.

**Neutral means portable, not minimal.** Do not simplify a skill doc because one
host lacks a capability. Describe the work at full fidelity and record the
difference here.
