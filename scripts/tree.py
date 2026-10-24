"""Where the three roots of a SiteMapper tree are, and what lives under them.

Shared by check.py, inventory.py, run.py and serve.py so that all four agree on
one question: given a lib root, where are the projects and where do runs go?

    ROOT      the lib's own tree: sites/, apps/, config.yaml, docs/   (--root)
    PROJECTS  the questions: projects/<group>/.../<project>/            (--projects)
    RUNS      what runs write: runs/<lib>/<owner>/<run-id>/            (--runs)

Why three and not one. A deployment keeps every lib's data in ONE tree
(connectOS#29): the lib's folder holds what is written in the lib's own
language (maps, apps), while projects are lib-neutral and sit beside it, and
run output never enters git at all. Laid out:

    data/                   the one tree
      projects/             <- PROJECTS   (groups nest; a folder with project.yaml is a project)
      runs/                 <- RUNS       (produced; gitignored as a class)
      SiteMapper/           <- ROOT       (sites/, apps/, config.yaml)

The framework repo and a classic map repository keep projects/ and runs/ inside
ROOT. Resolution is by presence, so neither layout needs a flag:

    PROJECTS = --projects | ROOT/projects if it exists | ROOT/../projects if it exists | ROOT/projects
    RUNS     = --runs     | ROOT/runs     if it exists | ROOT/../runs     if it exists | ROOT/runs
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import socket
from pathlib import Path

import yaml

LIB = "SiteMapper"

# Tier names a deployment may use in apps/<app>/app.yaml and `tiers:` on a
# workflow, and the settings.policy.environment spellings they stand for. The
# check compares the two through this table, so `environment: production` on
# a site matches the tier key `prod`. Documented in schema/app.yaml.
TIER_SYNONYMS = {"production": "prod", "prod": "prod",
                 "staging": "stg", "stg": "stg",
                 "development": "dev", "dev": "dev"}

PROJECT_KINDS = ("test", "producer", "tool", "migration", "spike")
EFFECT_VALUES = ("read-only", "mutating", "destructive")
ROLLBACK_VALUES = ("snapshot", "none")
ACTIONS = ("navigate", "click", "input", "read", "assert", "verify", "wait", "key",
           "script", "human")
HUMAN_KINDS = ("approve", "login", "physical", "other")
SHAPE_TYPES = ("string", "number", "bool", "null")
DEFAULT_KEEP = "1d"


def shape_problem(shape, where: str = "shape") -> str:
    """What makes a script step's `shape` malformed, or "" (schema/workflow.yaml).
    A bare YAML null stands for the type name null."""
    if shape is None:
        return ""
    if isinstance(shape, str):
        return "" if shape in SHAPE_TYPES else \
            f"{where}: '{shape}' is not {' | '.join(SHAPE_TYPES)}"
    if isinstance(shape, list):
        if len(shape) > 1:
            return f"{where}: a list shape holds one item shape, not {len(shape)}"
        return shape_problem(shape[0], f"{where}[0]") if shape else ""
    if isinstance(shape, dict):
        for key, sub in shape.items():
            if not isinstance(key, str):
                return f"{where}: key {key!r} is not a string"
            problem = shape_problem(sub, f"{where}.{key}")
            if problem:
                return problem
        return ""
    return f"{where}: {shape!r} is not a type name, a mapping or a one-item list"

PHASES = ("setup", "snapshot", "steps")


def steps_of(workflow: dict) -> list[dict]:
    out = []
    for phase in PHASES + ("teardown",):
        out += [s for s in (workflow.get(phase) or []) if isinstance(s, dict)]
    return out


def fixture_values(w):
    """Every value each fixture name takes, across the common block and every
    tier's block."""
    values = {}
    for k, v in (w.get("fixtures") or {}).items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                values.setdefault(kk, set()).add(str(vv))
        else:
            values.setdefault(k, set()).add(str(v))
    return values


def step_sites(w):
    """Every site a workflow's steps resolve to, literal or through fixtures.

    A `$role` site resolves against every fixtures block (common and per tier),
    so an environment-parameterised workflow reports each tier's site. Returns
    (sites, unresolved) where unresolved lists the $names no fixture answers."""
    default = w.get("site")
    values = fixture_values(w)
    sites, unresolved = set(), set()
    for s in steps_of(w):
        ref = s.get("site") or default
        if not ref:
            continue
        ref = str(ref)
        if ref.startswith("$"):
            name = ref[1:]
            if name in values:
                sites |= values[name]
            else:
                unresolved.add(ref)
        else:
            sites.add(ref)
    return sites, unresolved


def tier_name(environment: str | None) -> str:
    """The tier key a settings.policy.environment value stands for."""
    env = str(environment or "").strip().lower()
    return TIER_SYNONYMS.get(env, env)


def _sibling(root: str, name: str, explicit: str | None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    inside = os.path.join(root, name)
    if os.path.isdir(inside):
        return inside
    beside = os.path.join(os.path.dirname(root), name)
    if os.path.isdir(beside):
        return beside
    return inside


def projects_root(root: str, explicit: str | None = None) -> str:
    return _sibling(os.path.abspath(root), "projects", explicit)


def runs_root(root: str, explicit: str | None = None) -> str:
    return _sibling(os.path.abspath(root), "runs", explicit)


def instance_name() -> str:
    """The machine a run happened on. Part of every run id, so two users'
    runs are distinct folders and a sync never has to merge them."""
    return os.environ.get("SITEMAPPER_INSTANCE") or socket.gethostname()


def iter_projects(projects: str):
    """Every project under PROJECTS, recursively: (rel, dir).

    `rel` is the path from PROJECTS with forward slashes, e.g.
    'connect-testing/shop-order-test'; it is the project's identity in every
    view, so two groups may hold projects of the same folder name. A folder
    with project.yaml is a project and is not descended into; any other folder
    is a group (with or without group.yaml) and is."""
    out = []
    if not os.path.isdir(projects):
        return out
    for cur, dirs, names in os.walk(projects):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        if "project.yaml" in names and os.path.abspath(cur) != os.path.abspath(projects):
            out.append((os.path.relpath(cur, projects).replace(os.sep, "/"), cur))
            dirs[:] = []
    return out


def iter_groups(projects: str):
    """Every group folder under PROJECTS: (rel, dir, has_group_yaml). The root
    itself is not a group."""
    out = []
    if not os.path.isdir(projects):
        return out
    for cur, dirs, names in os.walk(projects):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        if "project.yaml" in names and os.path.abspath(cur) != os.path.abspath(projects):
            dirs[:] = []
            continue
        if os.path.abspath(cur) != os.path.abspath(projects):
            out.append((os.path.relpath(cur, projects).replace(os.sep, "/"), cur,
                        "group.yaml" in names))
    return out


def iter_apps(root: str):
    """Every app under ROOT/apps: (name, dir)."""
    base = os.path.join(root, "apps")
    if not os.path.isdir(base):
        return []
    return [(d, os.path.join(base, d)) for d in sorted(os.listdir(base))
            if os.path.isfile(os.path.join(base, d, "app.yaml"))]


def parse_keep(value) -> _dt.timedelta | None:
    """How long a run folder lives: `Nd`, `Nh`, or `keep` (None: never swept).
    Empty or unparseable means the default, one day."""
    text = str(value or "").strip().lower()
    if text == "keep":
        return None
    m = re.fullmatch(r"(\d+)\s*([dh])", text)
    if not m:
        return _dt.timedelta(days=1)
    n = int(m.group(1))
    return _dt.timedelta(days=n) if m.group(2) == "d" else _dt.timedelta(hours=n)


_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _run_record(folder: str) -> dict | None:
    try:
        with open(os.path.join(folder, "run.yaml"), encoding="utf-8") as fh:
            run = (yaml.load(fh, Loader=_LOADER) or {}).get("run")
    except (OSError, yaml.YAMLError, AttributeError):
        return None
    return run if isinstance(run, dict) else None


def _timestamp(value) -> _dt.datetime | None:
    try:
        ts = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=_dt.timezone.utc)


def sweep_runs(runs_root, now: _dt.datetime | None = None,
               dry_run: bool = False) -> list[Path]:
    """Delete every run folder under RUNS whose `keep` has run out, for every
    lib: runs/<lib>/<owner...>/<run-id>/run.yaml (schema/run.yaml). Returns
    the folders removed, or that would be with dry_run.

    A folder is a run only if its run.yaml reads as a record with a time
    (finished_at, else started_at). Anything else, such as a folder a
    migration parked in the store, is never touched."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    removed = []
    if not os.path.isdir(runs_root):
        return removed
    for cur, dirs, names in os.walk(runs_root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        if "run.yaml" not in names:
            continue
        dirs[:] = []
        run = _run_record(cur)
        if run is None:
            continue
        ended = _timestamp(run.get("finished_at") or run.get("started_at"))
        keep = parse_keep(run.get("keep"))
        if ended is None or keep is None or ended + keep > now:
            continue
        if not dry_run:
            shutil.rmtree(cur)
        removed.append(Path(cur))
    return removed
