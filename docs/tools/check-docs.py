#!/usr/bin/env python3
"""Structural documentation checks for aiDocs-based projects (issue #33).

Single entry point, stdlib only. Exit 1 on errors, 0 otherwise (warnings
don't fail the build). Runs identically in a consuming project and in the
aiDocs standard repo: standardized per-project filenames that only exist
after /setup are reported as warnings, never errors.

Usage: python docs/tools/check-docs.py [--root <repo-root>]
"""

import argparse
import re
import sys
from pathlib import Path

# Standardized per-project names: created by /setup, so a dangling link to
# them is a warning (missing setup step), not a broken link.
PER_PROJECT = {
    "installation.md", "development.md", "testing.md", "release.md",
    "changelog.md", "coding-guidelines.md", "architecture-rules.md",
    "issue-tracker.md", "wiki.md", "design-sync.md", "project-index.md",
    "skills-and-agents.md", "tools/jobs.md", "feature-map.md",
    "tools/evals.md",
}

# Entry points and registries are never orphans.
NON_ORPHANS = {"INDEX.md", "AGENTS.md", "README.md", "project-index.md",
               "skills-and-agents.md"}

SKIP_DIRS = {".venv", "venv", "__pycache__", "node_modules", "site-packages"}

# Feature-map entry points are verified against these source files.
SOURCE_EXT = {".kt", ".kts", ".java", ".swift", ".ts", ".tsx", ".js",
              ".jsx", ".py", ".cs", ".go", ".rs", ".cpp", ".cc", ".c",
              ".h", ".m", ".mm", ".dart", ".rb", ".php", ".vue"}
SOURCE_SKIP = SKIP_DIRS | {".git", "build", "dist", "out", "target",
                           ".gradle", ".idea", "docs"}


def md_files(base: Path):
    for md in base.rglob("*.md"):
        if not SKIP_DIRS & set(md.parts):
            yield md

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")

errors, warnings = [], []


def error(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def exists_cased(path: Path) -> bool:
    """True if path exists with exactly this casing (NTFS hides case bugs
    that break on Linux CI)."""
    if not path.exists():
        return False
    cur = path
    while cur != cur.parent:
        if cur.name not in [p.name for p in cur.parent.iterdir()]:
            return False
        cur = cur.parent
    return True


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def check_links(root: Path, docs: Path):
    """Every relative markdown link resolves, with exact casing."""
    linked = set()
    for md in md_files(docs):
        in_fence = False
        for lineno, line in enumerate(
                md.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            if in_fence:
                continue
            for target in LINK_RE.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = target.split("#")[0]
                if not target:
                    continue
                dest = (md.parent / target).resolve()
                where = f"{rel(root, md)}:{lineno}"
                if not dest.is_relative_to(root):
                    continue  # outside the repo (e.g. ../../wiki GitHub URL)
                try:
                    dest_rel = rel(docs, dest)
                except ValueError:
                    dest_rel = None  # points outside docs/ (e.g. ../SECURITY.md)
                if dest.exists():
                    if not exists_cased(dest):
                        error(f"{where}: link '{target}' differs in casing "
                              f"from the file on disk")
                    if dest_rel:
                        linked.add(dest_rel)
                elif dest_rel in PER_PROJECT:
                    warn(f"{where}: '{target}' not created yet "
                         f"(standardized per-project file - run /setup)")
                else:
                    error(f"{where}: broken link '{target}'")
    return linked


def check_orphans(docs: Path, linked: set):
    """Every docs page is reachable from some other page."""
    for md in md_files(docs):
        r = md.relative_to(docs).as_posix()
        if r in NON_ORPHANS or r in linked or ".template." in md.name:
            continue
        if r.startswith(("features/", "project/", "testing/")):
            continue  # collections, reached via their own conventions
        warn(f"docs/{r}: orphan - not linked from any other doc")


def check_registration(root: Path, docs: Path):
    """Agents and active skills are listed in the skills-and-agents registry.

    The filled registry is docs/skills-and-agents.md; the standard repo only
    carries the template, which serves as fallback."""
    registry = docs / "skills-and-agents.md"
    if not registry.exists():
        registry = docs / "skills-and-agents.template.md"
    if not registry.exists():
        error("docs/skills-and-agents.md missing (and no template)")
        return
    text = registry.read_text(encoding="utf-8", errors="replace")
    reg_name = rel(root, registry)
    agents_dir = root / ".claude" / "agents"
    if agents_dir.is_dir():
        for agent in agents_dir.glob("*.md"):
            if ".template" in agent.name:
                continue
            if agent.name not in text and agent.stem not in text:
                error(f".claude/agents/{agent.name}: not listed in {reg_name}")
    skills_dir = root / ".claude" / "skills"
    if skills_dir.is_dir():
        for skill in skills_dir.glob("*/SKILL.md"):
            if skill.parent.name not in text:
                warn(f".claude/skills/{skill.parent.name}: active skill not "
                     f"listed in {reg_name}")
        for skill in skills_dir.glob("*/SKILL.md.template"):
            if skill.parent.name not in text:
                warn(f".claude/skills/{skill.parent.name}: template skill "
                     f"not listed in {reg_name}")


def check_feature_map(root: Path, docs: Path):
    """Entry points named in feature-map.md still resolve in the source tree
    (issue #35): a stale anchor becomes a CI failure, not a quarterly
    discovery. Backticked names in the 'Entry point' column are split on
    dots and each segment must appear in some source file."""
    fmap = docs / "feature-map.md"
    if not fmap.exists():
        return
    wanted = {}  # identifier segment -> [(lineno, raw entry point)]
    for lineno, line in enumerate(
            fmap.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[1]) <= set("-: "):
            continue  # separator row or malformed
        for ident in re.findall(r"`([^`]+)`", cells[1]):
            if "[" in ident:
                continue  # unfilled placeholder
            base = re.split(r"[(<]", ident)[0]
            for seg in re.split(r"[.:#/]", base):
                if seg.strip():
                    wanted.setdefault(seg.strip(), []).append((lineno, ident))
    unresolved = set(wanted)
    for src in root.rglob("*"):
        if not unresolved:
            break
        if src.suffix not in SOURCE_EXT or SOURCE_SKIP & set(src.parts):
            continue
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        unresolved = {n for n in unresolved if n not in text}
    for name in sorted(unresolved):
        for lineno, ident in wanted[name]:
            error(f"docs/feature-map.md:{lineno}: entry point '{ident}' - "
                  f"'{name}' not found in any source file (stale anchor?)")


def check_standard_references(root: Path, docs: Path):
    """Every shipped docs template is referenced from INDEX.md and the setup
    skill, so a new standard file cannot be orphaned inside the standard
    itself (issue #38). No-ops in consuming projects, where templates are
    deleted on instantiation."""
    index = docs / "INDEX.md"
    setup = root / ".claude" / "skills" / "setup" / "SKILL.md"
    index_text = index.read_text(encoding="utf-8", errors="replace") \
        if index.exists() else ""
    setup_text = setup.read_text(encoding="utf-8", errors="replace") \
        if setup.exists() else ""
    for tpl in md_files(docs):
        if ".template." not in tpl.name:
            continue
        filled = tpl.name.replace(".template", "")
        stem = filled.rsplit(".", 1)[0]
        where = rel(root, tpl)
        if index_text and filled not in index_text:
            error(f"{where}: filled name '{filled}' not referenced "
                  f"in docs/INDEX.md")
        if setup_text and stem not in setup_text:
            error(f"{where}: '{stem}' not referenced in the setup skill")


def check_template_copies(root: Path, docs: Path):
    """Templates are instantiate-and-delete: never next to their filled copy."""
    for area in (docs, root / ".claude"):
        if not area.is_dir():
            continue
        for tpl in area.rglob("*.template*"):
            filled = tpl.with_name(tpl.name.replace(".template", ""))
            if filled.exists():
                error(f"{rel(root, tpl)}: template coexists with its filled "
                      f"copy {filled.name} - delete the template "
                      f"(instantiate-and-delete)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    docs = root / "docs"
    if not docs.is_dir():
        print(f"error: no docs/ under {root}", file=sys.stderr)
        return 1

    linked = check_links(root, docs)
    check_orphans(docs, linked)
    check_registration(root, docs)
    check_feature_map(root, docs)
    check_standard_references(root, docs)
    check_template_copies(root, docs)

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\ncheck-docs: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
