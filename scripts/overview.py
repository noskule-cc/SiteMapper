#!/usr/bin/env python3
"""Render docs/overview.html — the browsable view of every site, process and project.

Usage:
    python scripts/inventory.py            # writes this file and docs/inventory.md
    python scripts/overview.py             # writes only this file
    python scripts/overview.py --check     # exit 1 if the committed copy is stale
    python scripts/overview.py --links github --out build/overview.html
                                           # a copy whose links point at GitHub,
                                           # for publishing away from the repo

Same data as docs/inventory.md, different audience. The Markdown view is for
agents and git diffs: flat, greppable, small. This one is for a human opening a
browser — search, filters, the project/site graph, and every process (workflow
*and* script) with the command that starts it.

Self-contained by construction: no CDN, no fonts, no build step. The graph is
emitted as plain SVG rather than pulling in a diagram library, so the page works
offline from a file:// URL and stays a few tens of KB. The equivalent Mermaid
source is embedded too — as text here, as a rendered diagram in hosts that
support it (GitHub, Claude Artifacts).

It cannot RUN anything: a page opened from disk has no way to execute a
workflow, and workflows have no headless runner anyway (an agent drives them —
docs/skills/run-workflow.md). Each process therefore offers its invocation to
copy, and a human runs it. See issue #14 for the levels beyond that.
"""
import argparse
import html
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "overview.html")

# Where a link to a repo file points. Default is relative, which is what the
# committed copy in docs/ needs; --links github rewrites them absolute so the
# page still works when it is read somewhere other than a clone.
LOCAL = ".."
BASE = LOCAL

# One hue per project, stable across runs (index order), in both themes: the
# same blue that reads on white is too dark to label a node on a dark ground.
HUES = 6
LIGHT_HUES = ["#2563eb", "#c2410c", "#047857", "#7e22ce", "#be123c", "#0369a1"]
DARK_HUES = ["#60a5fa", "#fb923c", "#34d399", "#c084fc", "#fb7185", "#38bdf8"]

# Every colour is a token, defined in BOTH palettes. A colour whose only
# definition sits inside a media query renders one theme's ink on the other
# theme's ground for every reader on the default "system" setting.
LIGHT = """
  --bg: #f6f7f9; --panel: #ffffff; --ink: #16181d; --muted: #5d6473;
  --line: #e2e5ea; --accent: #2563eb; --chip: #eef1f6;
  /* Ink for text sitting ON the accent — white over the light theme's deep
     blue, but the dark theme's accent is pale, so it flips to near-black. */
  --on-accent: #ffffff;
  --agentic: #6d28d9; --deterministic: #0f766e; --warn: #b45309;
  --prod-bg: #fee2e2; --prod-fg: #991b1b;
  --staging-bg: #fef3c7; --staging-fg: #92400e;
  --dev-bg: #dcfce7; --dev-fg: #166534;
"""
DARK = """
  --bg: #14161a; --panel: #1c1f25; --ink: #e7e9ee; --muted: #99a1b0;
  --line: #2b3038; --accent: #7aa2f7; --chip: #262b33;
  --on-accent: #10131a;
  --agentic: #a78bfa; --deterministic: #2dd4bf; --warn: #fbbf24;
  --prod-bg: #3f1d1d; --prod-fg: #fca5a5;
  --staging-bg: #3d2f10; --staging-fg: #fcd34d;
  --dev-bg: #12331f; --dev-fg: #86efac;
"""


def theme_block():
    light = LIGHT + "".join(f"  --h{i}: {c};\n" for i, c in enumerate(LIGHT_HUES))
    dark = DARK + "".join(f"  --h{i}: {c};\n" for i, c in enumerate(DARK_HUES))
    return (":root {" + light + "}\n"
            # An explicit light choice has to beat a dark OS, hence the :not().
            '@media (prefers-color-scheme: dark) { :root:not([data-theme="light"])'
            " {" + dark + "} }\n"
            ':root[data-theme="dark"] {' + dark + "}\n")


CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
}
code, .mono, .name { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible, button:focus-visible, summary:focus-visible, input:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 20px 64px; }

header.top { border-bottom: 1px solid var(--line); background: var(--panel); }
header.top .wrap { padding-top: 26px; padding-bottom: 0; }
h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--muted); margin: 0 0 16px; font-size: 14px; }
.counts { display: flex; flex-wrap: wrap; gap: 20px; margin: 0 0 18px; }
.counts div { line-height: 1.2; }
.counts b { display: block; font-size: 22px; font-variant-numeric: tabular-nums; }
.counts span { color: var(--muted); font-size: 12px; text-transform: uppercase;
  letter-spacing: .06em; }

.toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  padding-bottom: 16px; }
#q {
  flex: 1 1 260px; min-width: 200px; padding: 9px 12px; font: inherit;
  background: var(--bg); color: var(--ink);
  border: 1px solid var(--line); border-radius: 8px;
}
#q:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.chips-label { color: var(--muted); font-size: 11px; text-transform: uppercase;
  letter-spacing: .07em; margin-right: 2px; }
.chip {
  padding: 7px 12px; font: inherit; font-size: 13px; cursor: pointer;
  background: var(--chip); color: var(--ink);
  border: 1px solid transparent; border-radius: 999px;
}
.chip[aria-pressed="true"] { background: var(--accent); color: var(--on-accent); }
.shown { color: var(--muted); font-size: 13px; margin-left: auto; }

h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .08em;
  color: var(--muted); margin: 40px 0 14px; font-weight: 600; }

.map { background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 8px 12px 12px; overflow-x: auto; }
.map svg { display: block; min-width: 680px; }
.map .n-label { font: 12.5px ui-monospace, Consolas, monospace; }
.map .n-meta { font: 11px ui-sans-serif, sans-serif; fill: var(--muted); }
.map g.node:hover .box { stroke-width: 2px; }
.map .edge { fill: none; stroke-width: 1.6px; opacity: .55; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; padding: 10px 2px 0;
  color: var(--muted); font-size: 12px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px;
  margin-right: 5px; vertical-align: baseline; }

.card { background: var(--panel); border: 1px solid var(--line);
  border-radius: 12px; padding: 18px 20px; margin-bottom: 14px; }
.card > h3 { margin: 0; font-size: 17px; display: flex; flex-wrap: wrap;
  align-items: center; gap: 9px; }
.card > h3 .name { font-size: 16px; }
.card .desc { color: var(--muted); margin: 8px 0 0; font-size: 14px;
  max-width: 78ch; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 12px 0 0;
  color: var(--muted); font-size: 12.5px; }
.meta b { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums; }

.tag { font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: var(--chip); color: var(--muted); letter-spacing: .02em;
  white-space: nowrap; }
.tag.env-production { background: var(--prod-bg); color: var(--prod-fg); }
.tag.env-staging { background: var(--staging-bg); color: var(--staging-fg); }
.tag.env-development { background: var(--dev-bg); color: var(--dev-fg); }
.tag.mode-agentic { color: var(--agentic); }
.tag.mode-deterministic { color: var(--deterministic); }
.tag.kind-workflow, .tag.kind-script { font-weight: 600; }
.tag.kind-script { color: var(--warn); }

.procs { margin: 16px 0 0; border-top: 1px solid var(--line); }
.proc { padding: 12px 0 12px; border-bottom: 1px solid var(--line); }
.proc:last-child { border-bottom: 0; padding-bottom: 0; }
.proc-head { display: flex; flex-wrap: wrap; align-items: center; gap: 9px;
  min-width: 0; }
.proc-head .name { font-size: 14px; font-weight: 600; }
.proc .purpose { color: var(--muted); font-size: 13px; margin: 6px 0 0;
  max-width: 84ch; }
.proc .links { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 7px;
  font-size: 12.5px; }
.spacer { flex: 1; }
.run {
  font: 12px/1.25 ui-monospace, Consolas, monospace; cursor: pointer;
  padding: 6px 10px; border-radius: 7px; white-space: nowrap;
  background: var(--chip); color: var(--ink); border: 1px solid var(--line);
  /* The label is a short form of the command; data-cmd carries it in full.
     Without a cap, a script path is wide enough to scroll the whole page. */
  max-width: 340px; overflow: hidden; text-overflow: ellipsis;
}
.run:hover { border-color: var(--accent); color: var(--accent); }
.run.copied { background: var(--accent); color: var(--on-accent); border-color: var(--accent); }

details { margin-top: 12px; }
summary { cursor: pointer; color: var(--muted); font-size: 13px; }
summary:hover { color: var(--accent); }
.pages { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.pages a { font-size: 12px; padding: 3px 9px; border-radius: 6px;
  background: var(--chip); }
pre { overflow-x: auto; background: var(--chip); padding: 12px;
  border-radius: 8px; font-size: 12px; line-height: 1.45; }
.empty { color: var(--muted); font-size: 14px; padding: 30px 0; display: none; }
footer { color: var(--muted); font-size: 12.5px; margin-top: 44px;
  border-top: 1px solid var(--line); padding-top: 14px; }
.hidden { display: none !important; }
"""

JS = """
const q = document.getElementById('q');
const cards = [...document.querySelectorAll('.card')];
const chips = [...document.querySelectorAll('.chip')];
const filters = { kind: 'all', mode: 'all' };

function apply() {
  const term = q.value.trim().toLowerCase();
  let shown = 0;
  for (const card of cards) {
    const cardHit = !term || card.dataset.search.includes(term);
    let any = false, anyHit = false;
    for (const proc of card.querySelectorAll('.proc')) {
      const passes = (filters.kind === 'all' || proc.dataset.kind === filters.kind)
                  && (filters.mode === 'all' || proc.dataset.mode === filters.mode);
      const hit = !term || cardHit || proc.dataset.search.includes(term);
      proc.classList.toggle('hidden', !(passes && hit));
      any = any || passes;
      anyHit = anyHit || (passes && hit && !cardHit);
    }
    // A card with no process at all is still a real site — hide it only when a
    // process filter is on, because then the question being asked is about processes.
    const filtering = filters.kind !== 'all' || filters.mode !== 'all';
    const visible = (cardHit || anyHit) && (!filtering || any);
    card.classList.toggle('hidden', !visible);
    if (visible) shown++;
  }
  for (const sec of document.querySelectorAll('section[data-group]')) {
    const has = [...sec.querySelectorAll('.card')].some(c => !c.classList.contains('hidden'));
    sec.classList.toggle('hidden', !has);
  }
  document.getElementById('shown').textContent =
    shown === cards.length ? `${cards.length} cards` : `${shown} of ${cards.length} cards`;
  document.getElementById('none').style.display = shown ? 'none' : 'block';
}

q.addEventListener('input', apply);
for (const chip of chips) {
  chip.addEventListener('click', () => {
    const group = chip.dataset.group;
    for (const other of chips) {
      if (other.dataset.group === group) other.setAttribute('aria-pressed', other === chip);
    }
    filters[group] = chip.dataset.value;
    apply();
  });
}
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); }
  if (e.key === 'Escape' && document.activeElement === q) { q.value = ''; apply(); }
});

// Copy the invocation. file:// is a secure context in Chrome, but fall back to
// the old selection trick anywhere the clipboard API is unavailable.
function copy(text) {
  if (navigator.clipboard) return navigator.clipboard.writeText(text);
  const ta = document.createElement('textarea');
  ta.value = text; document.body.appendChild(ta); ta.select();
  document.execCommand('copy'); ta.remove();
  return Promise.resolve();
}
for (const btn of document.querySelectorAll('.run')) {
  btn.addEventListener('click', () => {
    copy(btn.dataset.cmd).then(() => {
      const was = btn.textContent;
      btn.textContent = 'copied'; btn.classList.add('copied');
      setTimeout(() => { btn.textContent = was; btn.classList.remove('copied'); }, 1200);
    });
  });
}

// Hovering a graph node dims everything not connected to it.
const svg = document.querySelector('.map svg');
if (svg) {
  const edges = [...svg.querySelectorAll('.edge')];
  const focus = key => {
    for (const e of edges) {
      const on = !key || e.dataset.from === key || e.dataset.to === key;
      e.style.opacity = on ? (key ? 1 : .55) : .06;
    }
    for (const n of svg.querySelectorAll('g.node')) {
      const on = !key || n.dataset.key === key
              || edges.some(e => (e.dataset.from === key && e.dataset.to === n.dataset.key)
                              || (e.dataset.to === key && e.dataset.from === n.dataset.key));
      n.style.opacity = on ? 1 : .25;
    }
  };
  for (const n of svg.querySelectorAll('g.node')) {
    n.addEventListener('mouseenter', () => focus(n.dataset.key));
    n.addEventListener('mouseleave', () => focus(null));
  }
}
apply();
"""


def e(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def href(repo_rel):
    """A link to a file in this repo, resolved against the current link base."""
    return BASE + "/" + str(repo_rel).replace("\\", "/")


def github_base(branch="main"):
    """<remote>/blob/<branch>, read from git rather than hard-coded — a URL
    written into a script is one more thing that silently goes stale."""
    try:
        url = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("no git remote to build GitHub links from — pass --base explicitly")
    url = re.sub(r"^git@github\.com:", "https://github.com/", url)
    url = re.sub(r"^ssh://git@", "https://", url)
    return re.sub(r"\.git$", "", url) + "/blob/" + branch


def cmd_for(w):
    """The invocation a human types. A deterministic workflow with assert steps
    is a test, so it goes through /test — which evaluates them and emits a
    result — not /run. See docs/skills/run-workflow.md."""
    return ("/test " if w["is_test"] else "/run ") + w["name"]


# --------------------------------------------------------------------------
# graph
# --------------------------------------------------------------------------

NODE_H, ROW_GAP, PAD = 30, 12, 14
P_X, P_W, S_X, S_W = 14, 210, 400, 300


def graph(projects, sites, workflows):
    """Projects on the left, every site on the right, edges for the sites a
    project spans. The cross-site relationships are the part nobody can hold in
    their head — the same reason inventory.md draws it."""
    proj_of = {p["dir"]: i for i, p in enumerate(projects)}
    links = {p["dir"]: [s for s in p["sites"]] for p in projects}
    # Order sites by the first project that reaches them, so edges cross less.
    def rank(site):
        owners = [proj_of[p] for p, ss in links.items() if site in ss]
        return (min(owners) if owners else len(projects), site)

    ordered = sorted([s["dir"] for s in sites], key=rank)
    row = {d: i for i, d in enumerate(ordered)}
    by_dir = {s["dir"]: s for s in sites}

    height = max(len(ordered), len(projects)) * (NODE_H + ROW_GAP) + PAD
    p_y = {p["dir"]: (i + 0.5) * height / len(projects) - NODE_H / 2
           for i, p in enumerate(projects)} if projects else {}
    s_y = {d: PAD / 2 + i * (NODE_H + ROW_GAP) for d, i in row.items()}

    out = [f'<svg viewBox="0 0 {S_X + S_W + PAD} {int(height)}" '
           f'width="100%" height="{int(height)}" role="img" '
           f'aria-label="projects and the sites they span">']

    for p in projects:
        colour = f"var(--h{proj_of[p['dir']] % HUES})"
        for s in p["sites"]:
            if s not in s_y:
                continue  # a project may name a site that is not mapped yet
            y1 = p_y[p["dir"]] + NODE_H / 2
            y2 = s_y[s] + NODE_H / 2
            x1, x2 = P_X + P_W, S_X
            mid = (x1 + x2) / 2
            out.append(
                f'<path class="edge" data-from="{e(p["dir"])}" data-to="{e(s)}" '
                f'stroke="{colour}" d="M{x1},{y1:.1f} C{mid},{y1:.1f} {mid},{y2:.1f} '
                f'{x2},{y2:.1f}"/>')

    for p in projects:
        colour = f"var(--h{proj_of[p['dir']] % HUES})"
        y = p_y[p["dir"]]
        out.append(
            f'<g class="node" data-key="{e(p["dir"])}">'
            f'<a href="#p-{e(p["dir"])}">'
            f'<rect class="box" x="{P_X}" y="{y:.1f}" width="{P_W}" height="{NODE_H}" '
            f'rx="7" fill="{colour}" fill-opacity=".12" stroke="{colour}"/>'
            f'<text class="n-label" x="{P_X + 11}" y="{y + 19.5:.1f}" fill="{colour}">'
            f'{e(p["dir"])}</text>'
            f'<text class="n-meta" x="{P_X + P_W - 11}" y="{y + 19.5:.1f}" '
            f'text-anchor="end">{p["workflows"]}</text>'
            f'</a></g>')

    for d in ordered:
        s, y = by_dir[d], s_y[d]
        wf = sum(1 for w in workflows if w["kind"] == "site" and w["owner"] == d)
        meta = " · ".join(filter(None, [f"{wf} wf" if wf else "",
                                        f'{s["scripts"]} sc' if s["scripts"] else ""]))
        out.append(
            f'<g class="node" data-key="{e(d)}">'
            f'<a href="#s-{e(d)}">'
            f'<rect class="box" x="{S_X}" y="{y:.1f}" width="{S_W}" height="{NODE_H}" '
            f'rx="7" fill="var(--chip)" stroke="var(--line)"/>'
            f'<text class="n-label" x="{S_X + 11}" y="{y + 19.5:.1f}" fill="currentColor">'
            f'{e(d)}</text>'
            f'<text class="n-meta" x="{S_X + S_W - 11}" y="{y + 19.5:.1f}" '
            f'text-anchor="end">{e(meta)}</text>'
            f'</a></g>')

    out.append("</svg>")
    legend = " ".join(
        f'<span><i style="background:var(--h{i % HUES})"></i>{e(p["dir"])}</span>'
        for i, p in enumerate(projects))
    return ('<div class="map">' + "\n".join(out) + "</div>"
            f'<div class="legend">{legend}'
            '<span>numbers: workflows on a project, wf/sc on a site</span></div>')


# --------------------------------------------------------------------------
# cards
# --------------------------------------------------------------------------

def proc_workflow(w, show_owner=False):
    bits = [f'<span class="tag kind-workflow">workflow</span>',
            f'<a class="name" href="{e(href(w["path"]))}">{e(w["name"])}</a>',
            f'<span class="tag mode-{e(w["mode"])}">{e(w["mode"])}</span>']
    if w["is_test"]:
        bits.append('<span class="tag">test</span>')
    if show_owner:
        bits.append(f'<span class="tag">via {e(w["owner"])}</span>')
    bits.append(f'<span class="tag">{w["steps"]} steps</span>')
    if w["asserts"]:
        bits.append(f'<span class="tag">{w["asserts"]} asserts</span>')
    if w["params"]:
        bits.append(f'<span class="tag">{len(w["params"])} '
                    f'{"param" if len(w["params"]) == 1 else "params"}</span>')
    bits.append('<span class="spacer"></span>')
    bits.append(f'<button class="run" data-cmd="{e(cmd_for(w))}" '
                f'title="copy: {e(cmd_for(w))}">{e(cmd_for(w))}</button>')

    links = []
    if w["doc_path"]:
        links.append(f'<a href="{e(href(w["doc_path"]))}">flowchart&nbsp;.md</a>')
    if w["calls"]:
        links.append("calls " + ", ".join(f"<code>{e(c)}</code>" for c in w["calls"]))
    # No run history here — see the note in inventory.py. Run outputs live in the
    # deployment's private map repo, so linking them from here would either
    # dangle or publish the run dates it was meant to keep out.

    search = " ".join([w["name"], w["owner"], w["mode"], w["purpose"]] + w["params"]).lower()
    return (f'<div class="proc" data-kind="workflow" data-mode="{e(w["mode"])}" '
            f'data-search="{e(search)}">'
            f'<div class="proc-head">{"".join(bits)}</div>'
            f'<p class="purpose">{e(w["purpose"])}</p>'
            f'<div class="links">{" ".join(links)}</div></div>')


def script_cmd(sc):
    """What to hand a human for a script. A .py runs from the repo root; anything
    else has no invocation this page can know — a site's bare .js helper is
    pasted into the browser tab, not shelled out — so offer only its path."""
    if sc["name"].endswith(".py"):
        return "python " + sc["path"], "python …/" + sc["name"]
    return sc["path"], "copy path"


def proc_script(site, sc):
    cmd, label = script_cmd(sc)
    search = " ".join([sc["name"], site["dir"], sc["desc"]]).lower()
    return (f'<div class="proc" data-kind="script" data-mode="deterministic" '
            f'data-search="{e(search)}">'
            f'<div class="proc-head">'
            f'<span class="tag kind-script">script</span>'
            f'<a class="name" href="{e(href(sc["path"]))}">{e(sc["name"])}</a>'
            f'<span class="tag mode-deterministic">deterministic</span>'
            f'<span class="spacer"></span>'
            f'<button class="run" data-cmd="{e(cmd)}" title="copy: {e(cmd)}">'
            f'{e(label)}</button></div>'
            f'<p class="purpose">{e(sc["desc"])}</p></div>')


def project_card(p, workflows):
    own = [w for w in workflows if w["kind"] == "project" and w["owner"] == p["dir"]]
    chips = " ".join(f'<a class="tag" href="#s-{e(s)}">{e(s)}</a>' for s in p["sites"])
    data = ""
    if p["data"]:
        data = ('<div class="links">reference data ' + " ".join(
            f'<a href="{e(href(d["path"]))}"><code>{e(d["name"])}</code></a>'
            for d in p["data"]) + "</div>")
    search = " ".join([p["dir"], p["title"], p["purpose"]] + p["sites"]).lower()
    return (f'<article class="card" id="p-{e(p["dir"])}" data-search="{e(search)}">'
            f'<h3><span class="name">{e(p["dir"])}</span>'
            f'<span class="tag">{e(p["title"])}</span></h3>'
            f'<p class="desc">{e(p["purpose"])}</p>'
            f'<div class="meta"><span>spans {chips}</span>'
            f'<span><b>{len(own)}</b> workflows</span>'
            f'<span><a href="{e(href(p["path"]))}">project.yaml</a></span></div>'
            + data
            + '<div class="procs">' + "".join(proc_workflow(w) for w in own) + "</div>"
            "</article>")


def site_card(site, workflows, projects):
    own = [w for w in workflows if w["kind"] == "site" and w["owner"] == site["dir"]]
    via = [w for w in workflows if w["kind"] == "project" and site["dir"] in w["sites"]]
    users = [p["dir"] for p in projects if site["dir"] in p["sites"]]

    tags = []
    if site["environment"]:
        tags.append(f'<span class="tag env-{e(site["environment"])}">'
                    f'{e(site["environment"])}</span>')
    if site["safe_forms"] is True:
        tags.append('<span class="tag">forms: submit allowed</span>')

    meta = [f'<span><b>{site["pages"]}</b> pages</span>',
            f'<span><b>{len(own) + len(via)}</b> workflows</span>',
            f'<span><b>{site["scripts"]}</b> scripts</span>',
            f'<span>mapped <b>{e(site["mapped_at"])}</b></span>']
    if site["verified_at"] != "—":
        meta.append(f'<span>verified <b>{e(site["verified_at"])}</b></span>')
    if users:
        meta.append("<span>used by " + " ".join(
            f'<a class="tag" href="#p-{e(u)}">{e(u)}</a>' for u in users) + "</span>")

    procs = ("".join(proc_workflow(w) for w in own)
             + "".join(proc_script(site, sc) for sc in site["script_files"])
             + "".join(proc_workflow(w, show_owner=True) for w in via))
    if not procs:
        procs = '<div class="proc"><p class="purpose">Mapped, but nothing runs against it yet.</p></div>'

    pages = ""
    if site["page_files"]:
        pages = (f'<details><summary>{site["pages"]} mapped pages</summary>'
                 '<div class="pages">' + "".join(
                     f'<a href="{e(href(f["path"]))}">{e(f["name"])}</a>'
                     for f in site["page_files"]) + "</div></details>")

    search = " ".join([site["dir"], site["title"], site["desc"], site["url"],
                       site["environment"]] + users
                      + [f["name"] for f in site["page_files"]]).lower()
    return (f'<article class="card" id="s-{e(site["dir"])}" data-search="{e(search)}">'
            f'<h3><span class="name">{e(site["dir"])}</span>{"".join(tags)}</h3>'
            f'<div class="meta"><a href="{e(site["url"])}">{e(site["url"])}</a>'
            f'<span><a href="{e(href("sites/" + site["dir"] + "/site.yaml"))}">site.yaml</a></span>'
            + (f'<span><a href="{e(href(site["readme"]))}">scripts/README.md</a></span>'
               if site["readme"] else "")
            + "</div>"
            + (f'<p class="desc">{e(site["desc"])}</p>' if site["desc"] else "")
            + f'<div class="meta">{"".join(meta)}</div>'
            + f'<div class="procs">{procs}</div>{pages}</article>')


# --------------------------------------------------------------------------

def render(base=LOCAL, fragment=False):
    """fragment=True omits the document wrapper, for a host that supplies its
    own <head> and <body> and only wants the page itself."""
    import inventory  # deferred: inventory.py imports this module to write it

    global BASE
    BASE = base

    sites = inventory.collect_sites()
    projects = inventory.collect_projects()
    workflows = inventory.collect_workflows()
    n_scripts = sum(s["scripts"] for s in sites)

    modes = {}
    for w in workflows:
        modes[w["mode"]] = modes.get(w["mode"], 0) + 1

    counts = [(len(sites), "sites"), (len(projects), "projects"),
              (len(workflows) + n_scripts, "processes"),
              (len(workflows), "workflows"), (n_scripts, "scripts"),
              (sum(s["pages"] for s in sites), "mapped pages")]

    o = []
    a = o.append
    if not fragment:
        a("<!doctype html>")
        a('<html lang="en"><head><meta charset="utf-8">')
        a('<meta name="viewport" content="width=device-width, initial-scale=1">')
    a("<title>SiteMapper</title>")
    a("<style>" + theme_block() + CSS + "</style>")
    if not fragment:
        a("</head><body>")

    a('<header class="top"><div class="wrap">')
    a("<h1>SiteMapper</h1>")
    a('<p class="sub">Every mapped site, every process that runs against it, and '
      "the projects that span them. "
      f'{", ".join(f"{v} {k}" for k, v in sorted(modes.items()))} by mode.</p>')
    a('<div class="counts">' + "".join(
        f"<div><b>{n}</b><span>{label}</span></div>" for n, label in counts) + "</div>")
    a('<div class="toolbar">')
    a('<input id="q" type="search" placeholder="Search sites, processes, pages — press /" '
      'autocomplete="off">')
    for group, label, values in (("kind", "kind", ["all", "workflow", "script"]),
                                 ("mode", "mode", ["all", "agentic", "deterministic"])):
        a(f'<div class="chips"><span class="chips-label">{label}</span>')
        for v in values:
            a(f'<button class="chip" data-group="{group}" data-value="{v}" '
              f'aria-pressed="{"true" if v == "all" else "false"}">{v}</button>')
        a("</div>")
    a('<span class="shown" id="shown"></span>')
    a("</div></div></header>")

    a('<div class="wrap">')

    a("<h2>Landscape</h2>")
    a(graph(projects, sites, workflows))
    # Rendered as a diagram by hosts that support Mermaid (GitHub, Artifacts),
    # plain text everywhere else. The SVG above needs no such support.
    a("<details><summary>Mermaid source for this graph</summary>"
      '<pre class="mermaid">'
      + e("\n".join(inventory.mermaid(projects, workflows).splitlines()[1:-1]))
      + "</pre></details>")

    a('<section data-group="projects"><h2>Projects</h2>')
    for p in projects:
        a(project_card(p, workflows))
    a("</section>")

    a('<section data-group="sites"><h2>Sites</h2>')
    for s in sites:
        a(site_card(s, workflows, projects))
    a("</section>")

    a('<p class="empty" id="none">Nothing matches that.</p>')

    a("<footer>Generated by <code>scripts/inventory.py</code> from the YAML in the "
      "SiteMapper repo — do not edit. "
      + ("A snapshot: it is republished by hand, so it is only as current as the "
         "day it was built. "
         if base != LOCAL else
         "<code>python scripts/check.py --only overview</code> fails when it is "
         "stale. ")
      + "This page lists the command that starts each process; it cannot run one "
        "itself.</footer>")
    a("</div>")
    a("<script>" + JS + "</script>")
    if not fragment:
        a("</body></html>")
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if docs/overview.html is stale")
    ap.add_argument("--links", choices=["local", "github"], default="local",
                    help="local: links relative to docs/ (the committed copy). "
                         "github: absolute, for a copy read outside a clone")
    ap.add_argument("--branch", default="main", help="branch for --links github")
    ap.add_argument("--base", help="link base, overriding --links")
    ap.add_argument("--out", help="write here instead of docs/overview.html")
    ap.add_argument("--fragment", action="store_true",
                    help="omit <html>/<head>/<body>, for a host that wraps the page")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import inventory

    base = args.base or (github_base(args.branch) if args.links == "github" else LOCAL)
    fresh = render(base, fragment=args.fragment)

    if args.check:
        current = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if current != fresh:
            print("FAIL  docs/overview.html is stale — run: python scripts/inventory.py")
            return 1
        print("docs/overview.html is current")
        return 0

    inventory.write(args.out or OUT, fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
