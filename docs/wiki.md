# Wiki Documentation

The software documentation — how SiteMapper *functions* (user perspective),
architecture, domain concepts — is maintained in the repository's GitHub wiki.
What belongs in the wiki vs. `docs/` is defined in
[DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md).

## Location

```
../SiteMapper.wiki/     # Wiki repository (sibling to main project)
```

**Index file:** `_Sidebar.md` — contains the wiki navigation structure and
page listing.

The wiki is a Git repository cloned alongside the main project:

- **GitHub URL:** `https://github.com/noskule-cc/SiteMapper.wiki.git`
- **Web view:** <https://github.com/noskule-cc/SiteMapper/wiki>
- **Local path:** `../SiteMapper.wiki/` (relative to project root)

## Structure

The wiki is organized into two pillars — **Content** (user/domain-facing) and
**Architecture** (dev/system) — with a section prefix on every page.

**Content**

| Prefix      | Purpose                                        | Example Pages                                        |
|-------------|------------------------------------------------|------------------------------------------------------|
| `concepts-` | Domain concepts: what the building blocks are  | `concepts-site-map.md`, `concepts-workflow.md`, `concepts-framework-vs-deployment.md` |
| `features-` | Shipped behavior: what the system does for you | `features-drift-detection.md`, `features-deterministic-tests.md` |

**Architecture**

| Prefix          | Purpose                   | Example Pages                                            |
|-----------------|---------------------------|----------------------------------------------------------|
| `architecture-` | System design, dev-facing | `architecture-overview.md`, `architecture-runner.md`, `architecture-permissions.md` |

**File naming:** `<prefix>-<topic>.md`. `_Sidebar.md` groups the pages under
the two pillars.

Every page follows the behavior-first structure ("What It Does" / "Why It
Matters" / "Bindings") from
[DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md).

## Issue Tracker Alignment

Feature-area labels map to wiki page prefixes — when closing an issue that
adds significant functionality, update the wiki page its label maps to. See
the **Wiki Mapping** table in
[issue-tracker.md](issue-tracker.md#wiki-mapping) for the authoritative
label → page mapping.

## Usage

```bash
# Clone wiki (if not already present)
git clone https://github.com/noskule-cc/SiteMapper.wiki.git ../SiteMapper.wiki

# Navigate to wiki
cd ../SiteMapper.wiki

# Edit and commit changes
git add . && git commit -m "Document feature X"
git push
```

## Content Guidelines

See [DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md) for what
belongs in the wiki vs. the `docs/` folder.

The wiki is **public**, like the repository. Nothing deployment-specific goes
in it — no customer names, identifiers, hostnames or fleet data. Deployment
documentation lives in that deployment's own private map repository.

---

**Last Updated:** 2026-08-19
