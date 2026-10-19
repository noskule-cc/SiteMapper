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
            "target"?, "owner"?, "facts"?, "flow"?, "permissions"?, "children"?}

A workflow node carries what its page shows, each key omitted when empty:

    owner        the runs owner: the project's path under projects/, or the site
    facts        [{"label", "value"}]: mode, effect, trust, persona
    flow         [{"label", "kind": step|login|person, "detail"?,
                   "policy"?: {"class", "verdict": allow|ask|deny}}] in run order
    permissions  [{"tier", "class", "verdict", "source"}] per tier of every site
                 the workflow touches; "-" is a site that is no tier of an app.
                 source is the file whose rule decided, relative to the tree
                 root, "SiteMapper/config.yaml" for the framework's own, or
                 "defaults" when no file sets the class
"""
import argparse
import functools
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402
import run  # noqa: E402
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


ACTING = ("click", "input", "key", "script")


def source_label(path):
    if path is None:
        return "defaults"
    path = path.resolve()
    if path.is_relative_to(Path(ROOT).resolve()):
        return path.relative_to(Path(ROOT).resolve()).as_posix()
    return f"{tree.LIB}/{path.relative_to(run.FRAMEWORK_ROOT).as_posix()}"


@functools.cache
def site_policy(root, site_name):
    site = run.Site(Path(root), site_name)
    out = {}
    for cls in run.PERMISSION_DEFAULTS:
        verdict, path = run.permission_source(Path(root), site, cls)
        out[cls] = (verdict, source_label(path))
    return out


def workflow_sites(wf, row, apps):
    names = [row["owner"]] if row["kind"] == "site" else []
    names += [wf.get("site"), *(wf.get("sites") or []),
              *(s.get("site") for s in tree.steps_of(wf))]
    if wf.get("tiers"):
        tiers = (apps.get(row["app"]) or {}).get("tiers") or {}
        allowed = wf["tiers"].get("allowed") or wf["tiers"].get("required") or []
        names += [tiers.get(t) for t in allowed]
    return [n for n in dict.fromkeys(str(n) for n in names if n)
            if not n.startswith("$") and os.path.isfile(os.path.join(ROOT, "sites", n, "site.yaml"))]


def tier_of(apps, site_name):
    _, app = run.app_of_site(apps, site_name)
    if not app:
        return "-"
    return next(t for t, s in app["tiers"].items() if s == site_name)


def strictest(verdicts):
    return max(verdicts, key=lambda v: run.STRICTNESS[v[0]])


def persona_of(site_name):
    try:
        persona = run.load_persona(Path(ROOT), site_name, None)
    except run.RunError:
        return "chosen at run time", None
    if not persona:
        return "", None
    return str(persona.get("name") or ""), persona


def step_label(step):
    return (inventory.oneline(step.get("description"), 160)
            or " ".join(str(step[k]) for k in ("action", "page", "element") if step.get(k)))


def workflow_details(row, apps):
    wf = (run.load_yaml(Path(ROOT) / row["path"]) or {}).get("workflow") or {}
    sites = workflow_sites(wf, row, apps)
    policies = {s: site_policy(ROOT, s) for s in sites}
    persona_value, persona = persona_of(sites[0]) if sites else ("", None)

    flow = []
    auth = (persona or {}).get("auth")
    if auth in ("automated", "human"):
        login = {"label": f"Log in as {persona.get('name') or 'the persona'}", "kind": "login",
                 "detail": "automated" if auth == "automated" else "a person logs in"}
        if auth == "automated":
            login["policy"] = {"class": "auth", "verdict": policies[sites[0]]["auth"][0]}
        flow.append(login)
    needed = run.EFFECT_CLASS.get(wf.get("effect"), "read")
    for step in tree.steps_of(wf):
        if step.get("action") == "human":
            person = {"label": step_label(step), "kind": "person"}
            if step.get("reason"):
                person["detail"] = inventory.oneline(step["reason"], 300)
            flow.append(person)
            continue
        entry = {"label": step_label(step), "kind": "step"}
        if needed != "read" and step.get("action") in ACTING and sites:
            verdict = strictest(policies[s][needed] for s in sites)[0]
            entry["policy"] = {"class": needed, "verdict": verdict}
        flow.append(entry)

    facts = [{"label": label, "value": str(value)} for label, value in (
        ("Mode", wf.get("mode")), ("Effect", wf.get("effect")),
        ("Trust", wf.get("trust")), ("Persona", persona_value)) if value]

    by_tier = {}
    for s in sites:
        by_tier.setdefault(tier_of(apps, s), []).append(policies[s])
    permissions = [{"tier": tier, "class": cls, "verdict": verdict, "source": source}
                   for tier, found in by_tier.items() for cls in run.PERMISSION_DEFAULTS
                   for verdict, source in [strictest(p[cls] for p in found)]]
    return {"owner": row["owner"], "facts": facts, "flow": flow, "permissions": permissions}


def workflow_node(id_, w, details, project=None):
    return node(id_, w["name"], "workflow", description=w["purpose"],
                status=STATUS.get(w["trust"]), project=project, **details[w["path"]])


def site_node(s, workflows, project_sites, details):
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
    flows = ([workflow_node(f"sites/{d}/workflows/{w['name']}", w, details) for w in own]
             + [workflow_node(f"sites/{d}/workflows/{w['owner']}/{w['name']}", w, details,
                              w["owner"])
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
    apps = run.load_apps(Path(ROOT))
    details = {w["path"]: workflow_details(w, apps) for w in workflows}
    sites = [site_node(s, workflows, project_sites, details) for s in inventory.collect_sites()]
    app_nodes = [app_node(a) for a in sorted(inventory.collect_apps(), key=lambda a: a["dir"])]
    nodes = [node("sites", "Sites", "folder", sites) if sites else None,
             node("apps", "Apps", "folder", app_nodes) if app_nodes else None]
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
