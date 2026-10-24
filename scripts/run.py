"""Headless deterministic workflow runner (#18/#20).

    python scripts/run.py <workflow> [--param key=value ...] [--root PATH]
                          [--projects PATH] [--runs PATH] [--json] [--headed] [--record]
    python scripts/run.py <workflow> --preflight [--json] [--param ...] [--persona NAME]
    python scripts/run.py --sweep [--root PATH] [--runs PATH] [--dry-run]

Executes a `mode: deterministic` workflow against its mapped site(s) with no
LLM in the loop, and emits the neutral `result` object (schema/result.yaml).
LLM for decisions, code for work (docs/code-over-llm.md): the map must be
complete enough that no step needs judgement — if it isn't, this runner fails
loudly and the repair loop (an LLM, on demand) fixes the map.

Browser automation is Playwright driving the installed Chrome
(channel="chrome"): its auto-waiting covers ordinary load waiting, so
workflows carry no generic sleeps. Playwright is imported lazily, and only
when a step needs the browser: a workflow of `script` and `human` steps (a dataset
producer on a scheduler) runs without Chrome or Playwright, as does every
other script in this repo.

`--root` points at a separate (usually private) map repository, same
semantics as check.py / inventory.py. `--projects` and `--runs` point at the
projects tree and the runs store when they are not inside the root
(scripts/tree.py says how both are found without the flags).
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as _dt
import functools
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tree  # noqa: E402

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent

# Actions a deterministic workflow may contain. `verify` needs judgement, so
# its presence (or mode: agentic) makes the workflow un-runnable here.
MECHANICAL_ACTIONS = set(tree.ACTIONS) - {"verify"}

@dataclasses.dataclass(frozen=True)
class FailureClass:
    next: str                  # the one next step; {workflow} and {hint} are filled in
    hint: str                  # {hint} when the raise site gives none
    may_downgrade_trust: bool  # only a failure the map caused may set trust: broken


# What a run's outcome means for the map, and the one thing to do about it
# (schema/result.yaml). Only drift and assert are the map's fault.
CLASSES = {
    "ok": FailureClass("", "", False),
    "input": FailureClass("run {workflow} again with {hint}", "the inputs the error names",
                          False),
    "refused": FailureClass("{hint}", "ask the site's owner whether this run may happen "
                            "(docs/permissions.md)", False),
    "auth": FailureClass("{hint}", "refresh the persona's session: run {workflow} once "
                         "--headed with a persona whose auth is human", False),
    "drift": FailureClass("/repair {workflow}", "", True),
    "assert": FailureClass("compare {hint} with the live page before you patch the map",
                           "the failed assertion", True),
    "error": FailureClass("{hint}", "fix what the error names, then run {workflow} again",
                          False),
}


def next_step(cls: str, workflow: str, hint: str = "") -> str:
    entry = CLASSES[cls]
    return entry.next.replace("{hint}", hint or entry.hint).replace("{workflow}", workflow)


class RunError(Exception):
    """Fatal runner error — maps to result.status = error, with its class."""

    def __init__(self, message: str, cls: str = "error", hint: str = ""):
        super().__init__(message)
        self.cls = cls
        self.hint = hint


class WaitForPerson(Exception):
    def __init__(self, step: int, label: str, reason: str):
        super().__init__(f"step {step}: {label}")
        self.waiting_for = {"step": step, "label": label, "reason": reason}


# ---------------------------------------------------------------------------
# Loading

def load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Owner:
    """Where a workflow lives: a site or a project. Carries what the runner
    needs from that home — its name for the run record, its project.yaml
    (scripts, app, keep) when it is a project."""

    def __init__(self, kind: str, name: str, directory: Path, project: dict | None = None):
        self.kind = kind            # site | project
        self.name = name            # site name, or the project's path under projects/
        self.dir = directory
        self.project = project or {}


def iter_workflows(root: Path, projects: Path) -> list[tuple[Path, Owner]]:
    candidates: list[tuple[Path, Owner]] = []
    for path in sorted(root.glob("sites/*/workflows/*.yaml")):
        candidates.append((path, Owner("site", path.parent.parent.name, path.parent.parent)))
    for rel, pd_ in tree.iter_projects(str(projects)):
        pdir = Path(pd_)
        project = (load_yaml(pdir / "project.yaml") or {}).get("project", {})
        for path in sorted((pdir / "workflows").glob("*.yaml")):
            candidates.append((path, Owner("project", rel, pdir, project)))
    return candidates


def find_workflow(root: Path, projects: Path, name: str):
    candidates = iter_workflows(root, projects)
    for path, owner in candidates:
        if path.stem == name:
            return path, load_yaml(path), owner
    for path, owner in candidates:  # fall back to the name: field
        data = load_yaml(path)
        wf = (data or {}).get("workflow", {})
        if wf.get("name") == name:
            return path, data, owner
    raise RunError(
        f"no workflow named '{name}' under {root}/sites/*/workflows or {projects}",
        "input", "a workflow name that list_workflows shows")


class Site:
    """One mapped site: config, settings and its page maps."""

    def __init__(self, root: Path, site_name: str):
        self.name = site_name
        self.dir = root / "sites" / site_name
        site_file = self.dir / "site.yaml"
        if not site_file.is_file():
            raise RunError(f"site '{site_name}' has no {site_file}")
        self.config = (load_yaml(site_file) or {}).get("site") or {}
        self.base_url = (self.config.get("base_url") or "").rstrip("/")

    @functools.cached_property
    def pages(self):
        return {f.stem: (load_yaml(f) or {}).get("page") or {}
                for f in (self.dir / "pages").glob("*.yaml")}

    def page(self, page_name: str):
        if page_name not in self.pages:
            raise RunError(f"site '{self.name}' has no page map '{page_name}'", "drift")
        return self.pages[page_name]

    def element(self, page_name: str, element_name: str):
        for el in self.page(page_name).get("elements") or []:
            if el.get("name") == element_name:
                return el
            for child in el.get("children") or []:
                if child.get("name") == element_name:
                    return child
        raise RunError(
            f"page '{page_name}' ({self.name}) maps no element '{element_name}'", "drift"
        )


def load_apps(root: Path) -> dict[str, dict]:
    """name -> app dict, with the app's directory under '_dir'."""
    out = {}
    for name, ad in tree.iter_apps(str(root)):
        app = (load_yaml(Path(ad) / "app.yaml") or {}).get("app", {})
        app["_dir"] = Path(ad)
        out[name] = app
    return out


def app_of_site(apps: dict[str, dict], site_name: str):
    for name, app in apps.items():
        if site_name in (app.get("tiers") or {}).values():
            return name, app
    return None, None


def load_persona(root: Path, site_name: str, persona_name: str | None):
    """Resolve the persona for a site: --persona, else the site's only one,
    else anonymous (None). Site-scoped: sites/<site>/personas/<name>.yaml."""
    pdir = root / "sites" / site_name / "personas"
    files = sorted(pdir.glob("*.yaml")) if pdir.is_dir() else []
    if persona_name:
        for f in files:
            if f.stem == persona_name:
                return (load_yaml(f) or {}).get("persona") or {}
        raise RunError(f"site '{site_name}' has no persona '{persona_name}' "
                       f"({[f.stem for f in files] or 'none defined'})", "input",
                       f"--persona <one of {[f.stem for f in files]}>")
    if len(files) == 1:
        return (load_yaml(files[0]) or {}).get("persona") or {}
    if not files:
        return None
    raise RunError(f"site '{site_name}' has several personas "
                   f"({[f.stem for f in files]}) — pass --persona", "input",
                   f"--persona <one of {[f.stem for f in files]}>")


def load_context(root: Path, site_name: str, context_name: str | None,
                 workflow: dict):
    """Resolve the tenant context (#8): --context, else the site's only one.
    Check the workflow's `requires:` contract against it — fail fast."""
    cdir = root / "sites" / site_name / "contexts"
    files = sorted(cdir.glob("*.yaml")) if cdir.is_dir() else []
    required = (workflow.get("requires") or {}).get("context") or {}
    context = None
    if context_name:
        match = [f for f in files if f.stem == context_name]
        if not match:
            raise RunError(f"site '{site_name}' has no context '{context_name}' "
                           f"({[f.stem for f in files] or 'none defined'})", "input",
                           f"--context <one of {[f.stem for f in files]}>")
        context = load_yaml(match[0]).get("context", {})
    elif required and len(files) == 1:
        context = load_yaml(files[0]).get("context", {})
    elif required and files:
        raise RunError(f"workflow requires a context and site '{site_name}' has "
                       f"several ({[f.stem for f in files]}) — pass --context", "input",
                       f"--context <one of {[f.stem for f in files]}>")
    elif required:
        raise RunError(f"workflow declares `requires.context` but site "
                       f"'{site_name}' has no contexts/ directory")
    if context is not None:
        missing = [r for r in (required.get("roles") or [])
                   if r not in (context.get("roles") or {})]
        missing += [i for i in (required.get("ids") or [])
                    if i not in (context.get("ids") or {})]
        if missing:
            raise RunError(
                f"context '{context.get('name')}' does not satisfy the workflow's "
                f"requires: missing {missing} — a bad pairing fails up front, "
                "not mid-run (schema/context.yaml)", "input",
                "--context <one that has the roles and ids the workflow requires>")
    return context


def state_path(root: Path, site_name: str, persona: dict) -> Path:
    """Saved browser state: a credential, so always local and gitignored."""
    custom = persona.get("storage_state")
    if custom:
        return Path(custom) if Path(custom).is_absolute() else root / custom
    return root / ".runner" / "state" / f"{site_name}.{persona.get('name', 'default')}.json"


def state_expired(state: Path) -> str:
    """When a saved state has cookies and every one has an expiry in the past,
    the UTC time the last one ran out; else "". A browser-session cookie
    (expires -1) counts as live. A state with no cookies (a localStorage token
    session) is never judged: analytics keys make localStorage useless as a
    session signal next to cookies. An expired state would land on the login
    page and read as drift, so it fails as auth before the browser opens."""
    try:
        cookies = (json.loads(state.read_text(encoding="utf-8")) or {}).get("cookies") or []
        expiries = [float(c.get("expires", -1)) for c in cookies]
    except (OSError, ValueError, TypeError, AttributeError):
        return ""
    if not expiries or min(expiries) <= 0 or max(expiries) > time.time():
        return ""
    return _dt.datetime.fromtimestamp(max(expiries), _dt.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def read_secret(ref: str, what: str) -> str:
    ref = ref or ""
    if ref.startswith("env:"):
        value = os.environ.get(ref[4:])
        if not value:
            raise RunError(f"environment variable '{ref[4:]}' ({what}) is not set", "auth",
                           f"set the environment variable {ref[4:]}, then run {{workflow}} "
                           "again")
        return value
    if ref.startswith("keyring:"):
        service, _, name = ref[8:].partition("/")
        if not service or not name:
            raise RunError(f"persona {what} '{ref}' must read keyring:<service>/<name>",
                           "auth", f"write {what} as keyring:<service>/<name>")
        try:
            import keyring
        except ImportError:
            raise RunError(f"persona {what} is a keyring: reference, but keyring is not "
                           "installed: pip install keyring", "auth",
                           "pip install keyring") from None
        value = keyring.get_password(service, name)
        if not value:
            raise RunError(f"keyring entry '{ref}' ({what}) does not exist", "auth",
                           f"store the keyring entry {ref[8:]}")
        return value
    raise RunError(f"persona {what} must be an env: or keyring: reference, not a value "
                   "— committed files never contain secrets (schema/persona.yaml)", "auth",
                   f"replace {what} with an env: or keyring: reference")


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base or {})
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def settings_layers(root: Path, site: Site, page_name: str | None) -> list[tuple[Path, dict]]:
    """(file, settings) per scope, least specific first: the framework's
    config.yaml, the map repository's config.yaml, site.yaml, the page. A
    later layer wins per key (schema/settings.yaml)."""
    layers = []
    for cfg in dict.fromkeys((FRAMEWORK_ROOT / "config.yaml", root.resolve() / "config.yaml")):
        if cfg.is_file():
            layers.append((cfg, (load_yaml(cfg) or {}).get("settings") or {}))
    layers.append((site.dir / "site.yaml", site.config.get("settings") or {}))
    if page_name and page_name in site.pages:
        layers.append((site.dir / "pages" / f"{page_name}.yaml",
                       site.pages[page_name].get("settings") or {}))
    return layers


def merge_layers(layers: list[tuple[Path, dict]]) -> dict:
    return functools.reduce(deep_merge, (settings for _, settings in layers), {})


def resolve_settings(root: Path, site: Site, page_name: str | None):
    return merge_layers(settings_layers(root, site, page_name))


# ---------------------------------------------------------------------------
# Variables

VAR_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


class Bindings:
    """Resolves $name from parameters, context roles/ids, fixtures and
    captured variables — in that order (most caller-specific wins)."""

    def __init__(self, workflow: dict, cli_params: dict, context: dict | None = None):
        self.context_values = {}
        if context:
            self.context_values = {**(context.get("ids") or {}),
                                   **(context.get("roles") or {})}
        self.params = {}
        for p in workflow.get("parameters") or []:
            name = p["name"]
            if name in cli_params:
                value = cli_params[name]
                options = p.get("options")
                if p.get("type") == "select" and options and value not in options:
                    raise RunError(
                        f"parameter '{name}' must be one of {options}, got '{value}'",
                        "input", f"--param {name}=<one of {options}>")
                self.params[name] = value
            elif p.get("default") not in (None, ""):
                self.params[name] = p["default"]
        self.fixtures = self._flatten_fixtures(workflow.get("fixtures") or {})
        self.captures: dict = {}

    def _flatten_fixtures(self, fixtures: dict) -> dict:
        """Environment-keyed fixtures: common + the block named by a param value."""
        blocks = [v for v in fixtures.values() if isinstance(v, dict)]
        if not blocks:
            return fixtures
        flat = dict(fixtures.get("common") or {})
        for value in self.params.values():
            if isinstance(fixtures.get(value), dict):
                flat = {**flat, **fixtures[value]}
        # scalar top-level fixtures keep working alongside keyed blocks
        flat.update({k: v for k, v in fixtures.items() if not isinstance(v, dict)})
        return flat

    def lookup(self, name: str) -> str:
        for source in (self.params, self.context_values, self.fixtures, self.captures):
            if name in source:
                return str(source[name])
        raise RunError(f"unresolved variable '${name}' (not a parameter, context "
                       "role/id, fixture or capture)", "input",
                       f"a parameter, context or fixture that defines ${name}")

    def resolve(self, text):
        if not isinstance(text, str):
            return text
        return VAR_RE.sub(lambda m: self.lookup(m.group(1)), text)


# ---------------------------------------------------------------------------
# Steps on captured values: a `read` or `assert` with no `page` works on what an
# earlier step captured (typically a script's JSON), not on the browser.

CAPTURE_PATH_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)((?:\.[A-Za-z0-9_-]+|\[\])*)")


def is_capture_step(step: dict) -> bool:
    return step.get("action") in ("read", "assert") and not step.get("page")


def needs_browser(workflow: dict) -> bool:
    """A workflow of script, human and capture steps runs without Chrome, so
    it never opens a session or logs in."""
    return any(s.get("action") not in ("script", "human") and not is_capture_step(s)
               for s in tree.steps_of(workflow))


def capture_path(captures: dict, expr: str):
    """`$name.key.key` into a captured value; `[]` maps the rest over a list:
    `$forecast.vintages[].year_end` is every vintage's year_end."""
    m = CAPTURE_PATH_RE.fullmatch(expr.strip())
    if not m or m.group(1) not in captures:
        raise RunError(f"'{expr}' names no captured value (captures: {sorted(captures)})")
    values, mapped = [captures[m.group(1)]], False
    for part in re.findall(r"\.[A-Za-z0-9_-]+|\[\]", m.group(2)):
        if part == "[]":
            mapped = True
            values = [item for v in values for item in (v or [])]
        else:
            values = [v.get(part[1:]) if isinstance(v, dict) else None for v in values]
    return values if mapped else values[0]


def evaluate_capture(bindings: "Bindings", step: dict, expect):
    """An assert on a captured value: `element` names the capture (or `value` is a
    capture path). `contains`/`equals` compare its text (JSON for structured values),
    `count` its length."""
    expr = step.get("value") or f"${step.get('element', '')}"
    value = capture_path(bindings.captures, expr)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if isinstance(expect, dict) and "contains" in expect:
        needle = bindings.resolve(expect["contains"])
        return text, needle in text
    if isinstance(expect, dict) and "equals" in expect:
        wanted = bindings.resolve(expect["equals"])
        return text, text == wanted
    if isinstance(expect, dict) and "count" in expect:
        n = len(value) if isinstance(value, (list, dict, str)) else 0
        return n, n == expect["count"]
    if expect == "visible":
        return text, value not in (None, "", [], {})
    raise RunError(f"expect {expect!r} does not apply to a captured value")


# ---------------------------------------------------------------------------
# Script output shape (schema/workflow.yaml `shape`): an API that dropped a key
# or changed a type is drift, caught on the step instead of downstream.

JSON_TYPES = {type(None): "null", bool: "bool", int: "number", float: "number",
              str: "string", list: "list", dict: "object"}


def _type_name(value) -> str:
    return JSON_TYPES[type(value)]


def _merge_shapes(a, b):
    """The shape both a and b match: common keys only, and null where they disagree.
    null means unknown, so it yields to the other side."""
    if a == "null":
        return b
    if b == "null":
        return a
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: _merge_shapes(a[k], b[k]) for k in a if k in b}
    if isinstance(a, list) and isinstance(b, list):
        return [_merge_shapes(a[0], b[0])] if a and b else a or b
    return a if a == b else "null"


def infer_shape(value):
    """The shape of a script's parsed output. A list's item shape is the one
    every item matches, so a run always matches the shape it taught."""
    if isinstance(value, dict):
        return {k: infer_shape(v) for k, v in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        item = infer_shape(value[0])
        for other in value[1:]:
            item = _merge_shapes(item, infer_shape(other))
        return [item]
    return _type_name(value)


def shape_mismatch(shape, value) -> str:
    """Why `value` does not match `shape`, as "<path>: <what>", or "" when it
    does. Extra keys and an empty list match. A null value matches any shape and
    a null shape any value: an empty field is not an API change."""
    found = _mismatch(shape, value)
    if not found:
        return ""
    path, what = found
    return "$" + "".join(reversed(path)) + ": " + what


def _mismatch(shape, value):
    """(reversed path parts, what) or None. The path is built only on the way
    out of a mismatch, so a 1 MB output that matches formats no strings."""
    if value is None or shape is None or shape == "null":
        return None
    if type(shape) is str:
        got = JSON_TYPES[type(value)]
        return None if got == shape else ([], f"expected {shape}, got {got}")
    if type(shape) is dict:
        if type(value) is not dict:
            return [], f"expected object, got {JSON_TYPES[type(value)]}"
        for key, sub in shape.items():
            if key not in value:
                return [f".{key}"], "missing"
            got = value[key]
            if sub is None or type(sub) is str and (got is None or sub == "null"
                                                    or JSON_TYPES[type(got)] == sub):
                continue  # the common leaf, without a call
            found = _mismatch(sub, got)
            if found:
                found[0].append(f".{key}")
                return found
        return None
    if type(value) is not list:
        return [], f"expected list, got {JSON_TYPES[type(value)]}"
    if shape:
        item = shape[0]
        for i, entry in enumerate(value):
            found = _mismatch(item, entry)
            if found:
                found[0].append(f"[{i}]")
                return found
    return None


# ---------------------------------------------------------------------------
# Browser execution

# Playwright errors that say the browser or the network went away, not that the
# page changed: a closed window mid-click must not mark a working map broken.
NOT_THE_MAP = ("Target crashed", "Execution context was destroyed",
               "Target page, context or browser has been closed", "net::ERR_")


def element_drifted(exc: BaseException) -> bool:
    """A Playwright Error or TimeoutError about the element itself, without
    importing Playwright. A closed or crashed browser or a network error is not
    drift."""
    return (type(exc).__module__.startswith("playwright.")
            and type(exc).__name__ != "TargetClosedError"
            and not any(cause in str(exc) for cause in NOT_THE_MAP))


def build_locator(pw_page, element: dict, scope_value: str | None = None):
    """Map a page-map locator onto Playwright. One strategy, one call."""
    strategy = (element.get("locator") or {}).get("strategy")
    value = (element.get("locator") or {}).get("value")
    if not strategy or value is None:
        raise RunError(f"element '{element.get('name')}' has no usable locator", "drift")
    if strategy == "text":
        loc = pw_page.get_by_text(value)
    elif strategy == "aria-label":
        loc = pw_page.get_by_label(value)
    elif strategy == "role":
        loc = pw_page.get_by_role(value)
    elif strategy == "data-testid":
        loc = pw_page.get_by_test_id(value)
    elif strategy == "css":
        loc = pw_page.locator(value)
    else:
        raise RunError(f"unknown locator strategy '{strategy}'", "drift")
    if scope_value:
        # value-scoped match inside a container/table: pick the matching item
        loc = loc.get_by_text(scope_value)
    return loc.first


TABLE_JS = """(el, needle) => {
  const rows = Array.from(el.querySelectorAll('tr, [role=row]'));
  const childCellsIncludingHidden = r => Array.from(r.children);
  const isHead = r => r.closest('thead') !== null
    || r.querySelector(':scope > [role=columnheader]') !== null
    || (r.children.length > 0 && childCellsIncludingHidden(r).every(c => c.tagName === 'TH'));
  const head = rows.find(isHead);
  return {
    headers: head ? childCellsIncludingHidden(head).map(c => c.innerText.replace(/\\s+/g, ' ').trim()) : [],
    rows: rows.filter(r => !isHead(r) && r.innerText.includes(needle))
      .map(r => childCellsIncludingHidden(r).map(c => c.innerText.trim())),
  };
}"""


class Runner:
    DEFAULT_TIMEOUT_MS = 10_000

    def __init__(self, root: Path, wf_path: Path, workflow: dict, bindings: Bindings,
                 owner: Owner, headed: bool = False, persona: dict | None = None,
                 pre_authorized: set = frozenset(), learn_shape: bool = False):
        self.root = root
        self.wf_path = wf_path
        self.workflow = workflow
        self.bindings = bindings
        self.owner = owner
        self.apps = load_apps(root)
        self.headed = headed
        self.persona = persona
        self.pre_authorized = pre_authorized
        self.sites: dict[str, Site] = {}
        self.default_site = workflow.get("site")
        self.assertions: list[dict] = []
        self.evidence: list[str] = []
        self.snapshot: dict = {}  # captures of the snapshot phase, the pre-state
        self.current: dict = {}  # {phase, index, step} of the step in flight
        self.fingerprints: dict[str, str] = {}  # page -> ok | mismatch (watch, #24)
        self.scripts: dict[str, str] = {}  # script step -> ok | mismatch against its shape
        self.learn_shape = learn_shape
        self.learned: list[tuple[str, int, object]] = []  # (phase, index, shape)
        self._last_page: str | None = None
        self._pw = None
        self.browser = None
        self.pw_page = None
        self.login_failed = False

    # -- sites ------------------------------------------------------------
    def site(self, step: dict) -> Site:
        name = self.bindings.resolve(step.get("site") or self.default_site)
        if not name:
            raise RunError("step names no site and the workflow has no default `site:`")
        if name not in self.sites:
            self.sites[name] = Site(self.root, name)
        return self.sites[name]

    # -- browser lifecycle -------------------------------------------------
    def start(self, primary_site: str):
        context_args = {}
        credentials = None
        if self.persona:
            state = state_path(self.root, primary_site, self.persona)
            fresh = bool(self.persona.get("fresh_login"))
            if self.persona.get("auth") == "session":
                if fresh:
                    raise RunError(f"persona '{self.persona.get('name')}' is auth: session "
                                   "and fresh_login: true — a session persona only reuses "
                                   "saved state (schema/persona.yaml)", "auth",
                                   "drop fresh_login from the session persona")
                refresh = (f"refresh the session of persona '{self.persona.get('name')}': "
                           "run {workflow} once --headed with a persona whose auth is human")
                if not state.is_file():
                    raise RunError(
                        f"persona '{self.persona.get('name')}' is auth: session but "
                        f"{state} does not exist — run once with a persona whose auth "
                        "is `human` (headed) to create it. The runner never logs in "
                        "silently.", "auth", refresh
                    )
                expired = state_expired(state)
                if expired:
                    raise RunError(
                        f"persona '{self.persona.get('name')}' is auth: session but every "
                        f"cookie in {state} expired, the last at {expired}. The runner "
                        "never logs in silently.", "auth", refresh)
                context_args["storage_state"] = str(state)
            elif state.is_file() and not fresh:
                context_args["storage_state"] = str(state)
            elif self.persona.get("auth") == "automated":
                credentials = self._login_credentials(primary_site)
        try:  # after the persona checks, so an auth failure needs no browser to report
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RunError(
                "Playwright is not installed. The runner needs it (the rest of "
                "SiteMapper does not): pip install playwright  — no browser "
                "download required, the installed Chrome is used."
            )
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(channel="chrome", headless=not self.headed)
        self.context = self.browser.new_context(**context_args)
        self.pw_page = self.context.new_page()
        self.pw_page.set_default_timeout(self.DEFAULT_TIMEOUT_MS)
        if self.persona and "storage_state" not in context_args:
            self.log_in(primary_site, credentials)

    def log_in(self, primary_site: str, credentials: tuple[str, str] | None):
        """Establish the persona's session. A failure keeps the class its raise
        site named: drift in the login page's map stays drift, a rejected login
        is auth, anything else (a network error) is error."""
        failed, cls, hint = None, "error", ""
        try:
            self._establish_session(primary_site, credentials)
        except RunError as exc:
            failed, cls, hint = str(exc), exc.cls, exc.hint
        except Exception as exc:
            failed = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
        if failed:
            # Raised outside the except block: the Playwright exception's
            # call log holds fill("<password>") and must not ride along as
            # __context__. A login screen shows the username, so no screenshot.
            self.login_failed = True
            raise RunError(f"{failed} (no screenshot taken: the failure was in the login)",
                           cls, hint)

    def _login_credentials(self, site_name: str) -> tuple[str, str]:
        site = Site(self.root, site_name)
        settings = resolve_settings(self.root, site, None)
        verdict = permission_verdict(settings, "auth")
        if verdict == "deny" or (verdict == "ask" and "auth" not in self.pre_authorized):
            env = (settings.get("policy") or {}).get("environment", "?")
            raise RunError(
                f"automated login is '{verdict}' for site '{site_name}' "
                f"(environment: {env})" +
                (" — pass --yes-auth to pre-authorize" if verdict == "ask" else
                 ". Use a `human`-seeded session instead (docs/permissions.md)."),
                "refused", "pass --yes-auth to consent to this one run" if verdict == "ask"
                else ""
            )
        if not (self.persona.get("login") or {}).get("page"):
            raise RunError("auth: automated needs a `login:` block (schema/persona.yaml)",
                           "auth", "give the persona a `login:` block")
        creds = self.persona.get("credential_ref") or {}
        return (read_secret(creds.get("username"), "credential_ref.username"),
                read_secret(creds.get("password"), "credential_ref.password"))

    def _establish_session(self, site_name: str, credentials: tuple[str, str] | None):
        persona = self.persona
        method = persona.get("auth")
        site = Site(self.root, site_name)
        state = state_path(self.root, site_name, persona)
        if method == "human":
            if not self.headed:
                raise RunError(
                    f"persona '{persona.get('name')}' needs a first login by a human — "
                    "re-run with --headed, log in when the browser opens", "auth",
                    "run {workflow} again with --headed and log in when the browser opens"
                )
            login_page = (persona.get("login") or {}).get("page")
            self.pw_page.goto(site.base_url + (site.page(login_page).get("url_pattern", "")
                                               if login_page else ""))
            try:
                input("Log in in the browser window, then press Enter here... ")
            except (EOFError, KeyboardInterrupt):
                raise RunError("no interactive console to wait on — auth: human needs one",
                               "auth", "run {workflow} again --headed from a terminal and "
                               "log in when the browser opens")
        elif method == "automated":
            login = persona["login"]
            user, pw = credentials
            self.pw_page.goto(site.base_url + site.page(login["page"]).get("url_pattern", ""))
            moves = [("open_element", None)] if login.get("open_element") else []
            moves += [("username_element", user), ("password_element", pw),
                      ("submit_element", None)]
            for key, value in moves:
                locator = build_locator(self.pw_page, site.element(login["page"], login[key]))
                try:
                    if value is None:
                        locator.click()
                    else:
                        locator.fill(value)
                except Exception as exc:
                    raise RunError(f"login.{key} '{login[key]}' on page '{login['page']}': "
                                   f"{type(exc).__name__}: {str(exc).splitlines()[0]}",
                                   "drift") from None
            self.pw_page.wait_for_load_state()
            password = build_locator(self.pw_page,
                                     site.element(login["page"], login["password_element"]))
            try:
                password.wait_for(state="hidden")
            except Exception:
                raise RunError(f"login rejected on site '{site_name}': the password element "
                               f"'{login['password_element']}' still shows after submit. "
                               "Not retried.", "auth", f"check the credentials of persona "
                               f"'{persona.get('name')}'; the runner did not retry") from None
        else:
            raise RunError(f"persona auth method '{method}' is not session|human|automated",
                           "auth", "set the persona's auth to session, human or automated")
        if persona.get("fresh_login"):
            return
        state.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(state))
        print(f"session saved: {state}", file=sys.stderr)

    def stop(self):
        for closer in (self.browser, self._pw):
            try:
                if closer:
                    closer.close() if closer is self.browser else closer.stop()
            except Exception:
                pass

    # -- steps -------------------------------------------------------------
    def run_step(self, step: dict, phase: str = "steps", index: int = 0, number: int = 0):
        self.current = {"phase": phase, "index": index, "number": number, "step": step}
        action = step.get("action")
        if action not in MECHANICAL_ACTIONS:
            raise RunError(f"action '{action}' is not mechanical — this workflow needs an LLM")
        # Watch (#24): arriving at a page by click-chain — verify its
        # fingerprint in passing before acting on it. Deep-link arrivals are
        # verified in do_navigate after goto().
        page_name = step.get("page")
        if (page_name and page_name != self._last_page and action != "navigate"
                and self.pw_page):
            self.check_fingerprint(self.site(step), page_name)
        try:
            getattr(self, f"do_{action}")(step)
        except Exception as exc:
            # The browser failing on a mapped element (gone, timed out, no
            # longer an input) is the map's problem; any other exception stays
            # the runner's (class error).
            if step.get("element") and element_drifted(exc):
                raise RunError(f"{type(exc).__name__}: {str(exc).splitlines()[0]}",
                               "drift") from None
            raise
        if page_name:
            self._last_page = page_name
        # The snapshot phase's captures are the pre-state: kept apart so the
        # record can write them before anything else is looked at.
        if phase == "snapshot" and step.get("capture"):
            self.snapshot[step["capture"]] = self.bindings.captures.get(step["capture"])

    # -- watch (#24) --------------------------------------------------------
    def check_fingerprint(self, site: Site, page_name: str):
        """Cheap arrival check: URL regex + one anchor element. A mismatch is a
        drift signal, not an abort — it is recorded, degrades trust, and the
        step that needed the page will fail on its own if the page is gone."""
        fp = site.page(page_name).get("fingerprint") or {}
        if not fp:
            return
        ok = True
        url_re = fp.get("url")
        if url_re and not re.search(url_re, self.pw_page.url):
            ok = False
        anchor = fp.get("anchor")
        if ok and anchor:
            element = site.element(page_name, anchor)
            try:
                build_locator(self.pw_page, element).wait_for(state="visible", timeout=3000)
            except Exception:
                ok = False
        # a later mismatch on the same page must not be shadowed by an early ok
        current = self.fingerprints.get(page_name)
        self.fingerprints[page_name] = "mismatch" if (not ok or current == "mismatch") \
            else "ok"

    # -- failure report (#21) ----------------------------------------------
    def build_failure(self) -> dict:
        """Everything the repair loop needs: which step, which locator, what
        the page actually was. Built best-effort — never raises."""
        step = self.current.get("step") or {}
        failure = {
            "phase": self.current.get("phase", ""),
            "step_index": self.current.get("index", 0),
            "action": step.get("action", ""),
            "description": step.get("description", ""),
            "page": step.get("page", ""),
            "element": step.get("element", ""),
            "locator": {},
            "resolved_values": {},
            "url": "", "page_title": "",
            "fingerprint": self.fingerprints.get(step.get("page", ""), "unchecked"),
            "screenshot": "",
        }
        try:
            site = self.site(step)
            if step.get("page") and step.get("element"):
                el = site.element(step["page"], step["element"])
                failure["locator"] = dict(el.get("locator") or {})
        except Exception:
            pass
        for key in ("value", "site"):
            raw = step.get(key)
            if isinstance(raw, str) and "$" in raw:
                try:
                    failure["resolved_values"][raw] = self.bindings.resolve(raw)
                except Exception as exc:
                    failure["resolved_values"][raw] = f"<unresolved: {exc}>"
        if self.pw_page:
            try:
                failure["url"] = self.pw_page.url
                failure["page_title"] = self.pw_page.title()
            except Exception:
                pass
            if self.login_failed:
                return failure
            try:
                shots = self.root / ".runner"
                shots.mkdir(exist_ok=True)
                stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                shot = shots / f"{self.workflow.get('name', 'run')}-{stamp}.png"
                self.pw_page.screenshot(path=str(shot), full_page=False)
                failure["screenshot"] = str(shot)
            except Exception:
                pass
        return failure

    # -- drift check: replay the fixtures ------------------------------------
    def confirm_drift(self, result: dict, primary: str):
        """Tell drift from missing data before a read-only run breaks trust.

        A drift or assert run is replayed once, through the same gate, with
        each parameter that has a fixture of its name set to the fixture. A
        replay that passes means the map is fine and these arguments found no
        data, so the class becomes input. Any other replay outcome leaves the
        class alone. The replay goes into failure.replay of the same result.
        A run whose steps passed drifted only in a fingerprint: that is the
        page, never the data, so it is not replayed."""
        cls = result["class"]
        if cls not in ("drift", "assert") or result["status"] == "passed":
            return
        name = result["workflow"]
        effect = self.workflow.get("effect")
        human = next((n for n, s in enumerate(tree.steps_of(self.workflow), 1)
                      if s.get("action") == "human"), None)
        known = {p["name"]: str(self.bindings.fixtures[p["name"]])
                 for p in self.workflow.get("parameters") or []
                 if p.get("name") in self.bindings.fixtures}
        differs = {k: v for k, v in known.items() if self.bindings.lookup(k) != v}
        if effect != "read-only":
            replay = {"status": "skipped",
                      "reason": f"effect is {effect}: a replay would repeat what the run did"}
        elif human:
            replay = {"status": "skipped",
                      "reason": f"step {human} is a human step: a replay would stop there"}
        elif not self.workflow.get("parameters"):
            replay = {"status": "skipped",
                      "reason": "the workflow has no parameters, so a replay would repeat "
                                "the run"}
        elif not known:
            replay = {"status": "skipped",
                      "reason": "no parameter has a fixture of its name"
                      if self.workflow.get("fixtures") else "the workflow has no fixtures"}
            result["next"] += (f". To tell drift from missing data next time, give {name} a "
                               "fixture named like each parameter (schema/workflow.yaml)")
        elif not differs:
            replay = {"status": "skipped",
                      "reason": "the run already used the fixtures, so a replay would "
                                "repeat it"}
        elif not differs.keys() & self._names_until_failure(result):
            replay = {"status": "skipped", "reason": "the failing step used no parameter"}
        else:
            replay = self._replay(result, primary, differs)
        if replay["status"] == "passed":
            used = ", ".join(f"{k}={self.bindings.lookup(k)}" for k in differs)
            fixed = ", ".join(f"{k}={v}" for k, v in differs.items())
            result["class"] = "input"
            result["next"] = next_step("input", name, f"arguments the site has data for: the "
                                       f"fixture replay ({fixed}) passed, so there is no "
                                       f"data for these arguments ({used})")
        failure = result.setdefault("failure", {})
        failure.update({"class": result["class"], "next": result["next"], "replay": replay})
        print(f"replay: {replay['status']}"
              + (f" ({replay['reason']})" if replay.get("reason") else ""), file=sys.stderr)

    def _names_until_failure(self, result: dict) -> set[str]:
        """Every $name the steps up to the failing one refer to: the step that
        raised, or the assert step of the first failed assertion (assertions
        are appended one per assert step, in run order)."""
        ordered = [(phase, index, step) for phase in tree.PHASES + ("teardown",)
                   for index, step in enumerate(self.workflow.get(phase) or [])]
        if result["status"] == "error":
            at = (result["failure"].get("phase"), result["failure"].get("step_index"))
            end = next((n for n, (ph, i, _) in enumerate(ordered) if (ph, i) == at), -1)
        else:
            first = next(k for k, a in enumerate(result["assertions"]) if not a["pass"])
            end = [n for n, (_, _, s) in enumerate(ordered) if s.get("action") == "assert"][first]
        resolved = [self.workflow.get("site")]
        for _, _, step in ordered[:end + 1]:
            expect = step.get("expect") if isinstance(step.get("expect"), dict) else {}
            resolved += [step.get(k) for k in ("site", "value", "row", "column")]
            resolved += [expect.get(k) for k in ("contains", "equals", "url_matches", "value")]
        return {name for text in resolved if isinstance(text, str)
                for name in VAR_RE.findall(text)}

    def _replay(self, result: dict, primary: str, differs: dict) -> dict:
        inputs = {**{k: str(v) for k, v in self.bindings.params.items()}, **differs}
        persona = (self.persona or {}).get("name")
        try:
            gate(preflight(self.root, self.workflow, self.owner, inputs, persona,
                           frozenset(self.pre_authorized)))
            bindings = Bindings(self.workflow, inputs)
        except RunError as exc:
            return {"status": "refused", "reason": str(exc), "inputs": differs}
        bindings.context_values = self.bindings.context_values
        again = {"workflow": result["workflow"], "status": "passed", "error": "",
                 "started_at": utc_now()}
        attempt(Runner(self.root, self.wf_path, self.workflow, bindings, self.owner,
                       self.headed, self.persona, self.pre_authorized),
                self.workflow, bindings, primary, again)
        result["evidence"] += again["evidence"]
        result["finished_at"] = again["finished_at"]
        return {"status": "passed" if again["class"] == "ok" else "failed",
                "inputs": differs, "class": again["class"], "error": error_of(again),
                "counts": again["counts"], "started_at": again["started_at"],
                "finished_at": again["finished_at"]}

    def _element(self, step, site: Site):
        return site.element(step["page"], step["element"])

    def do_navigate(self, step):
        site = self.site(step)
        value = self.bindings.resolve(step.get("value"))
        if value:
            url = value if value.startswith("http") else site.base_url + value
        elif step.get("page"):
            if step.get("element"):
                raise RunError(
                    f"navigate step targets element '{step['element']}' — navigate takes a "
                    "URL or a page; opening a menu is a `click` (schema/workflow.yaml)"
                )
            pattern = site.page(step["page"]).get("url_pattern") or ""
            if re.search(r"[{<]", pattern):
                raise RunError(
                    f"page '{step['page']}' url_pattern '{pattern}' has unresolved "
                    "placeholders — navigate with an explicit `value:` instead", "input",
                    "a navigate step whose `value:` fills the placeholders"
                )
            url = site.base_url + pattern
        else:
            raise RunError("navigate step has neither `value` nor `page`")
        self.pw_page.goto(url)
        if step.get("page"):
            self.check_fingerprint(site, step["page"])
            self._last_page = step["page"]

    def do_click(self, step):
        site = self.site(step)
        element = self._element(step, site)
        scope = self.bindings.resolve(step.get("value")) if step.get("value") else None
        build_locator(self.pw_page, element, scope).click()

    def do_input(self, step):
        site = self.site(step)
        element = self._element(step, site)
        value = self.bindings.resolve(step.get("value", ""))
        locator = build_locator(self.pw_page, element)
        if element.get("type") == "select":
            try:
                locator.select_option(label=value)
            except Exception:
                # custom dropdown: open it, pick the option by text
                locator.click()
                self.pw_page.get_by_text(value, exact=True).first.click()
        else:
            locator.fill(value)
            self._ensure_value(locator, value)

    def _ensure_value(self, locator, value):
        """fill() is not enough for a framework-controlled field.

        A React/Angular combobox re-asserts its own state after fill(), so the
        page goes on filtering on the old value while the run reads a green
        assertion off an unfiltered list. Observed on GitHub's rebuilt issues
        index, 2026-10-09. Real keystrokes do land, so retype when the value
        did not stick.
        """
        try:
            self.pw_page.wait_for_timeout(300)
            if locator.input_value() == value:
                return
            locator.click()
            self.pw_page.keyboard.press("Control+a")
            locator.press_sequentially(value, delay=50)
            self.pw_page.wait_for_timeout(300)
            if locator.input_value() != value:
                raise RunError(
                    f"field did not accept '{value}' "
                    f"(reads '{locator.input_value()}') - fill and typing were both reverted",
                    "drift")
        except RunError:
            raise
        except Exception:
            pass  # not a value-bearing element; fill() was the whole job

    def do_read(self, step):
        if is_capture_step(step):
            if "row" in step or "column" in step:
                raise RunError("`row` and `column` read a table on a page; this read has "
                               "no `page`, so it reads a capture and cannot take them")
            value = capture_path(self.bindings.captures, step.get("value") or "")
            if step.get("capture"):
                self.bindings.captures[step["capture"]] = value
            return
        site = self.site(step)
        element = self._element(step, site)
        locator = build_locator(self.pw_page, element)
        if "row" in step or "column" in step:
            text = self._read_cell(locator, self.bindings.resolve(step.get("row")),
                                   self.bindings.resolve(step.get("column")))
        else:
            text = locator.inner_text()
        if step.get("capture"):
            self.bindings.captures[step["capture"]] = text.strip()

    def _read_cell(self, table, row: str, column: str) -> str:
        if not row or not column:
            raise RunError("a table read needs both `row` and `column`")
        grid, _ = self._poll(lambda: table.evaluate(TABLE_JS, row),
                             lambda g: len(g["rows"]) == 1)
        headers = grid["headers"]
        index = [i for i, h in enumerate(headers) if h == column] \
            or [i for i, h in enumerate(headers) if h.startswith(column)]
        if len(index) != 1:
            raise RunError(f"header '{column}' matches {len(index)} of the columns "
                           f"{headers}, expected 1", "drift")
        if len(grid["rows"]) != 1:
            raise RunError(f"{len(grid['rows'])} rows contain '{row}', expected 1", "drift")
        cells = grid["rows"][0]
        if index[0] >= len(cells):
            raise RunError(f"the row containing '{row}' has {len(cells)} cells, "
                           f"no cell under header '{column}'", "drift")
        return cells[index[0]]

    def do_wait(self, step):
        value = self.bindings.resolve(step.get("value"))
        if step.get("element"):
            site = self.site(step)
            element = self._element(step, site)
            build_locator(self.pw_page, element).wait_for(state="visible")
        elif value:
            self.pw_page.wait_for_timeout(float(value) * 1000)
        else:
            self.pw_page.wait_for_load_state("networkidle")

    def do_key(self, step):
        self.pw_page.keyboard.press(self.bindings.resolve(step.get("value", "")))

    def script_path(self, step, site: Site) -> Path:
        """Resolve a script name to its one home: the step's site, this
        workflow's project, or the app the site is a tier of — in that order
        (schema/workflow.yaml). A name declared nowhere is an error here, so a
        workflow never lists a foreign site to reach a script."""
        name = step.get("script")
        if name in {s.get("name") for s in site.config.get("scripts") or []}:
            return site.dir / "scripts" / name
        if self.owner.kind == "project" and name in {
                s.get("name") for s in self.owner.project.get("scripts") or []}:
            return self.owner.dir / "scripts" / name
        app_name, app = app_of_site(self.apps, site.name)
        if app and name in {s.get("name") for s in app.get("scripts") or []}:
            return app["_dir"] / "scripts" / name
        raise RunError(
            f"script '{name}' is declared neither by site '{site.name}', "
            f"nor by {('project ' + self.owner.name) if self.owner.kind == 'project' else 'a project'}, "
            f"nor by {('app ' + app_name) if app_name else 'an app the site is a tier of'}"
        )

    def do_script(self, step):
        site = self.site(step)
        path = self.script_path(step, site)
        args = self.bindings.resolve(step.get("value") or "")
        cmd = [sys.executable, str(path)] + args.split()
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root)
        if proc.returncode != 0:
            raise RunError(f"script '{step.get('script')}' failed:\n{proc.stderr.strip()}",
                           "error", f"fix script '{step.get('script')}' (its stderr is in "
                           "`error`), then run {workflow} again")
        out = proc.stdout.strip()
        try:
            parsed, is_json = json.loads(out), True
        except json.JSONDecodeError:
            parsed, is_json = out, False
        if step.get("capture"):
            self.bindings.captures[step["capture"]] = parsed
        if self.learn_shape:
            if is_json:
                self.learned.append((self.current["phase"], self.current["index"],
                                     infer_shape(parsed)))
        elif step.get("shape") is not None:
            self.check_shape(step, parsed if is_json else None, is_json)

    def check_shape(self, step: dict, output, is_json: bool):
        """A script whose output lost its stored shape is drift: the API changed
        under the workflow. It stops the run, so no later step reads data of the
        wrong shape."""
        problem = tree.shape_problem(step["shape"])
        if problem:
            raise RunError(f"script '{step['script']}' has a malformed {problem}", "error",
                           "fix the shape (python scripts/check.py names it), then run "
                           "{workflow} again")
        key = step.get("capture") or step["script"]
        why = shape_mismatch(step["shape"], output) if is_json else "not JSON"
        self.scripts[key] = "mismatch" if why or self.scripts.get(key) == "mismatch" else "ok"
        if why:
            raise RunError(f"script '{step['script']}' output does not match its shape: "
                           f"{why}", "drift")

    def do_human(self, step):
        number = self.current["number"]
        raise WaitForPerson(number, step.get("description") or f"step {number}",
                            step.get("reason", ""))

    def do_assert(self, step):
        site = self.site(step)
        expect = step.get("expect")
        page_name, el_name = step.get("page", ""), step.get("element", "")
        entry = {
            "id": f"{page_name}.{el_name}.{expect if isinstance(expect, str) else list(expect)[0]}",
            "page": page_name, "element": el_name,
            "expect": expect, "actual": None, "pass": False, "message": "",
        }
        try:
            entry["actual"], entry["pass"] = self._evaluate(site, step, expect)
        except Exception as exc:  # an un-evaluable assert is a failed one, not an error
            entry["message"] = str(exc).splitlines()[0]
        self.assertions.append(entry)

    def _evaluate(self, site: Site, step: dict, expect):
        if is_capture_step(step):
            return evaluate_capture(self.bindings, step, expect)
        if isinstance(expect, dict) and "url_matches" in expect:
            pattern = self.bindings.resolve(expect["url_matches"])
            return self._poll(lambda: self.pw_page.url,
                              lambda url: re.search(pattern, url) is not None)
        element = self._element(step, site)
        locator = build_locator(self.pw_page, element)
        if expect == "absent":
            try:
                locator.wait_for(state="hidden", timeout=3000)
                return "absent", True
            except Exception:
                return "present", False
        if expect == "visible":
            try:
                locator.wait_for(state="visible", timeout=self.DEFAULT_TIMEOUT_MS)
                return "visible", True
            except Exception:
                return "not visible", False
        if expect in ("enabled", "disabled"):
            enabled = locator.is_enabled()
            return ("enabled" if enabled else "disabled"), (enabled == (expect == "enabled"))
        if isinstance(expect, dict):
            if "count" in expect:
                return self._poll(lambda: self._count_all(element),  # all matches, not .first
                                  lambda n: n == expect["count"])
            if "contains" in expect:
                needle = self.bindings.resolve(expect["contains"])
                return self._poll(lambda: locator.inner_text().strip(),
                                  lambda text: needle in text)
            if "equals" in expect:
                wanted = self.bindings.resolve(expect["equals"])
                return self._poll(lambda: locator.inner_text().strip(),
                                  lambda text: text == wanted)
            if "value" in expect:
                wanted = self.bindings.resolve(expect["value"])
                return self._poll(locator.input_value, lambda val: val == wanted)
        raise RunError(f"unknown expect condition: {expect!r}")

    def _poll(self, read, ok):
        """Re-read until the condition holds or the timeout runs out.

        `visible` and `absent` have always waited; the content and URL checks
        read once, which on a single-page app asserts against whatever the
        frame happened to hold that millisecond. A route push or a list render
        landing a beat later then reads as a failure, and the inverse - a stale
        pass off the PREVIOUS state - is the expensive one. Reports the last
        reading either way, so a real mismatch still says what it saw.
        """
        deadline = time.monotonic() + self.DEFAULT_TIMEOUT_MS / 1000
        while True:
            actual = read()
            passed = ok(actual)
            if passed or time.monotonic() >= deadline:
                return actual, passed
            self.pw_page.wait_for_timeout(250)

    def _count_all(self, element: dict) -> int:
        strategy = (element.get("locator") or {}).get("strategy")
        value = (element.get("locator") or {}).get("value")
        page = self.pw_page
        if strategy == "text":
            return page.get_by_text(value).count()
        if strategy == "aria-label":
            return page.get_by_label(value).count()
        if strategy == "role":
            return page.get_by_role(value).count()
        if strategy == "data-testid":
            return page.get_by_test_id(value).count()
        return page.locator(value).count()


# ---------------------------------------------------------------------------
# Scope: which tier, which sites

def require_params(workflow: dict, cli_params: dict):
    for p in workflow.get("parameters") or []:
        if p.get("required") and p["name"] not in cli_params and p.get("default") in (None, ""):
            name = p["name"]
            raise RunError(f"required parameter '{name}' missing — pass --param {name}=...",
                           "input", f"--param {name}=...")


def resolve_scope(root: Path, workflow: dict, owner: Owner, cli_params: dict):
    """The tier this run targets and every site its steps touch.

    A workflow with `tiers` picks its tier with the `environment` parameter;
    the app maps the tier to a site, and that site leads. Every other site a
    step names, literally or through a fixture, is in scope too, because the
    permission gate is per step: the policy of each site a step runs on
    applies, never the policy of a site listed only to be read.
    Returns (tier, primary_site, sites)."""
    bindings = Bindings(workflow, cli_params)
    tier, primary = "-", None
    tiers = workflow.get("tiers") or {}
    if tiers:
        app_name = owner.project.get("app")
        apps = load_apps(root)
        if owner.kind != "project" or app_name not in apps:
            raise RunError("workflow declares tiers but its project names no existing app")
        tier = bindings.params.get("environment")
        allowed = tiers.get("allowed") or tiers.get("required") or []
        if tier not in allowed:
            raise RunError(f"parameter 'environment' must be one of {allowed}, got '{tier}'",
                           "input", f"--param environment=<one of {allowed}>")
        primary = (apps[app_name].get("tiers") or {}).get(tier)
        if not primary:
            raise RunError(f"app '{app_name}' maps no site for tier '{tier}'")
    sites = []
    for step in tree.steps_of(workflow):
        ref = step.get("site") or workflow.get("site")
        if not ref:
            continue
        try:
            name = bindings.resolve(str(ref))
        except RunError:
            continue  # a context role: bound after the context loads, gated by its site then
        if name and name not in sites:
            sites.append(name)
    for s in [workflow.get("site")] + list(workflow.get("sites") or []):
        if isinstance(s, str) and not s.startswith("$") and s not in sites:
            sites.append(s)
    if primary is None:
        if not sites:
            raise RunError("workflow names no literal site — cannot resolve a permission scope")
        primary = sites[0]
    elif primary not in sites:
        sites.insert(0, primary)
    return tier, primary, sites


# ---------------------------------------------------------------------------
# Permissions (#22) — action classes x allow/ask/deny, gated UP FRONT.

EFFECT_CLASS = {"read-only": "read", "mutating": "write", "destructive": "destructive"}
PERMISSION_DEFAULTS = {"read": "allow", "write": "ask", "auth": "ask", "destructive": "deny"}
STRICTNESS = {"allow": 0, "ask": 1, "deny": 2}


def deciding_rule(policy: dict, action_class: str) -> tuple[str, tuple[str, ...]] | None:
    """(verdict, key path) of the policy rule that decides the class; None
    leaves it to PERMISSION_DEFAULTS."""
    verdict = (policy.get("permissions") or {}).get(action_class)
    if verdict:
        return verdict, ("permissions", action_class)
    if action_class == "write" and policy.get("safe_to_submit_forms"):
        return "allow", ("safe_to_submit_forms",)  # legacy alias
    return None


def permission_verdict(settings: dict, action_class: str) -> str:
    rule = deciding_rule(settings.get("policy") or {}, action_class)
    return rule[0] if rule else PERMISSION_DEFAULTS[action_class]


def _sets(policy: dict, key_path: tuple[str, ...]) -> bool:
    for key in key_path[:-1]:
        policy = policy.get(key) or {}
    return key_path[-1] in policy


def permission_sources(root: Path, site: Site) -> dict[str, tuple[str, Path | None]]:
    """Per action class, the verdict and the file whose rule decided it, None
    for the default."""
    layers = settings_layers(root, site, None)
    policy = (merge_layers(layers).get("policy") or {})
    out = {}
    for action_class, default in PERMISSION_DEFAULTS.items():
        rule = deciding_rule(policy, action_class)
        if not rule:
            out[action_class] = (default, None)
            continue
        verdict, key_path = rule
        out[action_class] = (verdict, next(path for path, settings in reversed(layers)
                                           if _sets(settings.get("policy") or {}, key_path)))
    return out


Verdict = Literal["allow", "ask", "deny"]


@dataclasses.dataclass(frozen=True)
class Decision:
    verdict: Verdict
    site: str
    environment: str
    source: str | None

    def where(self) -> str:
        return f"site '{self.site}' (environment: {self.environment})"


@dataclasses.dataclass(frozen=True)
class Preflight:
    workflow: str
    effect: str
    tier: str
    sites: list[str]
    persona: str | None
    lock_key: str
    classes: dict[str, Decision]
    consent: list[str]
    needs_consent: list[str]
    outcome: Verdict


def site_decisions(root: Path, site_name: str) -> dict[str, Decision]:
    site = Site(root, site_name)
    env = (resolve_settings(root, site, None).get("policy") or {}).get("environment", "?")
    return {cls: Decision(verdict, site_name, env, path.as_posix() if path else None)
            for cls, (verdict, path) in permission_sources(root, site).items()}


def logs_in(root: Path, workflow: dict, primary: str, persona: dict) -> bool:
    if persona.get("auth") != "automated" or not needs_browser(workflow):
        return False
    return bool(persona.get("fresh_login")) or not state_path(root, primary, persona).is_file()


def preflight(root: Path, workflow: dict, owner: Owner, cli_params: dict,
              persona_name: str | None = None,
              consent: frozenset[str] = frozenset()) -> Preflight:
    """What a run would be allowed to do, decided before anything starts.

    Opens no browser and writes nothing. Each action class the run needs gets
    the strictest decision over the sites it applies to; an `ask` that
    `consent` answers counts as allowed in the outcome."""
    name = workflow.get("name")
    mode = workflow.get("mode")
    if mode != "deterministic":
        raise RunError(
            f"'{name}' is mode: {mode or 'unset'} — only deterministic workflows can run "
            "headless. An agentic workflow needs an LLM host (the /run skill).",
            "refused", "run {workflow} through the /run skill on an LLM host"
        )
    for phase in tree.PHASES + ("teardown",):
        for step in workflow.get(phase) or []:
            if step.get("action") == "verify":
                raise RunError(
                    f"step in `{phase}` uses action: verify (judgement) — the workflow "
                    "cannot be deterministic; fix its mode or the step",
                    "refused", "run {workflow} through the /run skill on an LLM host"
                )
    if workflow.get("rollback") == "snapshot" and not any(
            s.get("capture") for s in (workflow.get("snapshot") or []) if isinstance(s, dict)):
        raise RunError("rollback: snapshot declared, but the snapshot phase captures nothing "
                       "— there would be no pre-state to keep (schema/workflow.yaml)")

    tier, primary, sites = resolve_scope(root, workflow, owner, cli_params)
    effect = workflow.get("effect")
    if effect not in EFFECT_CLASS:
        raise RunError(
            f"effect: {effect or 'undeclared'} — a headless run needs the workflow to "
            "declare read-only | mutating | destructive (schema/workflow.yaml)",
            "refused", "declare the effect of {workflow} (schema/workflow.yaml)"
        )
    by_site = {s: site_decisions(root, s) for s in sites}
    action_class = EFFECT_CLASS[effect]
    classes = {action_class: max((by_site[s][action_class] for s in sites),
                                 key=lambda d: STRICTNESS[d.verdict])}
    persona = load_persona(root, primary, persona_name) or {}
    if logs_in(root, workflow, primary, persona):
        classes["auth"] = by_site[primary]["auth"]
    outcome = max(("allow" if d.verdict == "ask" and c in consent else d.verdict
                   for c, d in classes.items()), key=STRICTNESS.get)
    return Preflight(workflow=name, effect=effect, tier=tier, sites=sites,
                     persona=persona.get("name"),
                     lock_key=f"{'+'.join(sorted(sites))}/{persona.get('name') or '-'}",
                     classes=classes, consent=sorted(consent),
                     needs_consent=[c for c, d in classes.items()
                                    if d.verdict == "ask" and c not in consent],
                     outcome=outcome)


def gate(pre: Preflight):
    """Refuse or ask BEFORE the browser opens. `trust` grants nothing here.

    `ask` resolves via --yes-<class>, then a TTY prompt, and degrades to deny
    when non-interactive (CI has no human to ask). Returns the class a person
    consented to at the prompt, so a replay in the same run does not ask again.
    """
    action_class = EFFECT_CLASS[pre.effect]
    decision = pre.classes[action_class]
    consent = f"pass --yes-{action_class} to consent to this one run"
    if decision.verdict == "deny":
        raise RunError(
            f"permission denied: effect '{pre.effect}' needs class '{action_class}' which is "
            f"'deny' for {decision.where()}. This is policy, not a bug — see docs/permissions.md.",
            "refused"
        )
    if decision.verdict == "ask":
        if action_class in pre.consent:
            return
        if sys.stdin.isatty():
            try:
                answer = input(
                    f"'{pre.workflow}' is {pre.effect} and {decision.where()} says ask. "
                    "Proceed? [y/N] "
                )
            except (EOFError, KeyboardInterrupt):
                answer = ""  # a TTY that cannot actually answer is non-interactive
            if answer.strip().lower() == "y":
                return frozenset({action_class})
            raise RunError(
                f"not authorized: class '{action_class}' is 'ask' for {decision.where()} and "
                f"no consent was given. Pass --yes-{action_class} to pre-authorize.",
                "refused", consent
            )
        raise RunError(
            f"class '{action_class}' is 'ask' for {decision.where()}, and this run is "
            f"non-interactive — `ask` degrades to deny. Pass --yes-{action_class} to "
            "pre-authorize.", "refused", consent
        )


# ---------------------------------------------------------------------------
# Trust bookkeeping (#24) — the YAML is updated, not just the log. Text-level
# edits so the schema-template comments and formatting survive (no yaml.dump).

def _set_workflow_key(wf_path: Path, key: str, value: str):
    text = wf_path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^(\s*){key}:\s*\S*.*$", re.M)
    if pattern.search(text):
        text = pattern.sub(rf"\g<1>{key}: {value}", text, count=1)
    else:  # insert directly under mode: (or name: as fallback)
        for anchor in ("mode", "name"):
            m = re.search(rf"^(\s*){anchor}:.*$", text, re.M)
            if m:
                indent = m.group(1)
                text = text[:m.end()] + f"\n{indent}{key}: {value}" + text[m.end():]
                break
    wf_path.write_text(text, encoding="utf-8")


def update_trust(wf_path: Path, workflow: dict, result: dict):
    """broken when the run's class may downgrade trust (drift, assert); verified_at
    refresh on a green verified run; a green draft run promotes NOTHING —
    promotion is a review decision. Auth, input, refused and runner errors leave
    trust alone: the map did not cause them. A downgrade is noted on the result
    as `trust_change`, so write_run keeps the one run that explains the flag (#52)."""
    trust = workflow.get("trust")
    drifted = [name for outcomes in (result.get("fingerprints", {}), result.get("scripts", {}))
               for name, s in outcomes.items() if s == "mismatch"]
    if CLASSES[result["class"]].may_downgrade_trust:
        if trust != "broken":
            _set_workflow_key(wf_path, "trust", "broken")
            result["trust_change"] = f"{trust or 'unset'} -> broken"
            note = f" (drifted: {', '.join(drifted)})" if drifted else ""
            print(f"trust: {trust or 'unset'} -> broken in {wf_path.name}{note}",
                  file=sys.stderr)
    elif result["status"] == "passed" and trust == "verified":
        _set_workflow_key(wf_path, "verified_at", f'"{result["finished_at"][:10]}"')


def _last_line(node) -> int:
    """The 0-based last line a node's own text is on. A block collection's
    end mark sits at the next token, past any trailing comment, so it is
    found through its last child instead."""
    if isinstance(node, yaml.MappingNode) and node.value and not node.flow_style:
        return _last_line(node.value[-1][1])
    if isinstance(node, yaml.SequenceNode) and node.value and not node.flow_style:
        return _last_line(node.value[-1])
    end = node.end_mark
    return end.line - 1 if end.column == 0 else end.line


def _child(node, key: str):
    for k, v in node.value:
        if k.value == key:
            return k, v
    return None, None


def _set_step_shape(wf_path: Path, phase: str, index: int, shape):
    """Write one step's `shape:` in place, as text, so every comment, key order
    and the rest of the file survive: a stored shape's lines are replaced, a new
    one goes after the step's last line."""
    text = wf_path.read_text(encoding="utf-8")
    _, steps = _child(_child(yaml.compose(text), "workflow")[1], phase)
    step = steps.value[index]
    if step.flow_style:
        raise RunError(f"{wf_path.name}: {phase}[{index}] is a flow mapping; write it as a "
                       "block to learn its shape")
    indent = " " * step.value[0][0].start_mark.column
    if isinstance(shape, str) or not shape:
        block = [f"shape: {json.dumps(shape)}"]
    else:
        block = ["shape:"] + ["  " + line for line in yaml.safe_dump(
            shape, default_flow_style=False, sort_keys=False).splitlines()]
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    key, value = _child(step, "shape")
    if key is not None:
        start, end = key.start_mark.line, _last_line(value) + 1
    else:
        start = end = _last_line(step) + 1
        if lines and not lines[start - 1].endswith(("\n", "\r")):
            lines[start - 1] += newline
    lines[start:end] = [indent + line + newline for line in block]
    wf_path.write_text("".join(lines), encoding="utf-8")


def learn_shapes(wf_path: Path, learned: list, result: dict):
    """--learn-shape: on a passing run, store each script step's output shape in
    the workflow YAML. Nothing else changes, trust and verified_at included."""
    if result["status"] != "passed" or result["class"] != "ok":
        print(f"learn-shape: the run did not pass ({result['class']}); "
              f"{wf_path.name} is unchanged", file=sys.stderr)
        return
    for phase, index, shape in learned:
        _set_step_shape(wf_path, phase, index, shape)
        print(f"learn-shape: {phase}[{index}] shape written to {wf_path.name}",
              file=sys.stderr)


# ---------------------------------------------------------------------------
# Orchestration

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_id_of(result: dict, instance: str) -> str:
    """<workflow>.<utc-ts>.<tier>.<instance>.<suffix> (contracts/run-record.yaml):
    the start to the millisecond plus a random suffix, so runs started together
    still get folders of their own."""
    start = _dt.datetime.fromisoformat(result["started_at"].replace("Z", "+00:00"))
    stamp = start.strftime("%Y-%m-%dT%H%M%S.") + f"{start.microsecond // 1000:03d}Z"
    return (f"{result['workflow']}.{stamp}.{result.get('tier') or '-'}.{instance}."
            f"{secrets.token_hex(2)}")


def run_workflow(root: Path, projects: Path, name: str, cli_params: dict, headed: bool,
                 pre_authorized: set[str] = frozenset(), persona_name: str | None = None,
                 context_name: str | None = None, runs: Path | None = None,
                 record: bool = False, trigger: str = "manual",
                 learn_shape: bool = False) -> tuple[dict, Path | None]:
    wf_path, data, owner = find_workflow(root, projects, name)
    workflow = data.get("workflow", {})

    pre = preflight(root, workflow, owner, cli_params, persona_name, frozenset(pre_authorized))
    consented = gate(pre) or frozenset()
    require_params(workflow, cli_params)
    tier, primary = pre.tier, pre.sites[0]
    persona = load_persona(root, primary, persona_name)
    context = load_context(root, primary, context_name, workflow)

    bindings = Bindings(workflow, cli_params, context)
    runner = Runner(root, wf_path, workflow, bindings, owner, headed=headed,
                    persona=persona, pre_authorized=set(pre_authorized) | consented,
                    learn_shape=learn_shape)

    result = {
        "workflow": workflow.get("name", name),
        "site": primary,
        "tier": tier,
        "status": "passed",
        "class": "ok",
        "next": "",
        "started_at": utc_now(),
        "finished_at": "",
        "parameters": dict(bindings.params),
        "fixtures": dict(bindings.fixtures),
        "captures": {},
        "assertions": [],
        "evidence": [],
        "error": "",
    }
    if not record and workflow.get("rollback") != "snapshot":
        execute(runner, workflow, bindings, wf_path, primary, result)
        return result, None
    recorder = RunRecord(runs, owner, trigger, result)
    recorder.start(result)
    try:
        execute(runner, workflow, bindings, wf_path, primary, result)
        recorder.finish(result)
    except BaseException as exc:
        recorder.stopped(result, exc)
        raise
    return result, recorder.folder


def unstarted_result(name: str, exc: RunError) -> dict:
    """The result of a run refused before its first step: no record, nothing
    ran, trust untouched."""
    now = utc_now()
    return {"workflow": name, "site": "", "tier": "-", "status": "error",
            "class": exc.cls, "next": next_step(exc.cls, name, exc.hint),
            "started_at": now, "finished_at": now, "parameters": {}, "fixtures": {},
            "captures": {}, "assertions": [], "evidence": [], "fingerprints": {},
            "scripts": {}, "counts": {"total": 0, "passed": 0, "failed": 0}, "error": str(exc)}


def step_label(step: dict) -> str:
    lines = str(step.get("description") or "").strip().splitlines()
    return lines[0] if lines else " ".join(
        str(step[k]) for k in ("action", "page", "element", "script") if step.get(k))


def parameters_schema(workflow: dict) -> dict:
    properties, required = {}, []
    for p in workflow.get("parameters") or []:
        prop = {"type": "string"}
        if p.get("description"):
            prop["description"] = str(p["description"]).strip()
        if p.get("type") == "select" and p.get("options"):
            prop["enum"] = [str(o) for o in p["options"]]
        if p.get("default") not in (None, ""):
            prop["default"] = str(p["default"])
        elif p.get("required"):
            required.append(p["name"])
        properties[p["name"]] = prop
    return {"type": "object", "properties": properties, "required": required}


def describe_workflow(root: Path, projects: Path, name: str) -> dict:
    _, data, owner = find_workflow(root, projects, name)
    workflow = data.get("workflow", {})
    return {
        "name": workflow.get("name", name),
        "owner": owner.name,
        "description": str(workflow.get("description") or "").strip(),
        "mode": workflow.get("mode"),
        "effect": workflow.get("effect"),
        "parameters": parameters_schema(workflow),
        "steps": [{"number": number, "phase": phase, "action": step.get("action"),
                   "label": step_label(step)}
                  for number, (phase, step) in enumerate(
                      ((ph, s) for ph in tree.PHASES for s in workflow.get(ph) or []), 1)],
    }


def execute(runner: Runner, workflow: dict, bindings: Bindings, wf_path: Path, primary: str,
            result: dict):
    attempt(runner, workflow, bindings, primary, result)
    runner.confirm_drift(result, primary)
    if runner.learn_shape:
        learn_shapes(wf_path, runner.learned, result)
    else:
        update_trust(wf_path, workflow, result)


def attempt(runner: Runner, workflow: dict, bindings: Bindings, primary: str, result: dict):
    """Run the steps once and classify the outcome on `result`."""
    phase = "setup"
    ordered = [(ph, index, step) for ph in tree.PHASES
               for index, step in enumerate(workflow.get(ph) or [])]
    cls, hint = "error", ""
    try:
        if needs_browser(workflow):
            runner.start(primary)
        for number, (phase, index, step) in enumerate(ordered, 1):
            print(f"step {number}/{len(ordered)}: {step_label(step)}", file=sys.stderr,
                  flush=True)
            runner.run_step(step, phase, index, number)
    except WaitForPerson as wait:
        if any(not a["pass"] for a in runner.assertions):
            result["status"] = "failed"
        else:
            result["status"] = "waiting"
            result["waiting_for"] = wait.waiting_for
    except RunError as exc:
        result["status"] = "error"
        result["error"] = f"[{phase}] {exc}"
        result["failure"] = runner.build_failure()
        cls, hint = exc.cls, exc.hint
    except Exception as exc:  # Playwright timeouts, navigation errors, ...
        result["status"] = "error"
        result["error"] = f"[{phase}] {type(exc).__name__}: {str(exc).splitlines()[0]}"
        result["failure"] = runner.build_failure()
    finally:
        try:  # teardown is best-effort, even after a failure
            if result["status"] != "waiting":
                for index, step in enumerate(workflow.get("teardown") or []):
                    runner.run_step(step, "teardown", index)
        except Exception as exc:
            note = f"teardown incomplete: {str(exc).splitlines()[0]}"
            result["error"] = (result["error"] + "; " + note).lstrip("; ")
            if "failure" not in result:
                result["failure"] = runner.build_failure()
        runner.stop()
    if result.get("failure", {}).get("screenshot"):
        runner.evidence.append(result["failure"]["screenshot"])

    result["captures"] = bindings.captures
    result["snapshot"] = runner.snapshot
    result["assertions"] = runner.assertions
    result["evidence"] = runner.evidence
    result["fingerprints"] = runner.fingerprints
    result["scripts"] = runner.scripts
    if result["status"] == "passed" and any(not a["pass"] for a in runner.assertions):
        result["status"] = "failed"
    failed = [a for a in runner.assertions if not a["pass"]]
    drifted = "mismatch" in [*runner.fingerprints.values(), *runner.scripts.values()]
    # A drifted page explains whatever followed it, unless the raise site
    # named a cause of its own.
    if result["status"] != "error":
        cls = "drift" if drifted else "assert" if failed else "ok"
    elif cls == "error" and drifted:
        cls = "drift"
    if cls == "assert":
        hint = f"assertion {failed[0]['id']}"
    result["class"] = cls
    result["next"] = next_step(cls, result["workflow"], hint)
    if "failure" in result:
        result["failure"].update({"class": cls, "next": result["next"]})
    total = len(runner.assertions)
    passed = sum(1 for a in runner.assertions if a["pass"])
    result["counts"] = {"total": total, "passed": passed, "failed": total - passed}
    result["finished_at"] = utc_now()


SUMMARY_ENTRIES = 30
SUMMARY_VALUE_CHARS = 200
HEADLINE_CHARS = 200


def summary_of(captures: dict) -> list[dict]:
    entries = []

    def walk(label: str, value):
        if isinstance(value, dict) and value:
            for key, inner in value.items():
                walk(f"{label}.{key}", inner)
            return
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        entries.append({"label": label, "value": text[:SUMMARY_VALUE_CHARS]})

    for name, value in (captures or {}).items():
        walk(name, value)
    return entries[:SUMMARY_ENTRIES]


def assertion_counts(result: dict) -> dict | None:
    if result.get("counts"):
        return result["counts"]
    if not result.get("assertions"):
        return None
    total = len(result["assertions"])
    passed = sum(1 for a in result["assertions"] if a.get("pass"))
    return {"total": total, "passed": passed, "failed": total - passed}


def error_of(result: dict) -> str:
    if result.get("error"):
        return result["error"].splitlines()[0]
    failed = [a for a in result.get("assertions") or [] if not a.get("pass")]
    if result["status"] != "failed" or not failed:
        return ""
    first = failed[0]
    more = f" (+{len(failed) - 1} more)" if len(failed) > 1 else ""
    return " ".join(f"assertion {first.get('id')} failed: expected {first.get('expect')!r}, "
                    f"got {first.get('actual')!r}{more}".split())[:HEADLINE_CHARS]


def headline_of(result: dict, counts: dict | None, summary: list[dict], error: str) -> str:
    parts = [result["status"]]
    if result["status"] == "error" and error:
        parts.append(error)
    if result.get("waiting_for"):
        parts.append(f"at step {result['waiting_for']['step']}: {result['waiting_for']['label']}")
    if counts and counts["total"]:
        parts.append(f"{counts['passed']}/{counts['total']} assertions passed")
    parts += [f"{e['label']}: {e['value']}" for e in summary[:2]]
    return " ".join(" · ".join(parts).split())[:HEADLINE_CHARS]


if os.name == "nt":
    import msvcrt

    def _lock(fh, locked: bool):
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK if locked else msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(fh, locked: bool):
        fcntl.flock(fh, fcntl.LOCK_EX if locked else fcntl.LOCK_UN)


@contextlib.contextmanager
def locked_index(runs: Path, instance: str):
    """The instance's index, open for reading and appending under its exclusive lock."""
    path = runs / tree.LIB / f"index.{instance}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+b") as fh:
        _lock(fh, True)
        try:
            yield fh
        finally:
            _lock(fh, False)


def _append(fh, line: dict):
    fh.seek(0, os.SEEK_END)
    fh.write((json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8"))
    fh.flush()


def append_index(runs: Path, instance: str, line: dict):
    with locked_index(runs, instance) as fh:
        _append(fh, line)


def write_atomic(path: Path, text: str):
    """On Windows the rename fails while a reader holds the target open, so it
    is retried briefly."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.05)


INDEX_KEYS = ("owner", "workflow", "tier", "instance", "started_at", "finished_at",
              "status", "answered_by", "answered_at", "trigger", "pid", "headline",
              "trust_change")
ANSWERED = ("passed", "failed")


def write_record(runs: Path, instance: str, run_id: str, folder: Path | None, run: dict,
                 index=None):
    """Write run.yaml, then append its index line (contracts/run-record.md). Without a
    folder, a swept run gets the index line alone. `index` is the locked index when the
    caller already holds it."""
    run = {k: v for k, v in run.items() if v not in (None, "", [], {})}
    if folder is not None:
        write_atomic(folder / "run.yaml",
                     yaml.safe_dump({"run": run}, sort_keys=False, allow_unicode=True))
    line = {"run_id": run_id, **{k: run[k] for k in INDEX_KEYS if k in run}}
    if index is None:
        append_index(runs, instance, line)
    else:
        _append(index, line)


def last_line(index, run_id: str) -> dict | None:
    index.seek(0)
    found = None
    for raw in index.read().decode("utf-8", errors="replace").splitlines():
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if isinstance(line, dict) and line.get("run_id") == run_id:
            found = line
    return found


def finish_waiting(runs: Path, run_id: str, status: str, by: str) -> dict:
    """End a waiting run at a person's answer: passed after an approval, failed after a
    rejection. A run that already ended with this answer is left as it is."""
    if status not in ANSWERED:
        raise RunError(f"a waiting run ends passed or failed, not '{status}'")
    if not by.strip():
        raise RunError("say who answered the run")
    instance = tree.instance_name()
    with locked_index(runs, instance) as index:
        return _finish_locked(runs, instance, index, run_id, status, by)


def _finish_locked(runs: Path, instance: str, index, run_id: str, status: str, by: str) -> dict:
    last = last_line(index, run_id)
    if last is None:
        raise RunError(f"no run '{run_id}' in the index of {instance}; "
                       "finish a run on the instance that ran it")
    if last["status"] != "waiting":
        if last["status"] == status and last.get("answered_by"):
            return {"run_id": run_id, "status": status, "answered_by": last["answered_by"],
                    "answered_at": last.get("answered_at"), "changed": False}
        raise RunError(f"run '{run_id}' is {last['status']}, not waiting")
    now = utc_now()
    error = f"rejected by {by}" if status == "failed" else ""
    folder = runs / tree.LIB / last["owner"] / run_id
    path = folder / "run.yaml"
    run = (load_yaml(path) or {}).get("run") if path.is_file() else None
    if not isinstance(run, dict):
        run, folder = dict(last), None
        run.pop("run_id", None)
    run.pop("waiting_for", None)
    summary = run.get("summary") or []
    answer = error or f"approved by {by}"
    run.update(status=status, finished_at=now, answered_by=by, answered_at=now, error=error,
               headline=" ".join(" · ".join(
                   [status, answer, *(f"{e['label']}: {e['value']}" for e in summary[:2])]
               ).split())[:HEADLINE_CHARS])
    write_record(runs, instance, run_id, folder, run, index)
    return {"run_id": run_id, "status": status, "answered_by": by, "answered_at": now,
            "changed": True}


class RunRecord:
    def __init__(self, runs: Path, owner: Owner, trigger: str, result: dict):
        self.runs, self.owner, self.trigger = runs, owner, trigger
        self.instance = tree.instance_name()
        self.run_id = run_id_of(result, self.instance)
        self.folder = runs / tree.LIB / owner.name / self.run_id

    def _write(self, run: dict):
        write_record(self.runs, self.instance, self.run_id, self.folder, run)

    def _base(self, result: dict) -> dict:
        return {
            "lib": tree.LIB,
            "owner": self.owner.name,
            "workflow": result["workflow"],
            "tier": result.get("tier") or "-",
            "instance": self.instance,
            "started_at": result["started_at"],
            "finished_at": result["finished_at"],
            "status": result["status"],
            "trigger": self.trigger,
            "pid": os.getpid(),
            "keep": ("keep" if result.get("trust_change")
                     else str(self.owner.project.get("keep") or tree.DEFAULT_KEEP)),
        }

    def start(self, result: dict):
        self.folder.mkdir(parents=True, exist_ok=True)
        self._write({**self._base(result), "status": "running", "headline": "running",
                     "files": ["run.yaml"]})

    def finish(self, result: dict):
        folder = self.folder
        folder.mkdir(parents=True, exist_ok=True)
        files = ["run.yaml", "result.json"]
        for name, value in (result.get("snapshot") or {}).items():
            (folder / "snapshot").mkdir(exist_ok=True)
            (folder / "snapshot" / f"{name}.json").write_text(
                json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
            files.append(f"snapshot/{name}.json")
        for src in result.get("evidence") or []:
            p = Path(src)
            if p.is_file():
                (folder / "evidence").mkdir(exist_ok=True)
                shutil.copy2(p, folder / "evidence" / p.name)
                files.append(f"evidence/{p.name}")
        (folder / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        summary = summary_of(result.get("captures"))
        counts = assertion_counts(result)
        error = error_of(result)
        self._write({
            **self._base(result),
            "headline": headline_of(result, counts, summary, error),
            "error": error,
            "waiting_for": result.get("waiting_for"),
            "trust_change": result.get("trust_change"),
            "assertions": counts,
            "summary": summary,
            "files": files,
        })

    def stopped(self, result: dict, exc: BaseException):
        """The runner failed after the run started, so the record ends as an
        error instead of reading as lost."""
        self.folder.mkdir(parents=True, exist_ok=True)
        error = " ".join(f"runner stopped: {type(exc).__name__}: {exc}".split())[:HEADLINE_CHARS]
        self._write({
            **self._base(result),
            "finished_at": utc_now(),
            "status": "error",
            "headline": f"error · {error}"[:HEADLINE_CHARS],
            "error": error,
            "files": sorted({p.relative_to(self.folder).as_posix()
                             for p in self.folder.rglob("*") if p.is_file()} | {"run.yaml"}),
        })


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workflow", nargs="?",
                    help="workflow name (filename stem or its name: field)")
    ap.add_argument("--finish", metavar="RUN_ID",
                    help="end a waiting run at a person's answer, then exit "
                         "(with --status and --by)")
    ap.add_argument("--status", choices=ANSWERED,
                    help="--finish: passed after an approval, failed after a rejection")
    ap.add_argument("--by", help="--finish: who answered")
    ap.add_argument("--sweep", action="store_true",
                    help="only delete run folders whose `keep` has run out, then exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --sweep: list what would be removed, remove nothing")
    ap.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                    help="workflow parameter (repeatable)")
    ap.add_argument("--root", default=None,
                    help="map repository to run against (default: this repo)")
    ap.add_argument("--projects", default=None,
                    help="the projects tree, when it is not inside --root")
    ap.add_argument("--runs", default=None,
                    help="the runs store, when it is not inside --root or beside it")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--preflight", action="store_true",
                    help="print what the run would be allowed to do, then exit 0 "
                         "without running it")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--record", action="store_true",
                    help="write the run folder to the runs store (schema/run.yaml); "
                         "always on for a workflow with rollback: snapshot")
    ap.add_argument("--learn-shape", action="store_true",
                    help="on a passing run, write each script step's output shape into "
                         "the workflow YAML instead of checking it; nothing else changes")
    ap.add_argument("--trigger", choices=("schedule", "manual", "ui"), default="manual",
                    help="who started the run, written to the record (default: manual)")
    ap.add_argument("--yes-write", action="store_true",
                    help="pre-authorize the 'write' class where policy says ask")
    ap.add_argument("--yes-destructive", action="store_true",
                    help="pre-authorize the 'destructive' class where policy says ask")
    ap.add_argument("--yes-auth", action="store_true",
                    help="pre-authorize automated login where policy says ask")
    ap.add_argument("--persona", default=None,
                    help="persona to run as (default: the site's only persona, if any)")
    ap.add_argument("--context", default=None,
                    help="tenant context to bind (default: the site's only one, "
                         "when the workflow requires a context)")
    args = ap.parse_args(argv)
    if args.finish and not (args.status and args.by):
        ap.error("--finish needs --status and --by")
    if not args.workflow and not args.sweep and not args.finish:
        ap.error("a workflow name is required unless --sweep or --finish is given")

    root = Path(args.root).resolve() if args.root else FRAMEWORK_ROOT
    projects = Path(tree.projects_root(str(root), args.projects))
    runs = Path(tree.runs_root(str(root), args.runs))
    if args.finish:
        try:
            done = finish_waiting(runs, args.finish, args.status, args.by)
        except RunError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(done) if args.json else
              f"{done['run_id']}: {done['status']}, answered by {done['answered_by']}"
              + ("" if done["changed"] else " (already)"))
        return 0
    if args.sweep:
        removed = tree.sweep_runs(runs, dry_run=args.dry_run)
        verb = "would be removed" if args.dry_run else "removed"
        for folder in removed:
            print(f"{verb}: {folder}")
        print(f"sweep {runs}: {len(removed)} run folder(s) {verb}")
        return 0
    cli_params = {}
    for item in args.param:
        if "=" not in item:
            ap.error(f"--param needs KEY=VALUE, got '{item}'")
        key, value = item.split("=", 1)
        cli_params[key] = value

    pre_authorized = {cls for cls, flag in
                      (("write", args.yes_write), ("destructive", args.yes_destructive),
                       ("auth", args.yes_auth))
                      if flag}
    if args.preflight:
        try:
            _, data, owner = find_workflow(root, projects, args.workflow)
            pre = preflight(root, data.get("workflow", {}), owner, cli_params,
                            args.persona, frozenset(pre_authorized))
        except RunError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(dataclasses.asdict(pre), indent=2, ensure_ascii=False))
        else:
            print(f"{pre.workflow}: {pre.outcome}")
            for cls, d in pre.classes.items():
                print(f"  {cls}: {d.verdict}  {d.where()}, rule: {d.source or 'defaults'}")
            print(f"  lock: {pre.lock_key}")
        return 0
    try:
        result, record = run_workflow(root, projects, args.workflow, cli_params,
                                      args.headed, pre_authorized, args.persona,
                                      args.context, runs, args.record, args.trigger,
                                      args.learn_shape)
    except RunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps(unstarted_result(args.workflow, exc), indent=2,
                             ensure_ascii=False))
        return 2

    if record:
        print(f"record: {record}", file=sys.stderr)
        if result.get("trust_change"):
            print(f"kept (keep: keep): this run set trust {result['trust_change']}; "
                  f"delete the folder or lower its keep once trust is restored", file=sys.stderr)
        for folder in tree.sweep_runs(runs):
            print(f"swept: {folder}", file=sys.stderr)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        c = result["counts"]
        print(f"{result['workflow']}: {result['status']} "
              f"({c['passed']}/{c['total']} assertions passed)")
        for a in result["assertions"]:
            print(f"  {'PASS' if a['pass'] else 'FAIL'}  {a['id']}  "
                  f"expect={a['expect']!r} actual={a['actual']!r}")
        if result.get("waiting_for"):
            w = result["waiting_for"]
            print(f"  waiting for a person at step {w['step']}: {w['label']} ({w['reason']})")
        if result["error"]:
            print(f"  error: {result['error']}")
        if result["next"]:
            print(f"  {result['class']}, next: {result['next']}")
        replay = (result.get("failure") or {}).get("replay")
        if replay:
            print(f"  replay: {replay['status']}"
                  + (f" ({replay['reason']})" if replay.get("reason") else ""))
    return {"passed": 0, "waiting": 0, "failed": 1, "error": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
