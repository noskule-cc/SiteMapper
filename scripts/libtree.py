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

A page node carries `markdown`: the page's purpose, sources, concepts, sections,
recipes (each also as a Mermaid flowchart) and open questions (#93), which the
host draws on the node's How it works tab.

A workflow node carries what its page shows, each key omitted when empty:

    owner        the runs owner: the project's path under projects/, or the site
    facts        [{"label", "value"}]: mode, effect, trust, persona
    flow         [{"label", "kind": step|login|person, "detail"?,
                   "policy"?: {"class", "verdict": allow|ask|deny}}] in run order
    permissions  [{"tier", "class", "verdict", "source"}] per tier of every site
                 the workflow touches; "-" is a site that is no tier of an app.
                 source is the file whose rule decided, relative to the tree
                 root, "framework:config.yaml" for the framework's own, or
                 "defaults" when no file sets the class
"""
import argparse
import functools
import json
import os
import re
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
FRAMEWORK_CONFIG = run.FRAMEWORK_ROOT / "config.yaml"


def source_label(path):
    if path is None:
        return "defaults"
    path = path.resolve()
    if path == FRAMEWORK_CONFIG:
        return "framework:config.yaml"
    return path.relative_to(Path(ROOT).resolve()).as_posix()


def site_policy(site_name):
    sources = run.permission_sources(Path(ROOT), run.Site(Path(ROOT), site_name))
    return {cls: (verdict, source_label(path)) for cls, (verdict, path) in sources.items()}


def is_site(name):
    return not name.startswith("$") and os.path.isfile(os.path.join(ROOT, "sites", name, "site.yaml"))


def workflow_scope(wf, row, apps):
    """(primaries, sites): the site a run leads with, one per allowed tier
    when the workflow has tiers, and every site it touches."""
    tier_sites = []
    if wf.get("tiers"):
        app_tiers = (apps.get(row["app"]) or {}).get("tiers") or {}
        tier_sites = [app_tiers.get(t) for t in row["tiers"]["allowed"]]
    refs = [s.get("site") or wf.get("site") for s in tree.steps_of(wf)]
    refs += [wf.get("site"), *(wf.get("sites") or [])]
    refs += [row["owner"]] if row["kind"] == "site" else []
    names = [*tier_sites, *refs, *sorted(tree.step_sites(wf)[0])]
    sites = [n for n in dict.fromkeys(str(n) for n in names if n) if is_site(n)]
    primaries = [s for s in dict.fromkeys(tier_sites) if s in sites] or sites[:1]
    return primaries, sites


def tiers_of(apps, site_name):
    return [str(t) for app in apps.values() for t, s in (app.get("tiers") or {}).items()
            if s == site_name] or ["-"]


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
    return inventory.oneline(step.get("description"), 160) or inventory.oneline(
        " ".join(str(step[k]) for k in ("action", "page", "element", "script", "value")
                 if step.get(k)), 160)


def workflow_details(row, apps, policy):
    wf = row["workflow"]
    primaries, sites = workflow_scope(wf, row, apps)
    personas = [persona_of(s) for s in primaries]
    if any(p != personas[0] for p in personas):
        persona_value, persona = "chosen per tier", None
    else:
        persona_value, persona = personas[0] if personas else ("", None)

    flow = []
    auth = (persona or {}).get("auth")
    if auth in ("automated", "human") and run.needs_browser(wf):
        login = {"label": f"Log in as {persona.get('name') or 'the persona'}", "kind": "login",
                 "detail": "automated" if auth == "automated" else "a person logs in"}
        if auth == "automated":
            login["policy"] = {"class": "auth",
                               "verdict": strictest(policy(s)["auth"] for s in primaries)[0]}
        flow.append(login)
    needed = run.EFFECT_CLASS.get(wf.get("effect"), "read")
    for step in tree.steps_of(wf):
        if step.get("action") == "human":
            label = (inventory.oneline(step.get("description"), 160)
                     or inventory.oneline(step.get("reason"), 160) or "human")
            person = {"label": label, "kind": "person"}
            if step.get("description") and step.get("reason"):
                person["detail"] = inventory.oneline(step["reason"], 300)
            flow.append(person)
            continue
        entry = {"label": step_label(step), "kind": "step"}
        if needed != "read" and step.get("action") in ACTING and sites:
            ref = str(step.get("site") or wf.get("site") or "")
            on = [ref] if ref in sites else sites
            entry["policy"] = {"class": needed, "verdict": strictest(policy(s)[needed] for s in on)[0]}
        flow.append(entry)

    facts = [{"label": label, "value": str(value)} for label, value in (
        ("Mode", wf.get("mode")), ("Effect", wf.get("effect")),
        ("Trust", wf.get("trust")), ("Persona", persona_value)) if value]

    by_tier = {}
    for s in sites:
        for tier in tiers_of(apps, s):
            by_tier.setdefault(tier, []).append(policy(s))
    permissions = []
    for tier, found in by_tier.items():
        for cls in run.PERMISSION_DEFAULTS:
            verdict, source = strictest(p[cls] for p in found)
            permissions.append({"tier": tier, "class": cls, "verdict": verdict, "source": source})
    return {"owner": row["owner"], "facts": facts, "flow": flow, "permissions": permissions}


def text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def entries(page, block):
    value = page.get(block)
    return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def codes(names):
    return ", ".join(f"`{text(n)}`" for n in names or [])


def step_target(step):
    return text(step.get("recipe") if step.get("do") == "recipe"
                else step.get("element") or step.get("value"))


def recipe_flowchart(steps):
    """Steps in order; a step that runs another recipe is a subroutine box."""
    lines = ["```mermaid", "flowchart TD"]
    for i, step in enumerate(steps, 1):
        label = text(f"{text(step.get('do'))} {step_target(step)}").replace('"', "#quot;")
        shape = f'[["{label}"]]' if step.get("do") == "recipe" else f'["{label}"]'
        lines.append(f"  s{i}{shape}" + (f" --> s{i + 1}" if i < len(steps) else ""))
    return lines + ["```"]


def recipe_markdown(r):
    steps = [s for s in r.get("steps") or [] if isinstance(s, dict)]
    out = [f"#### {text(r.get('name'))}", "", text(r.get("goal")), ""]
    out += [f"When: {text(r['when'])}", ""] if r.get("when") else []
    out += recipe_flowchart(steps) + [""] if steps else []
    for i, step in enumerate(steps, 1):
        target = step_target(step)
        value = f" = `{text(step['value'])}`" if step.get("value") and step.get("element") else ""
        note = f" · {text(step['note'])}" if step.get("note") else ""
        out.append(f"{i}. {text(step.get('do'))}{f' `{target}`' if target else ''}{value}{note}")
    if r.get("after"):
        out += ["", f"After: {text(r['after'])}"]
    if r.get("uses"):
        out += ["", f"Builds on: {codes(r['uses'])}"]
    if r.get("gotchas"):
        out += ["", "Gotchas:"] + [f"- {text(g)}" for g in r["gotchas"]]
    return out + [""]


def page_markdown(page):
    """The page's meaning layers as compact Markdown, or "" when it has none."""
    out = []
    if page.get("purpose"):
        out += [f"**Purpose.** {text(page['purpose'])}", ""]
    sources = entries(page, "sources")
    if sources:
        out += ["Sources: " + ", ".join(f"[{text(s.get('title'))}]({text(s.get('url'))})"
                                        for s in sources), ""]
    concepts = entries(page, "concepts")
    if concepts:
        out += ["### Concepts", ""]
        out += [f"- **{text(c.get('name'))}**: {text(c.get('meaning'))}" for c in concepts]
        out += [""]
    sections = entries(page, "sections")
    if sections:
        out += ["### Sections", ""]
        for s in sections:
            on = f" (on {codes(s['applies_to'])})" if s.get("applies_to") else ""
            out.append(f"- **{text(s.get('name'))}**{on}: {text(s.get('meaning'))}")
            if s.get("elements"):
                out.append(f"  - Elements: {codes(s['elements'])}")
            out += [f"  - Rule: {text(x)}" for x in s.get("rules") or []]
            out += [f"  - Example: {text(x)}" for x in s.get("examples") or []]
        out += [""]
    recipes = entries(page, "recipes")
    if recipes:
        out += ["### Recipes", ""]
        for r in recipes:
            out += recipe_markdown(r)
    questions = entries(page, "open_questions")
    if questions:
        out += ["### Open questions", ""]
        for q in questions:
            parts = [f"Docs: {text(q['docs'])}" if q.get("docs") else "",
                     f"Observed: {text(q.get('observed'))}", f"Owner: {text(q.get('owner'))}"]
            out.append(f"- **{text(q.get('question'))}** " + " ".join(p for p in parts if p))
        out += [""]
    return "\n".join(out).strip() + "\n" if out else ""


def page_node(d, p):
    try:
        page = inventory.load(os.path.join(ROOT, "sites", d, "pages", f"{p['name']}.yaml"))
        page = page.get("page") if isinstance(page, dict) else None
    except inventory.yaml.YAMLError:  # check.py reports a broken page file
        page = None
    md = page_markdown(page) if isinstance(page, dict) else ""
    return node(f"sites/{d}/pages/{p['name']}", p["name"], "page", markdown=md)


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
    pages = [page_node(d, p) for p in s["page_files"]]
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
    workflows = inventory.collect_workflows(raw=True)
    project_sites = {p["dir"]: set(p["sites"]) for p in inventory.collect_projects()}
    apps = run.load_apps(Path(ROOT))
    policy = functools.cache(site_policy)
    details = {w["path"]: workflow_details(w, apps, policy) for w in workflows}
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
