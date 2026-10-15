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

import os
import socket

LIB = "SiteMapper"

# Tier names a deployment may use in apps/<app>/app.yaml and `tiers:` on a
# workflow, and the settings.policy.environment spellings they stand for. The
# check compares the two through this table, so `environment: production` on
# a site matches the tier key `prod`. Documented in schema/app.yaml.
TIER_SYNONYMS = {"production": "prod", "prod": "prod",
                 "staging": "stg", "stg": "stg",
                 "development": "dev", "dev": "dev"}

PROJECT_KINDS = ("test", "producer", "tool", "migration", "spike")
ROLLBACK_VALUES = ("snapshot", "none")
DEFAULT_KEEP = "1d"


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
