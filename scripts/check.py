#!/usr/bin/env python3
"""Check that the repo is internally consistent. Exits non-zero on any failure.

Usage:
    python scripts/check.py                    # run everything, on this repo
    python scripts/check.py --only links       # run one check
    python scripts/check.py --list             # show check names
    python scripts/check.py --root ../my-maps  # check a separate map repository

`--root` exists because the maps this was written to protect usually live in a
different (private) repository. Schemas and bindings still come from THIS repo —
see the two-roots note below — so there is one tool and one schema, not a copy
per map repo that drifts out of sync.

Every check here exists because the thing it catches actually happened. None of
them need an LLM: they are enumeration and comparison, which is code's job (see
docs/CODE_OVER_LLM.md). What this CANNOT check is whether prose is still true —
that still needs a human reading it.

Add a check when you find a class of drift that a script could have caught.
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

# TWO ROOTS, DELIBERATELY.
#
# HOME is this script's own repository: the framework. It owns schema/*.yaml,
# docs/ and the .claude bindings, and those do NOT travel with a map repository.
# ROOT is the tree being checked, which defaults to HOME and is repointed by
# --root at a separate (usually private) repository of maps.
#
# The distinction matters because the alternative is to copy this script and the
# schemas next to the maps, and a FORKED SCHEMA IS WORSE THAN NO CHECK: the copy
# drifts, the maps validate green against a contract nobody updated, and the
# check reports health it cannot know about. One tool, many trees.
HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = HOME

# Where the user actually stood when they typed the command. Captured BEFORE the
# chdir below, because a relative --root has to resolve against the shell's cwd,
# not against this repo. Getting that wrong is not a small bug: `--root .` from a
# map repository resolved to the framework instead and reported it green, which
# is a check lying about a tree it never looked at.
INVOCATION_CWD = os.getcwd()

os.chdir(ROOT)


def home(*parts):
    """A path inside the framework repo, wherever ROOT currently points."""
    return norm(os.path.join(HOME, *parts))


def external():
    return os.path.abspath(ROOT) != os.path.abspath(HOME)

NOTES = []
# Checks that declined to run. Reported as 'skipped', never as 'ok' — a check
# that did not run must not read like one that passed.
SKIPPED = set()

WORKFLOW_GLOBS = ["sites/*/workflows/*.yaml", "projects/*/workflows/*.yaml"]
DOC_GLOBS = ["README.md", "USAGE.md", "PRD.md", "Concept.md", "CLAUDE.md",
             "CODEX.md", "docs/**/*.md"]


def norm(p):
    return p.replace("\\", "/")


def files(patterns):
    out = []
    for p in patterns:
        out += [norm(f) for f in glob.glob(p, recursive=True)]
    return sorted(set(out))


def load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def top_keys(path, top):
    d = load(path)
    return set((d.get(top) or {}).keys())


def exists_cased(path):
    """os.path.exists is case-INSENSITIVE on Windows/NTFS, so a link whose case
    does not match the file resolves here and breaks on Linux CI or a
    case-sensitive volume. Compare against the real directory listing instead."""
    path = os.path.normpath(path)
    if not os.path.exists(path):
        return False
    parts = path.replace("\\", "/").split("/")
    cur = ""
    for i, part in enumerate(parts):
        if part in ("", ".", ".."):
            cur = os.path.join(cur, part) if cur else part
            continue
        try:
            entries = os.listdir(cur or ".")
        except OSError:
            return False
        if part not in entries:
            return False
        cur = os.path.join(cur, part) if cur else part
    return True


def strip_fences(text):
    """Markdown links inside code fences are examples, not references."""
    return re.sub(r"```.*?```", "", text, flags=re.S)


# --------------------------------------------------------------------------
# checks: each returns a list of failure strings
# --------------------------------------------------------------------------

def check_yaml():
    """Every YAML file parses."""
    fails = []
    for f in files(["config.yaml", "schema/*.yaml", "sites/**/*.yaml",
                    "projects/**/*.yaml", "data/**/*.yaml"]):
        try:
            load(f)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            line = mark.line + 1 if mark else "?"
            fails.append(f"{f}:{line}  {getattr(e, 'problem', e)}")
    return fails


# (top-level key, schema file — always in HOME, globs — always under ROOT)
SCHEMA_MAP = [
    ("site", "schema/site.yaml", ["sites/*/site.yaml"]),
    ("project", "schema/project.yaml", ["projects/*/project.yaml"]),
    ("page", "schema/page.yaml", ["sites/*/pages/*.yaml"]),
    ("workflow", "schema/workflow.yaml", WORKFLOW_GLOBS),
]


def check_schema():
    """Files use no top-level key the schema does not define, and vice versa.

    Shallow on purpose: the schemas are commented YAML templates, and those
    comments are real documentation. A key-set diff catches the drift we hit
    without forcing a rewrite to JSON Schema that would gut them.
    """
    fails = []
    for top, schema, pats in SCHEMA_MAP:
        # The schema is the framework's; the files are the checked tree's.
        schema = home(schema)
        if not os.path.exists(schema):
            fails.append(f"missing schema: {schema}")
            continue
        allowed = top_keys(schema, top)
        used = set()
        for f in files(pats):
            extra = top_keys(f, top) - allowed
            used |= top_keys(f, top)
            if extra:
                fails.append(f"{f}: key(s) not in {schema}: {sorted(extra)}")
        unused = allowed - used
        if unused:
            # Not a failure: an optional key written by tooling (verified_at) is
            # legitimately absent until that tooling has run. Worth surfacing so a
            # schema documenting something that never existed still gets noticed.
            NOTES.append(f"{schema}: defines key(s) no file currently uses: {sorted(unused)}")
    return fails


def check_listings():
    """site.yaml / project.yaml agree with what is on disk, and refs resolve."""
    fails = []
    for sd in sorted(glob.glob("sites/*")):
        sd = norm(sd)
        sy = f"{sd}/site.yaml"
        if not os.path.exists(sy):
            fails.append(f"{sd}: no site.yaml")
            continue
        s = load(sy).get("site") or {}
        for key, sub in (("pages", "pages"), ("workflows", "workflows")):
            listed = set(s.get(key) or [])
            actual = {os.path.basename(f) for f in glob.glob(f"{sd}/{sub}/*.yaml")}
            for m in sorted(listed - actual):
                fails.append(f"{sy}: {key} lists '{m}' but the file does not exist")
            for m in sorted(actual - listed):
                fails.append(f"{sy}: {sub}/{m} exists but is not listed under {key}")
        declared = {x.get("name") for x in (s.get("scripts") or []) if isinstance(x, dict)}
        on_disk = {os.path.basename(f) for f in glob.glob(f"{sd}/scripts/*")
                   if os.path.isfile(f) and os.path.basename(f) not in
                   ("README.md", "requirements.txt")}
        for m in sorted(declared - on_disk):
            fails.append(f"{sy}: scripts declares '{m}' but the file does not exist")
        if not s.get("mapped_at"):
            fails.append(f"{sy}: no mapped_at")

    for pd_ in sorted(glob.glob("projects/*")):
        pd_ = norm(pd_)
        py = f"{pd_}/project.yaml"
        if not os.path.exists(py):
            fails.append(f"{pd_}: no project.yaml")
            continue
        p = load(py).get("project") or {}
        listed = set(p.get("workflows") or [])
        actual = {os.path.basename(f) for f in glob.glob(f"{pd_}/workflows/*.yaml")}
        for m in sorted(listed - actual):
            fails.append(f"{py}: workflows lists '{m}' but the file does not exist")
        for m in sorted(actual - listed):
            fails.append(f"{py}: workflows/{m} exists but is not listed")
        for s in p.get("sites") or []:
            if not os.path.isdir(f"sites/{s}"):
                fails.append(f"{py}: sites references '{s}', which is not a directory under sites/")

    # workflow -> site references (this is what iot-portal broke)
    for f in files(WORKFLOW_GLOBS):
        w = load(f).get("workflow") or {}
        for s in (w.get("sites") or ([w.get("site")] if w.get("site") else [])):
            s = str(s)
            if s.startswith("$"):
                continue  # environment-parameterised; resolved at run time
            if not os.path.isdir(f"sites/{s}"):
                fails.append(f"{f}: site '{s}' is not a directory under sites/")
        if not w.get("mode"):
            fails.append(f"{f}: no `mode` — a runner cannot tell if this needs an LLM")
    return fails


def check_companions():
    """Every workflow YAML has its sibling .md (USAGE.md + schema require it)."""
    return [f"{f}: no companion {os.path.basename(f)[:-5]}.md"
            for f in files(WORKFLOW_GLOBS) if not os.path.exists(f[:-5] + ".md")]


def check_links():
    """Markdown links and page `screenshot:` paths resolve."""
    fails = []
    for f in files(DOC_GLOBS):
        base = os.path.dirname(f)
        for m in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", strip_fences(open(f, encoding="utf-8").read())):
            t = m.group(1)
            if t.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target = os.path.join(base, t.split("#")[0])
            if not os.path.exists(os.path.normpath(target)):
                fails.append(f"{f}: broken link -> {t}")
            elif not exists_cased(target):
                fails.append(f"{f}: link case does not match the file -> {t} "
                             "(resolves on Windows, breaks on Linux/CI)")
    for f in files(["sites/*/pages/*.yaml"]):
        shot = (load(f).get("page") or {}).get("screenshot")
        if shot and not os.path.exists(os.path.join(os.path.dirname(os.path.dirname(f)), shot)):
            fails.append(f"{f}: screenshot -> {shot} does not exist")
    return fails


def check_bindings():
    """Neutral docs are registered, and host bindings point at one that exists.

    Catches both halves of the orphan problem: a doc nobody can navigate to
    (INTERFACE.md was orphaned for weeks) and a binding pointing at nothing.
    """
    # Framework-only. A map repository has no docs/skills/ and no .claude/
    # bindings — those belong to the tool, not to the maps — so running this
    # against --root would check nothing and report success, which is worse than
    # saying so out loud.
    if external():
        SKIPPED.add("bindings")
        NOTES.append("bindings: framework-only — docs/skills and .claude bindings "
                     "belong to the tool, not to a map repository")
        return []

    fails = []
    index = open("docs/INDEX.md", encoding="utf-8").read() if os.path.exists("docs/INDEX.md") else ""
    agents = open("docs/AGENTS.md", encoding="utf-8").read() if os.path.exists("docs/AGENTS.md") else ""
    reachable = index + agents

    for f in files(["docs/*.md", "docs/skills/*.md", "docs/subagents/*.md"]):
        name = os.path.basename(f)
        if name in ("INDEX.md", "AGENTS.md", "inventory.md"):
            continue
        if name not in reachable:
            fails.append(f"{f}: not referenced from docs/INDEX.md or docs/AGENTS.md")

    # a binding must point at a neutral doc that exists, and carry no instructions
    for f in files([".claude/skills/*/SKILL.md", ".claude/agents/*.md"]):
        body = open(f, encoding="utf-8").read()
        refs = re.findall(r"docs/(?:skills|subagents)/[\w.-]+\.md", body)
        if not refs:
            fails.append(f"{f}: binding does not point at a docs/ instruction file")
        for r in refs:
            if not os.path.exists(r):
                fails.append(f"{f}: points at {r}, which does not exist")
        if len(body.splitlines()) > 25:
            fails.append(f"{f}: {len(body.splitlines())} lines — a binding should be "
                         "frontmatter plus a pointer, not instructions")

    for f in files(["docs/skills/*.md"]):
        stem = os.path.basename(f)[:-3]
        alt = {"run-workflow": "run"}.get(stem, stem)
        if not os.path.exists(f".claude/skills/{alt}/SKILL.md"):
            fails.append(f"{f}: no .claude/skills/{alt}/SKILL.md binding")
    return fails


def generated_is_stale(module, out_attr="OUT"):
    # The generators are the framework's (import from HOME); the tree they walk
    # is the checked one (set_root to ROOT). Both must be set, or a --root run
    # silently regenerates the framework's own views instead.
    sys.path.insert(0, os.path.join(HOME, "scripts"))
    mod = __import__(module)
    if external():
        mod.set_root(ROOT)
        __import__("inventory").set_root(ROOT)
    out = getattr(mod, out_attr)
    cur = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    if cur != mod.render():
        hint = f" --root {norm(ROOT)}" if external() else ""
        return [f"{norm(os.path.relpath(out, ROOT))} is stale — "
                f"run: python scripts/inventory.py{hint}"]
    return []


def check_inventory():
    """docs/inventory.md is current."""
    return generated_is_stale("inventory")


def check_overview():
    """docs/overview.html is current."""
    return generated_is_stale("overview")


CHECKS = {
    "yaml": check_yaml,
    "schema": check_schema,
    "listings": check_listings,
    "companions": check_companions,
    "links": check_links,
    "bindings": check_bindings,
    "inventory": check_inventory,
    "overview": check_overview,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", choices=sorted(CHECKS), help="run a single check")
    ap.add_argument("--list", action="store_true", help="list check names")
    ap.add_argument("--root", help="check this tree instead of the script's own repo "
                                   "(e.g. a private map repository). Schemas and "
                                   "bindings still come from the framework.")
    args = ap.parse_args()

    if args.root:
        global ROOT
        ROOT = os.path.abspath(os.path.join(INVOCATION_CWD, args.root))
        if not os.path.isdir(ROOT):
            sys.exit(f"--root is not a directory: {ROOT}")
        os.chdir(ROOT)
        print(f"checking {norm(ROOT)}  (schemas from {norm(HOME)})")
        print()

    if args.list:
        for name, fn in sorted(CHECKS.items()):
            print(f"{name:12} {(fn.__doc__ or '').splitlines()[0]}")
        return 0

    selected = [args.only] if args.only else list(CHECKS)
    total = 0
    for name in selected:
        fails = CHECKS[name]()
        total += len(fails)
        status = ("skipped" if name in SKIPPED
                  else "ok" if not fails else f"{len(fails)} FAILED")
        print(f"[{name}] {status}")
        for msg in fails:
            print(f"  FAIL  {msg}")
    for msg in NOTES:
        print(f"  note  {msg}")
    skipped = SKIPPED & set(selected)
    tail = f", {len(skipped)} skipped" if skipped else ""
    print(f"\n{len(selected) - len(skipped)} checks run, {total} failures, "
          f"{len(NOTES)} notes{tail}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
