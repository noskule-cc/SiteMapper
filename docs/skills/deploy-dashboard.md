# Skill: deploy-dashboard

Publish the **framework** dashboard to its standing shareable URL — the
manual path. **The normal path is automatic:** the `deploy-dashboard` cloud
routine republishes the standing artifact on every push to
`noskule-cc/SiteMapper` (GitHub webhook) and daily at 03:00 UTC as a safety
net (<https://claude.ai/code/routines/trig_01KVFkR31fCPHq466Q88Tse2>). Use
this skill only for an out-of-band deploy of uncommitted state, or when the
routine failed.

Artifact publishing needs an agent session with the Artifact capability —
plain headless `claude -p` cannot do it by design; the dashboard's deploy
button therefore builds and hands off to a session.

## Guardrail — read before anything else

**Framework page only, ever.** A deployment's dashboard is never published to
a shareable URL: it carries tenant names, identifiers and internal detail,
and it is served locally (`scripts/serve.py --root <maps>`) — that is its
home. If the working tree or the prepared build is a map repository's page
(title anything other than the framework's), STOP and say so. The serve
endpoint refuses map repositories for the same reason.

## Sequence

1. **Get the build.** Use `.runner/deploy/dashboard-artifact.html` if the
   deploy button just prepared it (it renders fresh on every press);
   otherwise build it:
   `python scripts/overview.py --links github --fragment --out .runner/deploy/dashboard-artifact.html`
2. **Look at what you publish.** Read the file; confirm the title is the
   framework's, the header carries the "shareable copy" badge, all links are
   absolute into the public repo, and nothing deployment-specific is present.
3. **Publish to the standing URL** — registered in `docs/JOBS.md` (never
   create a new artifact; the standing link must not rot):
   favicon 🗺️ (stable), the registered description, a short version label.
   A version conflict means another session published meanwhile: look at
   what is live first; replacing a *framework* page is routine, replacing
   anything else needs the user's explicit go-ahead.
4. **Confirm** the URL back to the user. The replaced version stays in the
   artifact's version history.

## When

After sites/workflows/projects change and the shared page should show it —
see `docs/JOBS.md`. The artifact is a snapshot; the standing URL is only as
current as the last deploy.
