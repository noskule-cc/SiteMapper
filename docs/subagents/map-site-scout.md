# map-site-scout

Drafts a page-map **proposal** for one page — a read-only reconnaissance the
human then reviews inside a normal `/map-site` session. Not an agent-ified
`/map-site`: discovery is human-in-the-loop by design, because the
corrections and gotchas a user contributes cannot be derived from the DOM
(`CODE_OVER_LLM.md`, the boundary). A sub-agent cannot converse, so it must
never own discovery — it only takes the mechanical first pass off the
human's clock.

## Responsibilities

- Visit the one page it is given (already-authenticated session, no logins)
- Draft `page:` YAML per `schema/page.yaml`: purpose, url_pattern with
  `{placeholders}`, candidate elements with semantic names and the most
  stable locator it can see (prefer `data-testid`/`aria-label` over `text`)
- Flag what it is unsure about (`# scout: unsure —` comments in the draft)
- Return the draft as text — **never write it into `sites/`**

## Rules

- Read-only: no clicks that mutate, no form submissions, no file writes.
  The draft becomes a map only after the human reviews it in `/map-site`.
- No gotchas invented. A gotcha states observed non-obvious behavior; the
  scout records only what it actually observed, and leaves the section with
  a `# scout: to be filled by the human` marker otherwise.
- One page per invocation. Fan out across pages only when they are
  read-only reachable and session-neutral (`subagents/README.md`).

## Output

The draft YAML, plus a short list of open questions for the human
("two elements match 'Save' — which is canonical?"). That list is the
point: it is the agenda for the human half of the session.

## Checklist

- [ ] Page visited read-only; nothing mutated
- [ ] Draft follows `schema/page.yaml`, placeholders for dynamic ids
- [ ] Uncertainties marked, questions listed
- [ ] Draft returned as text; `sites/` untouched
