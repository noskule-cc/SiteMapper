# Skill: deploy-dashboard

Publish a dashboard to its artifact — the publish half of the page's deploy
button. For the **framework** page, **the normal path is automatic:** the
`deploy-dashboard` cloud routine republishes the standing artifact on every
push to `noskule-cc/SiteMapper` (GitHub webhook) and daily at 03:00 UTC as a
safety net (<https://claude.ai/code/routines/trig_01KVFkR31fCPHq466Q88Tse2>).
Use this skill for an out-of-band deploy of uncommitted state, when the
routine failed — or for a **map repository's** page, which only ever deploys
manually, through here (#34).

Artifact publishing needs an agent session with the Artifact capability —
plain headless `claude -p` cannot do it by design; the dashboard's deploy
button therefore builds and hands off to a session.

**Which session sees the command:** skills are discovered from the repo a
session starts in. This framework repo's command publishes the framework
page. A map repository carries its own `/deploy-dashboard` wrapper
(templated in `data/.claude/skills/`) that targets itself — publishing a map
repo's page happens from a session started in that repo. Either command is
just packaged instructions: any session can be asked to do the publish.

## Guardrail — read before anything else

Two targets, never crossed (docs/PERMISSIONS.md, "Dashboard deploy"):

- **Framework page → the standing URL** registered in `docs/JOBS.md`. Public
  content, public repo links.
- **A map repository's page → that repository's OWN private artifact**,
  registered in its `config.yaml` as `dashboard: artifact_url:`. It carries
  tenant names, identifiers and internal detail, so: **never** publish it to
  the framework's standing URL, **never** share the artifact (it stays
  private to the operator's account — sharing is the line), and publish only
  when the user asked for this deploy — the serve endpoint's consent click,
  or the request in this conversation. Redeploying does not scrub version
  history; a wrong publish stays visible in the artifact's history.

If the prepared build's title does not match the tree you were asked to
deploy, STOP and say so.

## Sequence

1. **Get the build.** Use `<tree>/.runner/deploy/dashboard-artifact.html` if
   the deploy button just prepared it (it renders fresh on every press);
   otherwise build it:
   `python scripts/overview.py [--root <maps>] --links github --fragment --out <tree>/.runner/deploy/dashboard-artifact.html`
2. **Look at what you publish.** Read the file; confirm the title matches the
   intended tree, all links are absolute into that tree's repo, and — for the
   framework page — nothing deployment-specific is present.
3. **Publish to the registered URL** (never create a second artifact for a
   tree that has one; the link must not rot): favicon 🗺️ (stable), the
   registered description, a short version label. **Map repository, first
   publish:** no URL is registered yet — publish as a new artifact titled
   after the repo. **Map repository, every publish:** record what was
   published so the dashboard's staleness chip works (#36) — copy `hash` and
   the date from `.runner/deploy/build-info.json` (written next to the
   build) into the map repo's `config.yaml`:

   ```yaml
   dashboard:
     artifact_url: https://claude.ai/code/artifact/<id>
     published_hash: sha256:<hash from build-info.json>
     published_at: <YYYY-MM-DD>
   ```

   A version conflict means another session published meanwhile: look at
   what is live first; replacing the same tree's page is routine, replacing
   anything else needs the user's explicit go-ahead.
4. **Confirm** the URL back to the user. The replaced version stays in the
   artifact's version history. For a map repository, restate: private, do not
   share.

## When

After sites/workflows/projects change and the shared page should show it —
see `docs/JOBS.md`. The artifact is a snapshot; the standing URL is only as
current as the last deploy.
