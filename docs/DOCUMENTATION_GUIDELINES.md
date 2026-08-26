# Documentation Guidelines

## Core Principle

> Document what a seasoned developer or LLM would need to **reconstruct** the project on the same platform, or **translate** it to another platform — skip what they already know.

## Information Minimalism

Before adding documentation, run the 3-question test — *needed? obvious from code? duplicate?* — defined once in [INFORMATION_MINIMALISM.md](INFORMATION_MINIMALISM.md). Fail any question → don't write it.

### What to Document

| Type | When | Example |
|------|------|---------|
| **Behavioral intent** | Expected outcome matters | `// Session survives rotation — user expects no data loss` |
| **Constraint rationale** | A limit/threshold exists | `// 500ms debounce — faster causes UI jank on low-end devices` |
| **Domain knowledge** | Values a dev wouldn't know | `// RMSSD typically 20-200ms for healthy adults` |
| **Non-obvious "why"** | Decision isn't self-evident | `// Room over DataStore: need relational queries for history` |
| **Quirks/workarounds** | Platform or device-specific | `// PLATFORM: Coospo BLE requires 500ms post-connect delay` |
| **Complex behavior** | Signature doesn't tell the story | `@param windowMillis Sliding window; resets on new session` |

### What to Skip

- What the code does (read the code)
- Obvious parameters (`@param id The ID`)
- Standard patterns the platform expects (ViewModel lifecycle, Composable structure)
- Commented-out code (delete it)

### Platform-Specific Marker

Use one marker for platform-specific quirks that need evaluation when porting:

```kotlin
// PLATFORM: Coospo BLE requires 500ms post-connect delay before notifications work
```

Everything *without* this marker is implicitly cross-platform intent. No separate INTENT marker needed — if it's not platform-specific, it's a requirement.

## Documentation Levels

| Location | Contains | Examples |
|----------|----------|----------|
| **Code** (docstrings, comments) | Intent, rationale, edge cases, API behavior | Function docs, inline "why" comments |
| **/docs folder** | Developer operations, platform guides, contribution workflow | Build, test, run, release, agent behavior |
| **Wiki** | How software functions (user perspective), architecture, domain concepts | Features, behavior, system design |

## Doc-System Layer Model

The documentation set is partitioned by **content, not audience**. Every audience (LLM, developer, user) follows references into every source, so audience cannot be the partitioning key — instead, each content type has exactly one home and everything else links to it (single source of truth).

**Two content axes:**

| Axis | Home | Organized by | Answers |
|------|------|--------------|---------|
| **Feature/behavior** | Wiki | user-facing features | "What does the software do, and why?" |
| **Operations/code** | `/docs` | developer operations and code structure | "How do I build, test, navigate, and release?" |

Within the axes, every file belongs to exactly one **layer**, which decides who maintains it and what verifies it:

| Layer | Files | Maintained by | Verified by |
|-------|-------|---------------|-------------|
| **Fixed standard** | UPPERCASE files | upstream aiDocs, via `/update-aidocs` | `check-docs.py` |
| **Curated** | filled templates and lowercase project files | the project, by hand | `check-docs.py` + `validation-docs` |
| **Generated** | code-index reports, code maps | tooling in `docs/tools/` — never hand-edited | regeneration |
| **Wiki** | wiki pages | the project, by hand | `validation-docs` (wiki scope) |

**Derivable content is generated, non-derivable content is curated.** If tooling can produce it from code (structure overviews, dependency maps), don't hand-write it — it fails Q2 of the minimalism test and rots. Hand-curate only what code cannot reveal (rationale, feature→code mapping, failure modes).

**Feature map vs wiki:** `feature-map.md` (curated, in `/docs`) is a *routing table* — feature → entry point, gotchas, failure-mode hints — for triage by agents working in-repo. The wiki feature page owns behavior and rationale; the map links to it and never restates it, and the wiki never carries entry points.

How the pieces route and verify each other:

```mermaid
flowchart TB
    CODE["Code<br/>intent comments, docstrings"]
    subgraph DOCS["docs/ — operations/code axis"]
        FIXED["Fixed standard (UPPERCASE)<br/>AGENTS, INDEX, guidelines"]
        CURATED["Curated (lowercase)<br/>development, testing, ..."]
        GENERATED["Generated<br/>code-index reports"]
    end
    subgraph WIKI["Wiki — feature/behavior axis"]
        PAGES["features-*, architecture-*,<br/>domain pages"]
    end
    FIXED -->|"routes: INDEX,<br/>situational refs"| CURATED
    CURATED -->|"behavior?<br/>link, don't restate"| PAGES
    PAGES -->|"implementation?<br/>link back"| CURATED
    GENERATED -.->|"regenerated from"| CODE
    CHECK["check-docs.py (CI)"] -.->|verifies| DOCS
    VDOCS["validation-docs"] -.->|verifies| DOCS
    VDOCS -.->|verifies| WIKI
    VLLM["validation-llm"] -.->|"tests entry path"| FIXED
```

### Code Documentation

Apply Information Minimalism. Document only what isn't obvious from reading the code.

**Technical Debt:**

```kotlin
// TODO: Brief description of what's needed
// TODO(#123): With issue reference if tracked
```

### /docs Folder

Documents platform-specific setup, development, and testing.

**File Naming:**

- **UPPERCASE** — Fixed standard files, kept as-is in every project (e.g. `AGENTS.md`, `DOCUMENTATION_GUIDELINES.md`)
- **lowercase** — Project-specific content files (e.g. `development.md`, `issue-tracker.md`)
- **`*.template.md`** — Templates to copy and fill per project (e.g. `coding-guidelines.template.md`); the filled copy drops the `.template` suffix
- **Skills and agents** live in `.claude/` with lowercase hyphenated names, registered in `skills-and-agents.md`

The casing doubles as the update contract: `/update-aidocs` may overwrite UPPERCASE and `*.template.md` files (upstream-owned) but never lowercase project files.

**Before writing:** Check `INDEX.md` to avoid duplication
**After writing:** Update the index

### Wiki

Documents how software **functions** (user perspective), not how code **works** (implementation).

**File Naming:** Section prefix + descriptive name

```
architecture-overview.md
features-heart_rate_zones.md
devices-ble-polar.md
```

**Before writing:** Check wiki index to avoid duplication
**After writing:** Update the sidebar

#### Structure: Behavior First, Then Platform

Wiki pages separate **what the feature does** (platform-agnostic) from **how it's implemented** (platform-specific):

```markdown
# Device Connection Management

## What It Does
Users pair heart rate devices once. The app remembers paired devices and
reconnects automatically on launch. Manual disconnect prevents auto-reconnect
until user explicitly reconnects.

Connection states: Disconnected → Connecting → Connected → Disconnected

## Why It Matters
- Auto-reconnect saves time for daily workouts
- Respecting manual disconnect prevents unwanted battery drain
- Clear states let UI show accurate feedback

## Android Implementation

### Key Components
| Component | Responsibility |
|-----------|---------------|
| `DeviceManager` | Coordinates BLE and WearOS sources |
| `BleDeviceSource` | Android BLE scanning and GATT connections |

### Quirks
- BLE scanning requires location permission (Android platform requirement)
- Some devices (Coospo) need post-connect delay before notifications work

## iOS Implementation
*To be documented when iOS development begins.*
```

If someone reads only "What It Does" and "Why It Matters", they have everything needed to implement the feature on any platform.

## Diagrams

Use [Mermaid](https://mermaid.js.org/) fenced code blocks — GitHub renders these natively in repo markdown and wiki pages. Apply Information Minimalism: only add diagrams that pass the 3-question test.

**Good fit:** state machines, multi-component interactions, data flow across layers, DB schema.

| Mermaid type | Use for |
|---|---|
| `stateDiagram-v2` | Lifecycle, connection states |
| `sequenceDiagram` | Component interactions over time |
| `flowchart` | Decision logic, branching workflows |
| `erDiagram` | Database schema |
| `classDiagram` | Architecture overview (simplified) |

**Conventions:**

- Place inline in the markdown file where relevant
- Add a brief caption sentence before each diagram
- Keep under ~15 nodes — split or simplify if larger
- **Fallback to SVG** in `docs/images/` for visuals Mermaid can't express

## Examples

**Good** — rationale, platform quirk, domain knowledge:

```kotlin
// 500ms debounce — faster causes UI jank on mid-range devices (Pixel 4a, Galaxy A52)
// PLATFORM: Coospo H808S requires 500ms post-connect delay; Polar H10/Garmin work immediately
// RMSSD typically 20-200ms for healthy adults; outside range → likely sensor noise
```

**Bad** — obvious or mechanics-only:

```kotlin
// Get the heart rate        → obvious from name
// Delays for 500ms          → says what, not why
// @param userId The user ID → obvious parameter
```

## Periodic Validation

Invoke the `validation-docs` agent (`.claude/agents/validation-docs.md`) before major releases or quarterly.
Invoke the `validation-llm` agent (`.claude/agents/validation-llm.md`) after major restructuring or new project setup.
Applies to both docs/ and wiki/.

---

**Last Updated:** 2026-08-26
