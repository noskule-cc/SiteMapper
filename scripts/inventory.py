#!/usr/bin/env python3
"""Generate docs/inventory.md — what exists in this repo, from the YAML itself.

Usage:
    python scripts/inventory.py                    # write all three views for this repo
    python scripts/inventory.py --check            # exit 1 if any is stale
    python scripts/inventory.py --root ../my-maps  # write THAT repo's views, into its tree
    python scripts/inventory.py --root data/SiteMapper --projects data/projects

All three files are GENERATED. Never hand-edit them; change the YAML and re-run.
`--check` is what keeps that true: a generated file nobody verifies is just
slower drift.

The collectors below are the single source every renderer reads: this file emits
the Markdown table view (for agents and git diffs), `overview.py` the browsable
HTML view (for humans), `libtree.py` the lib-tree.json a host draws (TeamOS).
One walk of the YAML, three presentations.

Why a script and not a skill: enumerating 16 workflows is mechanical, so an LLM
re-parsing them on every question is the wrong executor. See docs/code-over-llm.md.
"""
import argparse
import glob
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not installed. Run: python -m pip install pyyaml")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree  # noqa: E402

# The tree being inventoried — this script's own repo by default. set_root()
# repoints it at a separate map repository, which is what check.py --root does:
# the tooling lives in the framework repo, the maps it describes need not.
# PROJECTS is the projects tree, inside ROOT or beside it (scripts/tree.py).
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = tree.projects_root(ROOT)
OUT = os.path.join(ROOT, "docs", "inventory.md")


def set_root(root, projects=None):
    """Point the collectors at another tree, and OUT with them.

    OUT moves deliberately: a --root run inventories that repository, so its
    generated file belongs in ITS docs/, not in the framework's. Writing the
    framework's inventory.md from someone else's maps is exactly the leak the
    two-repo split exists to prevent.
    """
    global ROOT, PROJECTS, OUT
    ROOT = os.path.abspath(root)
    PROJECTS = tree.projects_root(ROOT, projects)
    OUT = os.path.join(ROOT, "docs", "inventory.md")
    return ROOT


def rel(p):
    """A path relative to ROOT, forward slashes; a project path beside ROOT
    reads '../projects/...', which is what a link from ROOT/docs needs."""
    return os.path.relpath(p, ROOT).replace("\\", "/")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def oneline(s, limit=110):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[: limit - 1] + "…" if len(s) > limit else s


# NO RUN HISTORY IS COLLECTED HERE, DELIBERATELY.
#
# Run output lives in the runs store (schema/run.yaml), outside every repository
# and outside this tree; nothing a run wrote is ever committed. So the views
# describe what exists to be run, not what ran. A reader of run history (a UI, a
# sweep) reads the runs store; these views link only to files that exist in
# every clone of the tree.


def phases(w):
    """Every step of a workflow, whichever phase it sits in."""
    out = []
    for phase in ("snapshot", "setup", "steps", "teardown"):
        out += [s for s in (w.get(phase) or []) if isinstance(s, dict)]
    return out


def _workflow_row(f, kind, owner, project=None):
    w = load(f).get("workflow") or {}
    sites = w.get("sites") or ([w.get("site")] if w.get("site") else [])
    steps = phases(w)
    tiers = w.get("tiers") or {}
    return {
        "kind": kind,
        "owner": owner,
        "group": "/".join(owner.split("/")[:-1]) if kind == "project" else "",
        "app": (project or {}).get("app") or "",
        "name": w.get("name") or os.path.basename(f)[:-5],
        "desc": oneline(w.get("description")),
        "purpose": oneline(w.get("description"), 320),
        "sites": [str(s) for s in sites],
        "tiers": {"required": [str(t) for t in (tiers.get("required") or [])],
                  "allowed": [str(t) for t in (tiers.get("allowed") or tiers.get("required") or [])],
                  "absent": {str(k): str(v) for k, v in (tiers.get("absent") or {}).items()}}
                 if tiers else {},
        "mode": str(w.get("mode") or "**—**"),
        "trust": str(w.get("trust") or ""),
        "effect": str(w.get("effect") or ""),
        "rollback": str(w.get("rollback") or ""),
        "verified_at": str(w.get("verified_at") or ""),
        "steps": len(w.get("steps") or []),
        "params": [str(p.get("name")) for p in (w.get("parameters") or [])
                   if isinstance(p, dict) and p.get("name")],
        "asserts": sum(1 for s in steps if s.get("action") == "assert"),
        # A *deterministic* workflow with assert steps is a test: it is run
        # with /test, which evaluates them and emits a result. An agentic
        # one asserts too but needs an LLM, so it goes through /run.
        # the run and test skills, step 2 (.claude/skills/{run,test}/SKILL.md).
        "is_test": (str(w.get("mode")) == "deterministic"
                    and any(s.get("action") == "assert" for s in steps)),
        "calls": sorted({str(s.get("script")) for s in steps if s.get("script")}),
        "companion": os.path.exists(f[:-5] + ".md"),
        "doc_path": rel(f[:-5] + ".md") if os.path.exists(f[:-5] + ".md") else "",
        "path": rel(f),
    }


def collect_workflows():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "sites", "*", "workflows", "*.yaml"))):
        rows.append(_workflow_row(f, "site", rel(f).split("/")[1]))
    for prel, pd_ in tree.iter_projects(PROJECTS):
        p = load(os.path.join(pd_, "project.yaml")).get("project") or {}
        for f in sorted(glob.glob(os.path.join(pd_, "workflows", "*.yaml"))):
            rows.append(_workflow_row(f, "project", prel, p))
    return rows


def collect_sites():
    rows = []
    tier_of = {}
    for a in collect_apps():
        for tier, site in a["tiers"].items():
            tier_of[site] = (a["dir"], tier)
    for sd in sorted(glob.glob(os.path.join(ROOT, "sites", "*"))):
        sy = os.path.join(sd, "site.yaml")
        if not os.path.exists(sy):
            continue
        s = load(sy).get("site") or {}
        policy = ((s.get("settings") or {}).get("policy")) or {}
        app, tier = tier_of.get(os.path.basename(sd), ("", ""))
        rows.append({
            "dir": os.path.basename(sd),
            "name": oneline(s.get("name"), 40),
            "title": oneline(s.get("name"), 80) or os.path.basename(sd),
            "desc": oneline(s.get("description"), 300),
            "base_url": oneline(s.get("base_url"), 40),
            "url": str(s.get("base_url") or ""),
            "auth": oneline(s.get("auth_notes"), 200),
            "environment": str(policy.get("environment") or ""),
            "app": app,
            "tier": tier,
            # permissions.write, with the legacy safe_to_submit_forms as alias
            "safe_forms": ((policy.get("permissions") or {}).get("write") == "allow"
                           or policy.get("safe_to_submit_forms") or None),
            "pages": len(glob.glob(os.path.join(sd, "pages", "*.yaml"))),
            "page_files": [{"name": os.path.basename(f)[:-5], "path": rel(f)}
                           for f in sorted(glob.glob(os.path.join(sd, "pages", "*.yaml")))],
            "workflows": len(glob.glob(os.path.join(sd, "workflows", "*.yaml"))),
            "scripts": len(s.get("scripts") or []),
            # Scripts are declared in site.yaml (that is where their description
            # lives); check.py already fails if a declared one is missing on disk.
            "script_files": [{"name": str(x.get("name")),
                              "desc": oneline(x.get("description"), 320),
                              "path": rel(os.path.join(sd, "scripts", str(x.get("name"))))}
                             for x in (s.get("scripts") or []) if isinstance(x, dict)],
            "readme": rel(os.path.join(sd, "scripts", "README.md"))
                      if os.path.exists(os.path.join(sd, "scripts", "README.md")) else "",
            "mapped_at": s.get("mapped_at") or "—",
            "verified_at": s.get("verified_at") or "—",
        })
    return rows


def collect_apps():
    rows = []
    for name, ad in tree.iter_apps(ROOT):
        a = load(os.path.join(ad, "app.yaml")).get("app") or {}
        parity = a.get("parity") or {}
        rows.append({
            "dir": name,
            "title": oneline(a.get("name"), 80) or name,
            "desc": oneline(a.get("description"), 300),
            "tiers": {str(k): str(v) for k, v in (a.get("tiers") or {}).items()},
            "reference": str(parity.get("reference") or ""),
            "gaps": [{"tier": str(g.get("tier")), "page": str(g.get("page")),
                      "why": oneline(g.get("why"), 200)}
                     for g in (parity.get("gaps") or []) if isinstance(g, dict)],
            "script_files": [{"name": str(x.get("name")),
                              "desc": oneline(x.get("description"), 320),
                              "path": rel(os.path.join(ad, "scripts", str(x.get("name"))))}
                             for x in (a.get("scripts") or []) if isinstance(x, dict)],
            "path": rel(os.path.join(ad, "app.yaml")),
        })
    return rows


def collect_groups():
    """Group folders under PROJECTS, with their declared order. The root of
    the projects tree is the implicit top group."""
    rows = {}
    for grel, gd, has in tree.iter_groups(PROJECTS):
        g = load(os.path.join(gd, "group.yaml")).get("group") or {} if has else {}
        rows[grel] = {"dir": grel,
                      "title": oneline(g.get("name"), 80) or grel.split("/")[-1],
                      "desc": oneline(g.get("description"), 300),
                      "order": [str(x) for x in (g.get("order") or [])]}
    return rows


def collect_projects():
    rows = []
    groups = collect_groups()
    for prel, pd_ in tree.iter_projects(PROJECTS):
        py = os.path.join(pd_, "project.yaml")
        p = load(py).get("project") or {}
        sched = p.get("schedule") or {}
        rows.append({
            "dir": prel,
            "group": "/".join(prel.split("/")[:-1]),
            "name": oneline(p.get("name"), 30),
            "title": oneline(p.get("name"), 80) or prel.split("/")[-1],
            "desc": oneline(p.get("description"), 90),
            "purpose": oneline(p.get("description"), 600),
            "kind": str(p.get("kind") or ""),
            "app": str(p.get("app") or ""),
            "sites": [str(s) for s in (p.get("sites") or [])],
            "schedule": (f'{sched.get("every")} on {sched.get("instance")}'
                         if sched.get("every") else ""),
            "dataset": str(p.get("dataset") or ""),
            "workflows": len(glob.glob(os.path.join(pd_, "workflows", "*.yaml"))),
            # Project-scoped lookup tables people maintain (schema/project.yaml → data:)
            "data": [{"name": str(d), "path": rel(os.path.join(pd_, str(d)))}
                     for d in (p.get("data") or [])],
            "state": [str(s) for s in (p.get("state") or [])],
            "path": rel(py),
        })

    # Display order: a group's `order` first, then by name; depth-first by group.
    def key(row):
        parts = row["dir"].split("/")
        out = []
        for i, part in enumerate(parts):
            parent = "/".join(parts[:i])
            order = groups.get(parent, {}).get("order", []) if parent else []
            out.append((order.index(part) if part in order else len(order), part))
        return out
    rows.sort(key=key)
    return rows


def nid(prefix, s):
    """Mermaid node id. Hyphens are not safe in ids, so strip to word chars."""
    return prefix + re.sub(r"\W", "_", str(s))


def mermaid(projects, workflows):
    """Project → site edges. The cross-site relationships are the part nobody
    can hold in their head; the per-site workflows are already obvious."""
    lines = ["```mermaid", "graph LR"]
    seen = set()
    for p in projects:
        pid = nid("p_", p["dir"])
        lines.append(f'  {pid}["{p["dir"]}"]')
        for s in p["sites"]:
            sid = nid("s_", s)
            if sid not in seen:
                lines.append(f'  {sid}("{s}")')
                seen.add(sid)
            lines.append(f"  {pid} --> {sid}")
    orphans = sorted({w["owner"] for w in workflows if w["kind"] == "site"}
                     - {s for p in projects for s in p["sites"]})
    if orphans:
        lines.append("  subgraph site-only")
        for s in orphans:
            oid = nid("o_", s)
            lines.append(f'    {oid}("{s}")')
        lines.append("  end")
    lines.append("```")
    return "\n".join(lines)


def docs_link(path):
    return os.path.relpath(path, "docs").replace(os.sep, "/")


def render():
    wf = collect_workflows()
    sites = collect_sites()
    projects = collect_projects()
    apps_ = collect_apps()

    out = []
    a = out.append
    a("# Inventory")
    a("")
    a("**Generated by `scripts/inventory.py` — do not edit.** Change the YAML and")
    a("re-run. `python scripts/inventory.py --check` fails if this file is stale.")
    a("")
    modes = {}
    for w in wf:
        modes[w["mode"]] = modes.get(w["mode"], 0) + 1
    a(f"{len(sites)} sites · {len(apps_)} apps · {len(projects)} projects · {len(wf)} workflows "
      f"({', '.join(f'{v} {k}' for k, v in sorted(modes.items()))})")
    a("")

    a("## Projects")
    a("")
    a("| Project | Kind | App | Sites | Workflows | Schedule | Purpose |")
    a("|---|---|---|---|---:|---|---|")
    for p in projects:
        a(f'| `{p["dir"]}` | {p["kind"] or "—"} | {p["app"] or "—"} | '
          f'{", ".join(f"`{s}`" for s in p["sites"]) or "—"} | '
          f'{p["workflows"]} | {p["schedule"] or "—"} | {p["desc"]} |')
    a("")
    a(mermaid(projects, wf))
    a("")

    if apps_:
        a("## Apps")
        a("")
        a("| App | Tiers | Parity reference | Declared gaps | Scripts |")
        a("|---|---|---|---:|---:|")
        for ap_ in apps_:
            tiers = ", ".join(f"{t}: `{s}`" for t, s in ap_["tiers"].items())
            a(f'| `{ap_["dir"]}` | {tiers} | {ap_["reference"] or "—"} | '
              f'{len(ap_["gaps"])} | {len(ap_["script_files"])} |')
        a("")

    a("## Workflows")
    a("")
    a("| Owner | Workflow | Mode | Trust | Tiers | Steps | Doc | Purpose |")
    a("|---|---|---|---|---|---:|:-:|---|")
    for w in sorted(wf, key=lambda r: (r["kind"], r["owner"], r["name"])):
        tiers = ("required " + ", ".join(w["tiers"]["required"])
                 if w["tiers"] else "—")
        a(f'| `{w["owner"]}` | [`{w["name"]}`]({docs_link(w["path"])}) '
          f'| {w["mode"]} | {w["trust"] or "—"} | {tiers} | {w["steps"]} '
          f'| {"✓" if w["companion"] else "—"} | {w["desc"]} |')
    a("")

    a("## Sites")
    a("")
    a("| Site | Base URL | Tier of | Pages | Workflows | Scripts | Mapped | Verified |")
    a("|---|---|---|---:|---:|---:|---|---|")
    for s in sites:
        tier = f'{s["app"]} ({s["tier"]})' if s["app"] else "—"
        a(f'| `{s["dir"]}` | {s["base_url"]} | {tier} | {s["pages"]} | {s["workflows"]} '
          f'| {s["scripts"]} | {s["mapped_at"]} | {s["verified_at"]} |')
    a("")
    return "\n".join(out) + "\n"


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {rel(path)}")


def stale(path, fresh):
    current = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    return current != fresh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if a generated file is stale")
    ap.add_argument("--root", help="inventory this tree instead of the script's own "
                                   "repo (e.g. a private map repository)")
    ap.add_argument("--projects", help="the projects tree, when it is not inside --root")
    args = ap.parse_args()

    import libtree  # one command regenerates every view
    import overview
    if args.root or args.projects:
        set_root(args.root or ROOT, args.projects)
        overview.set_root(args.root or ROOT, args.projects)
        libtree.set_root(args.root or ROOT, args.projects)

    targets = [(OUT, render()), (overview.OUT, overview.render()),
               (libtree.OUT, libtree.render())]
    if args.check:
        bad = [p for p, fresh in targets if stale(p, fresh)]
        for p in bad:
            hint = f" --root {args.root}" if args.root else ""
            print(f"FAIL  {rel(p)} is stale — run: python scripts/inventory.py{hint}")
        if bad:
            return 1
        print("docs/inventory.md, docs/overview.html and lib-tree.json are current")
        return 0

    for path, fresh in targets:
        write(path, fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
