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

## Session hygiene: one tab, and why

**A run uses ONE tab.** Not one per site — one per session, navigated between
sites. Every other tab in that window is throttled by the browser and will make
a run fail in ways that look like broken page maps.

Measured on Windows Chrome, 2026-09-18:

| Situation | `document.visibilityState` | Usable |
|---|---|---|
| only tab in its window, window in the background, **no OS focus** | `visible` | **yes** — clicks, dialogs and timers all work |
| second tab of the same window, not the active one | `hidden` | no |
| window minimised or fully covered | `hidden` | no |

So the window does **not** need to be clicked or focused. It only has to stay
un-minimised and not fully covered, with the agent's tab active in it. A
synthetic click gives the page focus by itself (`document.hasFocus()` flips to
true on the first click).

What a hidden tab does: timers are clamped, so a page-side `setTimeout` loop
stops making progress; dialogs stop reacting to clicks; scripts hit the host's
45 s evaluate timeout; a batch of actions dies halfway. None of that reports
itself as a visibility problem, which is why it is worth checking up front.

Rules that follow:

- **Open a second tab only when two pages must be live at once**, and expect the
  inactive one to be dead while it is. Cross-site workflows should instead be
  **phased**: do all the work on site A, then navigate the same tab to site B.
- **Check visibility at the start of every batch that clicks or types.** Fail
  fast with a named cause rather than timing out. The guard is one line:
  `if (document.visibilityState !== 'visible') throw new Error('TAB HIDDEN')`.
- **Prefer host-side waits over page-side sleeps.** A `computer` wait runs in the
  host and is unaffected by throttling; `await new Promise(r => setTimeout(...))`
  inside the page is not. Keep page-side waits short and poll for a condition.
- **After running a script in the page, take a screenshot or zoom before the next
  click.** Evaluating script takes focus from the page for a moment: a click
  issued immediately afterwards lands but does nothing. A zoom in between fixes
  it (observed on Vaadin and Ember apps alike, 2026-09-17).
- **Close the tabs a run opened** when it ends, so the next session starts with
  one tab.

## Non-browser capabilities

| Capability | What it must do | Claude Code |
|---|---|---|
| **run script** | Execute a declared script from `sites/<site>/scripts/` or `projects/<project>/scripts/`, capture stdout (JSON with `--json`) | `Bash` / `PowerShell` |
| **read/write files** | Read and write maps, workflows and results | `Read`, `Write`, `Edit`, `Glob`, `Grep` |
| **fan out** | Run independent read-only work in parallel *(optional — see below)* | `Agent` / subagents |

## Optional capabilities

**Fan-out is an optimization, never a requirement.** A host with no subagent
concept runs the same work sequentially and must produce an identical `result`.
If a workflow's correctness ever depends on parallelism, that is a bug in the
workflow, not a missing host feature. See [interface.md](interface.md) →
Bindings.

Where work is mechanical, prefer a **script** over fan-out: it is faster than
agents and runs on every host.

## Adding a host

The steps are in [extending.md](extending.md) → "Add a host". The part that
belongs here is the column: one per host, in the tables above.

**Neutral means portable, not minimal.** Do not simplify a skill because one
host lacks a capability. Describe the work at full fidelity and record the
difference here.
