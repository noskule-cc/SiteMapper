# Wiki

The software documentation — how SiteMapper functions (user perspective),
architecture, domain concepts — lives in the repository's GitHub wiki.
What belongs there vs. `docs/` is defined in
[DOCUMENTATION_GUIDELINES.md](DOCUMENTATION_GUIDELINES.md).

## Location

- **GitHub:** <https://github.com/noskule-cc/SiteMapper/wiki>
- **Git URL:** `https://github.com/noskule-cc/SiteMapper.wiki.git`
- **Local clone:** `../SiteMapper.wiki/` (sibling to this repository)
- **Index file:** `_Sidebar.md` — the wiki navigation; every page is listed there

## Usage

```bash
# Clone (if not already present)
git clone https://github.com/noskule-cc/SiteMapper.wiki.git ../SiteMapper.wiki

# Edit, then
cd ../SiteMapper.wiki
git add . && git commit -m "Document feature X" && git push
```

The wiki is **public**, like the repository. Nothing deployment-specific goes
in it — deployment documentation lives in that deployment's private map
repository.
