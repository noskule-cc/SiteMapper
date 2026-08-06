#!/usr/bin/env python3
"""Generate docs/inventory.md — what exists in this repo, from the YAML itself.

Usage:
    python scripts/inventory.py            # write docs/inventory.md
    python scripts/inventory.py --check    # exit 1 if the committed copy is stale

The file is GENERATED. Never hand-edit it; change the YAML and re-run. `--check`
is what keeps that true: a generated file nobody verifies is just slower drift.

Why a script and not a skill: enumerating 14 workflows is mechanical, so an LLM
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


def last_result(workflow_path):
    """Newest results/<workflow>.<date>.md beside the workflow's owner dir."""
    owner = os.path.dirname(os.path.dirname(workflow_path))
    stem = os.path.basename(workflow_path)[:-5]
    hits = sorted(glob.glob(os.path.join(owner, "results", stem + ".*.md")))
    if not hits:
        return "—"
    return os.path.basename(hits[-1])[:-3].split(".")[-1]


def collect_workflows():
    rows = []
    for pat, kind in (("sites/*/workflows/*.yaml", "site"),
                      ("projects/*/workflows/*.yaml", "project")):
        for f in sorted(glob.glob(os.path.join(ROOT, pat))):
            w = load(f).get("workflow") or {}
            sites = w.get("sites") or ([w.get("site")] if w.get("site") else [])
            rows.append({
                "kind": kind,
                "owner": rel(f).split("/")[1],
                "name": w.get("name") or os.path.basename(f)[:-5],
                "desc": oneline(w.get("description")),
                "sites": [str(s) for s in sites],
                "mode": str(w.get("mode") or "**—**"),
                "steps": len(w.get("steps") or []),
                "companion": os.path.exists(f[:-5] + ".md"),
                "last": last_result(f),
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
        rows.append({
            "dir": os.path.basename(sd),
            "name": oneline(s.get("name"), 40),
            "base_url": oneline(s.get("base_url"), 40),
            "pages": len(glob.glob(os.path.join(sd, "pages", "*.yaml"))),
            "workflows": len(glob.glob(os.path.join(sd, "workflows", "*.yaml"))),
            "scripts": len(s.get("scripts") or []),
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
            "desc": oneline(p.get("description"), 90),
            "sites": [str(s) for s in (p.get("sites") or [])],
            "workflows": len(glob.glob(os.path.join(pd_, "workflows", "*.yaml"))),
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
    a("| Owner | Workflow | Mode | Steps | Doc | Last run | Purpose |")
    a("|---|---|---|---:|:-:|---|---|")
    for w in sorted(wf, key=lambda r: (r["kind"], r["owner"], r["name"])):
        a(f'| `{w["owner"]}` | [`{w["name"]}`]({os.path.relpath(w["path"], "docs").replace(os.sep, "/")}) '
          f'| {w["mode"]} | {w["steps"]} | {"✓" if w["companion"] else "—"} '
          f'| {w["last"]} | {w["desc"]} |')
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if docs/inventory.md is stale")
    args = ap.parse_args()

    fresh = render()
    if args.check:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != fresh:
            print("FAIL  docs/inventory.md is stale — run: python scripts/inventory.py")
            return 1
        print("docs/inventory.md is current")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fresh)
    print(f"wrote {rel(OUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
