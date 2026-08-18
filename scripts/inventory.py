#!/usr/bin/env python3
"""Generate docs/inventory.md — what exists in this repo, from the YAML itself.

Usage:
    python scripts/inventory.py            # write docs/inventory.md + docs/overview.html
    python scripts/inventory.py --check    # exit 1 if either committed copy is stale

Both files are GENERATED. Never hand-edit them; change the YAML and re-run.
`--check` is what keeps that true: a generated file nobody verifies is just
slower drift.

The collectors below are the single source both renderers read: this file emits
the Markdown table view (for agents and git diffs), `overview.py` emits the
browsable HTML view (for humans). One walk of the YAML, two presentations.

Why a script and not a skill: enumerating 16 workflows is mechanical, so an LLM
re-parsing them on every question is the wrong executor. See docs/CODE_OVER_LLM.md.
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "inventory.md")


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def oneline(s, limit=110):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[: limit - 1] + "…" if len(s) > limit else s


# NO RUN HISTORY IS COLLECTED HERE, DELIBERATELY.
#
# Both views used to carry a "Last run" column and links to each run, read from
# <owner>/results/. Run outputs live in a deployment's private map repo, and
# collecting them again would be wrong in both directions: on a clean clone every
# workflow reads "never run", and on a machine with the private repo mounted the
# generated files fill up with run dates and paths that then get committed HERE.
# That second case is the one that matters — it is how run metadata leaks back
# into a public repo one regeneration at a time.
#
# So the public inventory describes the tool, not its history. Run history is the
# private repo's to index.


def phases(w):
    """Every step of a workflow, whichever phase it sits in."""
    out = []
    for phase in ("setup", "steps", "teardown"):
        out += [s for s in (w.get(phase) or []) if isinstance(s, dict)]
    return out


def collect_workflows():
    rows = []
    for pat, kind in (("sites/*/workflows/*.yaml", "site"),
                      ("projects/*/workflows/*.yaml", "project")):
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            w = load(f).get("workflow") or {}
            sites = w.get("sites") or ([w.get("site")] if w.get("site") else [])
            steps = phases(w)
            rows.append({
                "kind": kind,
                "owner": rel(f).split("/")[1],
                "name": w.get("name") or os.path.basename(f)[:-5],
                "desc": oneline(w.get("description")),
                "purpose": oneline(w.get("description"), 320),
                "sites": [str(s) for s in sites],
                "mode": str(w.get("mode") or "**—**"),
                "steps": len(w.get("steps") or []),
                "params": [str(p.get("name")) for p in (w.get("parameters") or [])
                           if isinstance(p, dict) and p.get("name")],
                "asserts": sum(1 for s in steps if s.get("action") == "assert"),
                # A *deterministic* workflow with assert steps is a test: it is run
                # with /test, which evaluates them and emits a result. An agentic
                # one asserts too but needs an LLM, so it goes through /run.
                # docs/skills/run-workflow.md step 2, docs/skills/test.md step 2.
                "is_test": (str(w.get("mode")) == "deterministic"
                            and any(s.get("action") == "assert" for s in steps)),
                "calls": sorted({str(s.get("script")) for s in steps if s.get("script")}),
                "companion": os.path.exists(f[:-5] + ".md"),
                "doc_path": rel(f[:-5] + ".md") if os.path.exists(f[:-5] + ".md") else "",
                "path": rel(f),
            })
    return rows


def collect_sites():
    rows = []
    for sd in sorted(glob.glob(os.path.join(ROOT, "sites", "*"))):
        sy = os.path.join(sd, "site.yaml")
        if not os.path.exists(sy):
            continue
        s = load(sy).get("site") or {}
        policy = ((s.get("settings") or {}).get("policy")) or {}
        rows.append({
            "dir": os.path.basename(sd),
            "name": oneline(s.get("name"), 40),
            "title": oneline(s.get("name"), 80) or os.path.basename(sd),
            "desc": oneline(s.get("description"), 300),
            "base_url": oneline(s.get("base_url"), 40),
            "url": str(s.get("base_url") or ""),
            "auth": oneline(s.get("auth_notes"), 200),
            "environment": str(policy.get("environment") or ""),
            "safe_forms": policy.get("safe_to_submit_forms"),
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


def collect_projects():
    rows = []
    for pd_ in sorted(glob.glob(os.path.join(ROOT, "projects", "*"))):
        py = os.path.join(pd_, "project.yaml")
        if not os.path.exists(py):
            continue
        p = load(py).get("project") or {}
        rows.append({
            "dir": os.path.basename(pd_),
            "name": oneline(p.get("name"), 30),
            "title": oneline(p.get("name"), 80) or os.path.basename(pd_),
            "desc": oneline(p.get("description"), 90),
            "purpose": oneline(p.get("description"), 600),
            "sites": [str(s) for s in (p.get("sites") or [])],
            "workflows": len(glob.glob(os.path.join(pd_, "workflows", "*.yaml"))),
            # Project-scoped lookup tables (schema/project.yaml → data:)
            "data": [{"name": str(d), "path": rel(os.path.join(pd_, str(d)))}
                     for d in (p.get("data") or [])],
            "path": rel(py),
        })
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


def render():
    wf = collect_workflows()
    sites = collect_sites()
    projects = collect_projects()

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
    a(f"{len(sites)} sites · {len(projects)} projects · {len(wf)} workflows "
      f"({', '.join(f'{v} {k}' for k, v in sorted(modes.items()))})")
    a("")

    a("## Projects")
    a("")
    a("| Project | Sites | Workflows | Purpose |")
    a("|---|---|---:|---|")
    for p in projects:
        a(f'| `{p["dir"]}` | {", ".join(f"`{s}`" for s in p["sites"])} | '
          f'{p["workflows"]} | {p["desc"]} |')
    a("")
    a(mermaid(projects, wf))
    a("")

    a("## Workflows")
    a("")
    a("| Owner | Workflow | Mode | Steps | Doc | Purpose |")
    a("|---|---|---|---:|:-:|---|")
    for w in sorted(wf, key=lambda r: (r["kind"], r["owner"], r["name"])):
        a(f'| `{w["owner"]}` | [`{w["name"]}`]({os.path.relpath(w["path"], "docs").replace(os.sep, "/")}) '
          f'| {w["mode"]} | {w["steps"]} | {"✓" if w["companion"] else "—"} '
          f'| {w["desc"]} |')
    a("")

    a("## Sites")
    a("")
    a("| Site | Base URL | Pages | Workflows | Scripts | Mapped | Verified |")
    a("|---|---|---:|---:|---:|---|---|")
    for s in sites:
        a(f'| `{s["dir"]}` | {s["base_url"]} | {s["pages"]} | {s["workflows"]} '
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
    args = ap.parse_args()

    import overview  # one command regenerates both views; see overview.py

    targets = [(OUT, render()), (overview.OUT, overview.render())]
    if args.check:
        bad = [p for p, fresh in targets if stale(p, fresh)]
        for p in bad:
            print(f"FAIL  {rel(p)} is stale — run: python scripts/inventory.py")
        if bad:
            return 1
        print("docs/inventory.md and docs/overview.html are current")
        return 0

    for path, fresh in targets:
        write(path, fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
