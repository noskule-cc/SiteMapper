#!/usr/bin/env python3
"""Render lib-tree.json — the tree a host draws for this lib, at the lib root.

Usage:
    python scripts/inventory.py            # writes this file and the two docs/ views
    python scripts/libtree.py              # writes only this file
    python scripts/libtree.py --check      # exit 1 if the committed copy is stale

Same data as docs/inventory.md, for a host instead of a reader. The format is
the host's, not SiteMapper's (TeamOS#21): a lib-neutral list of nodes the host
renders as an expandable tree without parsing any of this lib's YAML. It lives
at the lib root, not in docs/, because the host finds it at
<data tree>/<lib>/lib-tree.json whatever the lib.

    {"lib": str, "nodes": [Node, ...]}
    Node = {"id", "label", "kind", "description"?, "status"?, "project"?,
            "target"?, "children"?}
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402
import tree  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = tree.projects_root(ROOT)
OUT = os.path.join(ROOT, "lib-tree.json")

STATUS = {"verified": "ok", "draft": "unproven", "broken": "broken"}


def set_root(root, projects=None):
    """Render another tree. See inventory.set_root()."""
    global ROOT, PROJECTS, OUT
    ROOT = os.path.abspath(root)
    PROJECTS = tree.projects_root(ROOT, projects)
    OUT = os.path.join(ROOT, "lib-tree.json")
    return ROOT


def node(id_, label, kind, children=None, **optional):
    """One node, optional keys omitted when empty — the format says so."""
    n = {"id": id_, "label": label, "kind": kind}
    n.update({k: v for k, v in optional.items() if v})
    if children:
        n["children"] = children
    return n


def joined(*parts):
    return " · ".join(p for p in parts if p)


def workflow_node(id_, w, project=None):
    return node(id_, w["name"], "workflow", description=w["desc"],
                status=STATUS.get(w["trust"]), project=project)


def site_node(s, workflows, project_sites):
    d = s["dir"]
    own = sorted((w for w in workflows if w["kind"] == "site" and w["owner"] == d),
                 key=lambda w: w["name"])
    # A project workflow belongs under every site it touches: its own site/sites,
    # or failing that, any site its project declares.
    used = sorted((w for w in workflows if w["kind"] == "project"
                   and d in set(w["sites"]) | project_sites.get(w["owner"], set())),
                  key=lambda w: (w["owner"], w["name"]))
    pages = [node(f"sites/{d}/pages/{p['name']}", p["name"], "page")
             for p in s["page_files"]]
    flows = ([workflow_node(f"sites/{d}/workflows/{w['name']}", w) for w in own]
             + [workflow_node(f"sites/{d}/workflows/{w['owner']}/{w['name']}", w, w["owner"])
                for w in used])
    return node(f"sites/{d}", d, "site", [
        f for f in (node(f"sites/{d}/pages", "Pages", "folder", pages) if pages else None,
                    node(f"sites/{d}/workflows", "Workflows", "folder", flows) if flows else None)
        if f], description=joined(s["title"] if s["title"] != d else "", s["url"]))


def app_node(a):
    d = a["dir"]
    tiers = [node(f"apps/{d}/tiers/{t}", f"{t} · {site}", "tier", target=f"sites/{site}")
             for t, site in sorted(a["tiers"].items())]
    return node(f"apps/{d}", d, "app", tiers,
                description=joined(a["title"] if a["title"] != d else "", a["desc"]))


def render():
    # Same reason as overview.render(): inventory.py run as a script is
    # __main__, so this module's `inventory` is a second copy whose root
    # nobody set.
    inventory.set_root(ROOT, PROJECTS)
    workflows = inventory.collect_workflows()
    project_sites = {p["dir"]: set(p["sites"]) for p in inventory.collect_projects()}
    sites = [site_node(s, workflows, project_sites) for s in inventory.collect_sites()]
    apps = [app_node(a) for a in sorted(inventory.collect_apps(), key=lambda a: a["dir"])]
    nodes = [node("sites", "Sites", "folder", sites) if sites else None,
             node("apps", "Apps", "folder", apps) if apps else None]
    doc = {"lib": "SiteMapper", "nodes": [n for n in nodes if n]}
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed copy is stale")
    ap.add_argument("--root", help="render this tree instead of the script's own repo")
    ap.add_argument("--projects", help="the projects tree, when it is not inside --root")
    args = ap.parse_args()
    if args.root or args.projects:
        set_root(args.root or ROOT, args.projects)
    fresh = render()
    if args.check:
        if inventory.stale(OUT, fresh):
            print(f"FAIL  {inventory.rel(OUT)} is stale — run: python scripts/inventory.py")
            return 1
        print(f"{inventory.rel(OUT)} is current")
        return 0
    inventory.write(OUT, fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
