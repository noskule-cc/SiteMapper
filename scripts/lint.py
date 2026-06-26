#!/usr/bin/env python3
"""Validate that every YAML file in the repo parses.

Usage:
    python scripts/lint.py

Exits non-zero if any file fails to parse. Requires PyYAML (pip install pyyaml).

Common gotcha this catches: a list item that *starts* with a double-quoted
phrase but has trailing text, e.g.

    - "Save All" commits everything      # BROKEN: parsed as a quoted scalar

Wrap the whole value in single quotes instead:

    - '"Save All" commits everything'    # OK
"""
import glob
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not installed. Run: python -m pip install pyyaml")

PATTERNS = ["config.yaml", "schema/*.yaml", "sites/**/*.yaml", "projects/**/*.yaml"]


def main() -> int:
    files = sorted({f for p in PATTERNS for f in glob.glob(p, recursive=True)})
    failures = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                yaml.safe_load(fh)
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            line = mark.line + 1 if mark else "?"
            failures.append((f, line, getattr(e, "problem", str(e))))

    for f, line, msg in failures:
        print(f"FAIL  {f}:{line}  {msg}")

    print(f"\n{len(files)} files checked, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
