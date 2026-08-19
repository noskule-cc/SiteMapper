"""Headless deterministic workflow runner (#18/#20).

    python scripts/run.py <workflow> [--param key=value ...] [--root PATH]
                          [--json] [--headed] [--record]

Executes a `mode: deterministic` workflow against its mapped site(s) with no
LLM in the loop, and emits the neutral `result` object (schema/result.yaml).
LLM for decisions, code for work (docs/CODE_OVER_LLM.md): the map must be
complete enough that no step needs judgement — if it isn't, this runner fails
loudly and the repair loop (an LLM, on demand) fixes the map.

Browser automation is Playwright driving the installed Chrome
(channel="chrome"): its auto-waiting covers ordinary load waiting, so
workflows carry no generic sleeps. Playwright is imported lazily — every other
script in this repo still needs nothing beyond PyYAML.

`--root` points at a separate (usually private) map repository, same
semantics as check.py / inventory.py.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent

# Actions a deterministic workflow may contain. `verify` needs judgement, so
# its presence (or mode: agentic) makes the workflow un-runnable here.
MECHANICAL_ACTIONS = {"navigate", "click", "input", "read", "assert", "wait", "key", "script"}


class RunError(Exception):
    """Fatal runner error — maps to result.status = error."""


# ---------------------------------------------------------------------------
# Loading

def load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_workflow(root: Path, name: str):
    """Locate a workflow YAML by name (filename stem or workflow.name)."""
    candidates = list(root.glob("sites/*/workflows/*.yaml"))
    candidates += list(root.glob("projects/*/workflows/*.yaml"))
    for path in candidates:
        if path.stem == name:
            return path, load_yaml(path)
    for path in candidates:  # fall back to the name: field
        data = load_yaml(path)
        wf = (data or {}).get("workflow", {})
        if wf.get("name") == name:
            return path, data
    raise RunError(
        f"no workflow named '{name}' under {root}/sites/*/workflows or projects/*/workflows"
    )


class Site:
    """One mapped site: config, settings and its page maps."""

    def __init__(self, root: Path, site_name: str):
        self.name = site_name
        self.dir = root / "sites" / site_name
        site_file = self.dir / "site.yaml"
        if not site_file.is_file():
            raise RunError(f"site '{site_name}' has no {site_file}")
        self.config = load_yaml(site_file).get("site", {})
        self.base_url = (self.config.get("base_url") or "").rstrip("/")
        self.pages = {}
        for page_file in (self.dir / "pages").glob("*.yaml"):
            self.pages[page_file.stem] = load_yaml(page_file).get("page", {})

    def page(self, page_name: str):
        if page_name not in self.pages:
            raise RunError(f"site '{self.name}' has no page map '{page_name}'")
        return self.pages[page_name]

    def element(self, page_name: str, element_name: str):
        for el in self.page(page_name).get("elements") or []:
            if el.get("name") == element_name:
                return el
            for child in el.get("children") or []:
                if child.get("name") == element_name:
                    return child
        raise RunError(
            f"page '{page_name}' ({self.name}) maps no element '{element_name}'"
        )


def load_persona(root: Path, site_name: str, persona_name: str | None):
    """Resolve the persona for a site: --persona, else the site's only one,
    else anonymous (None). Site-scoped: sites/<site>/personas/<name>.yaml."""
    pdir = root / "sites" / site_name / "personas"
    files = sorted(pdir.glob("*.yaml")) if pdir.is_dir() else []
    if persona_name:
        for f in files:
            if f.stem == persona_name:
                return load_yaml(f).get("persona", {})
        raise RunError(f"site '{site_name}' has no persona '{persona_name}' "
                       f"({[f.stem for f in files] or 'none defined'})")
    if len(files) == 1:
        return load_yaml(files[0]).get("persona", {})
    if not files:
        return None
    raise RunError(f"site '{site_name}' has several personas "
                   f"({[f.stem for f in files]}) — pass --persona")


def state_path(root: Path, site_name: str, persona: dict) -> Path:
    """Saved browser state: a credential, so always local and gitignored."""
    custom = persona.get("storage_state")
    if custom:
        return Path(custom) if Path(custom).is_absolute() else root / custom
    return root / ".runner" / "state" / f"{site_name}.{persona.get('name', 'default')}.json"


def env_secret(ref: str, what: str) -> str:
    import os
    if not (ref or "").startswith("env:"):
        raise RunError(f"persona {what} must be an env: reference, got '{ref}' — "
                       "committed files never contain secrets (schema/persona.yaml)")
    value = os.environ.get(ref[4:])
    if not value:
        raise RunError(f"environment variable '{ref[4:]}' ({what}) is not set")
    return value


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base or {})
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def resolve_settings(root: Path, site: Site, page_name: str | None):
    """config.yaml (framework, then map repo) -> site.yaml -> page. Most specific wins."""
    merged: dict = {}
    for cfg in {FRAMEWORK_ROOT / "config.yaml", root / "config.yaml"}:
        if cfg.is_file():
            merged = deep_merge(merged, (load_yaml(cfg) or {}).get("settings", {}))
    merged = deep_merge(merged, site.config.get("settings", {}))
    if page_name and page_name in site.pages:
        merged = deep_merge(merged, site.pages[page_name].get("settings", {}))
    return merged


# ---------------------------------------------------------------------------
# Variables

VAR_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


class Bindings:
    """Resolves $name from parameters, fixtures and captured variables."""

    def __init__(self, workflow: dict, cli_params: dict):
        self.params = {}
        for p in workflow.get("parameters") or []:
            name = p["name"]
            if name in cli_params:
                value = cli_params[name]
                options = p.get("options")
                if p.get("type") == "select" and options and value not in options:
                    raise RunError(
                        f"parameter '{name}' must be one of {options}, got '{value}'"
                    )
                self.params[name] = value
            elif p.get("default") not in (None, ""):
                self.params[name] = p["default"]
            elif p.get("required"):
                raise RunError(
                    f"required parameter '{name}' missing — pass --param {name}=..."
                )
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
        for source in (self.params, self.fixtures, self.captures):
            if name in source:
                return str(source[name])
        raise RunError(f"unresolved variable '${name}' (not a parameter, fixture or capture)")

    def resolve(self, text):
        if not isinstance(text, str):
            return text
        return VAR_RE.sub(lambda m: self.lookup(m.group(1)), text)


# ---------------------------------------------------------------------------
# Browser execution

def build_locator(pw_page, element: dict, scope_value: str | None = None):
    """Map a page-map locator onto Playwright. One strategy, one call."""
    strategy = (element.get("locator") or {}).get("strategy")
    value = (element.get("locator") or {}).get("value")
    if not strategy or value is None:
        raise RunError(f"element '{element.get('name')}' has no usable locator")
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
        raise RunError(f"unknown locator strategy '{strategy}'")
    if scope_value:
        # value-scoped match inside a container/table: pick the matching item
        loc = loc.get_by_text(scope_value)
    return loc.first


class Runner:
    DEFAULT_TIMEOUT_MS = 10_000

    def __init__(self, root: Path, wf_path: Path, workflow: dict, bindings: Bindings,
                 headed: bool = False, persona: dict | None = None,
                 pre_authorized: set = frozenset()):
        self.root = root
        self.wf_path = wf_path
        self.workflow = workflow
        self.bindings = bindings
        self.headed = headed
        self.persona = persona
        self.pre_authorized = pre_authorized
        self.sites: dict[str, Site] = {}
        self.default_site = workflow.get("site")
        self.assertions: list[dict] = []
        self.evidence: list[str] = []
        self.current: dict = {}  # {phase, index, step} of the step in flight
        self.fingerprints: dict[str, str] = {}  # page -> ok | mismatch (watch, #24)
        self._last_page: str | None = None
        self._pw = None
        self.browser = None
        self.pw_page = None

    # -- sites ------------------------------------------------------------
    def site(self, step: dict) -> Site:
        name = self.bindings.resolve(step.get("site") or self.default_site)
        if not name:
            raise RunError("step names no site and the workflow has no default `site:`")
        if name not in self.sites:
            self.sites[name] = Site(self.root, name)
        return self.sites[name]

    # -- browser lifecycle -------------------------------------------------
    def start(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RunError(
                "Playwright is not installed. The runner needs it (the rest of "
                "SiteMapper does not): pip install playwright  — no browser "
                "download required, the installed Chrome is used."
            )
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(channel="chrome", headless=not self.headed)
        context_args = {}
        site_name = None
        if self.persona:
            site_name = self.workflow.get("site") or (self.workflow.get("sites") or [None])[0]
            state = state_path(self.root, site_name, self.persona)
            if self.persona.get("auth") == "session":
                if not state.is_file():
                    raise RunError(
                        f"persona '{self.persona.get('name')}' is auth: session but "
                        f"{state} does not exist — run once with a persona whose auth "
                        "is `human` (headed) to create it. The runner never logs in "
                        "silently."
                    )
                context_args["storage_state"] = str(state)
            elif state.is_file():  # human/automated reuse an existing state too
                context_args["storage_state"] = str(state)
        self.context = self.browser.new_context(**context_args)
        self.pw_page = self.context.new_page()
        self.pw_page.set_default_timeout(self.DEFAULT_TIMEOUT_MS)
        if self.persona and "storage_state" not in context_args:
            self._establish_session(site_name)

    def _establish_session(self, site_name: str):
        """First-time login for auth: human | automated. Saves storage_state."""
        persona = self.persona
        method = persona.get("auth")
        site = Site(self.root, site_name)
        state = state_path(self.root, site_name, persona)
        state.parent.mkdir(parents=True, exist_ok=True)
        if method == "human":
            if not self.headed:
                raise RunError(
                    f"persona '{persona.get('name')}' needs a first login by a human — "
                    "re-run with --headed, log in when the browser opens"
                )
            login_page = (persona.get("login") or {}).get("page")
            self.pw_page.goto(site.base_url + (site.page(login_page).get("url_pattern", "")
                                               if login_page else ""))
            try:
                input("Log in in the browser window, then press Enter here... ")
            except (EOFError, KeyboardInterrupt):
                raise RunError("no interactive console to wait on — auth: human needs one")
        elif method == "automated":
            settings = resolve_settings(self.root, site, None)
            verdict = permission_verdict(settings, "auth")
            if verdict == "deny" or (verdict == "ask" and "auth" not in self.pre_authorized):
                env = (settings.get("policy") or {}).get("environment", "?")
                raise RunError(
                    f"automated login is '{verdict}' for site '{site_name}' "
                    f"(environment: {env})" +
                    (" — pass --yes-auth to pre-authorize" if verdict == "ask" else
                     ". Use a `human`-seeded session instead (docs/PERMISSIONS.md).")
                )
            login = persona.get("login") or {}
            if not login.get("page"):
                raise RunError("auth: automated needs a `login:` block (schema/persona.yaml)")
            creds = persona.get("credential_ref") or {}
            user = env_secret(creds.get("username"), "credential_ref.username")
            pw = env_secret(creds.get("password"), "credential_ref.password")
            self.pw_page.goto(site.base_url + site.page(login["page"]).get("url_pattern", ""))
            build_locator(self.pw_page,
                          site.element(login["page"], login["username_element"])).fill(user)
            build_locator(self.pw_page,
                          site.element(login["page"], login["password_element"])).fill(pw)
            build_locator(self.pw_page,
                          site.element(login["page"], login["submit_element"])).click()
            self.pw_page.wait_for_load_state()
        else:
            raise RunError(f"persona auth method '{method}' is not session|human|automated")
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
    def run_step(self, step: dict, phase: str = "steps", index: int = 0):
        self.current = {"phase": phase, "index": index, "step": step}
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
        getattr(self, f"do_{action}")(step)
        if page_name:
            self._last_page = page_name

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
            try:
                shots = self.root / ".runner"
                shots.mkdir(exist_ok=True)
                stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
                shot = shots / f"{self.workflow.get('name', 'run')}-{stamp}.png"
                self.pw_page.screenshot(path=str(shot), full_page=False)
                failure["screenshot"] = str(shot)
            except Exception:
                pass
        return failure

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
                    "placeholders — navigate with an explicit `value:` instead"
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

    def do_read(self, step):
        site = self.site(step)
        element = self._element(step, site)
        text = build_locator(self.pw_page, element).inner_text()
        if step.get("capture"):
            self.bindings.captures[step["capture"]] = text.strip()

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

    def do_script(self, step):
        site = self.site(step)
        script_name = step.get("script")
        declared = {s.get("name") for s in site.config.get("scripts") or []}
        if script_name not in declared:
            raise RunError(
                f"script '{script_name}' is not declared in {site.name}/site.yaml scripts:"
            )
        args = self.bindings.resolve(step.get("value") or "")
        cmd = [sys.executable, str(site.dir / "scripts" / script_name)] + args.split()
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=self.root)
        if proc.returncode != 0:
            raise RunError(f"script '{script_name}' failed:\n{proc.stderr.strip()}")
        if step.get("capture"):
            out = proc.stdout.strip()
            try:
                self.bindings.captures[step["capture"]] = json.loads(out)
            except json.JSONDecodeError:
                self.bindings.captures[step["capture"]] = out

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
        if isinstance(expect, dict) and "url_matches" in expect:
            url = self.pw_page.url
            return url, re.search(self.bindings.resolve(expect["url_matches"]), url) is not None
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
                n = self._count_all(element)  # all matches, not .first
                return n, n == expect["count"]
            text = locator.inner_text().strip()
            if "contains" in expect:
                needle = self.bindings.resolve(expect["contains"])
                return text, needle in text
            if "equals" in expect:
                return text, text == self.bindings.resolve(expect["equals"])
            if "value" in expect:
                val = locator.input_value()
                return val, val == self.bindings.resolve(expect["value"])
        raise RunError(f"unknown expect condition: {expect!r}")

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
# Permissions (#22) — action classes x allow/ask/deny, gated UP FRONT.

EFFECT_CLASS = {"read-only": "read", "mutating": "write", "destructive": "destructive"}
PERMISSION_DEFAULTS = {"read": "allow", "write": "ask", "auth": "ask", "destructive": "deny"}
STRICTNESS = {"allow": 0, "ask": 1, "deny": 2}


def permission_verdict(settings: dict, action_class: str) -> str:
    policy = settings.get("policy") or {}
    verdict = (policy.get("permissions") or {}).get(action_class)
    if not verdict and action_class == "write" and policy.get("safe_to_submit_forms"):
        verdict = "allow"  # legacy alias
    return verdict or PERMISSION_DEFAULTS[action_class]


def gate(root: Path, workflow: dict, sites: list[str], pre_authorized: set[str]):
    """Refuse or ask BEFORE the browser opens. `trust` grants nothing here.

    Cross-site workflows are gated against every involved site; the strictest
    verdict wins. `ask` resolves via --yes-<class>, then a TTY prompt, and
    degrades to deny when non-interactive (CI has no human to ask).
    """
    effect = workflow.get("effect")
    if effect not in EFFECT_CLASS:
        raise RunError(
            f"effect: {effect or 'undeclared'} — a headless run needs the workflow to "
            "declare read-only | mutating | destructive (schema/workflow.yaml)"
        )
    action_class = EFFECT_CLASS[effect]
    verdict, source = "allow", "defaults"
    for site_name in sites:
        site = Site(root, site_name)
        v = permission_verdict(resolve_settings(root, site, None), action_class)
        env = (resolve_settings(root, site, None).get("policy") or {}).get("environment", "?")
        if STRICTNESS[v] > STRICTNESS[verdict]:
            verdict, source = v, f"site '{site_name}' (environment: {env})"
    if verdict == "deny":
        raise RunError(
            f"permission denied: effect '{effect}' needs class '{action_class}' which is "
            f"'deny' for {source}. This is policy, not a bug — see docs/PERMISSIONS.md."
        )
    if verdict == "ask":
        if action_class in pre_authorized:
            return
        if sys.stdin.isatty():
            try:
                answer = input(
                    f"'{workflow.get('name')}' is {effect} and {source} says ask. "
                    "Proceed? [y/N] "
                )
            except (EOFError, KeyboardInterrupt):
                answer = ""  # a TTY that cannot actually answer is non-interactive
            if answer.strip().lower() == "y":
                return
            raise RunError(
                f"not authorized: class '{action_class}' is 'ask' for {source} and no "
                f"consent was given. Pass --yes-{action_class} to pre-authorize."
            )
        raise RunError(
            f"class '{action_class}' is 'ask' for {source}, and this run is non-interactive "
            f"— `ask` degrades to deny. Pass --yes-{action_class} to pre-authorize."
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
    """broken on failure/drift; verified_at refresh on a green verified run;
    a green draft run promotes NOTHING — promotion is a review decision."""
    trust = workflow.get("trust")
    drifted = [p for p, s in result.get("fingerprints", {}).items() if s == "mismatch"]
    if result["status"] in ("failed", "error") or drifted:
        if trust != "broken":
            _set_workflow_key(wf_path, "trust", "broken")
            note = f" (drifted: {', '.join(drifted)})" if drifted else ""
            print(f"trust: {trust or 'unset'} -> broken in {wf_path.name}{note}",
                  file=sys.stderr)
    elif result["status"] == "passed" and trust == "verified":
        _set_workflow_key(wf_path, "verified_at", f'"{result["finished_at"][:10]}"')


# ---------------------------------------------------------------------------
# Orchestration

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_workflow(root: Path, name: str, cli_params: dict, headed: bool,
                 pre_authorized: set[str] = frozenset(), persona_name: str | None = None):
    wf_path, data = find_workflow(root, name)
    workflow = data.get("workflow", {})

    mode = workflow.get("mode")
    if mode != "deterministic":
        raise RunError(
            f"'{name}' is mode: {mode or 'unset'} — only deterministic workflows can run "
            "headless. An agentic workflow needs an LLM host (docs/skills/run-workflow.md)."
        )
    for phase in ("setup", "steps", "teardown"):
        for step in workflow.get(phase) or []:
            if step.get("action") == "verify":
                raise RunError(
                    f"step in `{phase}` uses action: verify (judgement) — the workflow "
                    "cannot be deterministic; fix its mode or the step"
                )

    involved = [s for s in ([workflow.get("site")] if workflow.get("site") else
                            list(workflow.get("sites") or [])) if isinstance(s, str)
                and not s.startswith("$")]
    if not involved:
        raise RunError("workflow names no literal site — cannot resolve a permission scope")
    gate(root, workflow, involved, pre_authorized)
    persona = load_persona(root, involved[0], persona_name)

    bindings = Bindings(workflow, cli_params)
    runner = Runner(root, wf_path, workflow, bindings, headed=headed,
                    persona=persona, pre_authorized=pre_authorized)

    result = {
        "workflow": workflow.get("name", name),
        "site": workflow.get("site") or (workflow.get("sites") or [""])[0],
        "status": "passed",
        "started_at": utc_now(),
        "finished_at": "",
        "parameters": dict(bindings.params),
        "fixtures": dict(bindings.fixtures),
        "captures": {},
        "assertions": [],
        "evidence": [],
        "error": "",
    }

    phase = "setup"
    try:
        runner.start()
        for phase in ("setup", "steps"):
            for index, step in enumerate(workflow.get(phase) or []):
                runner.run_step(step, phase, index)
    except RunError as exc:
        result["status"] = "error"
        result["error"] = f"[{phase}] {exc}"
        result["failure"] = runner.build_failure()
    except Exception as exc:  # Playwright timeouts, navigation errors, ...
        result["status"] = "error"
        result["error"] = f"[{phase}] {type(exc).__name__}: {str(exc).splitlines()[0]}"
        result["failure"] = runner.build_failure()
    finally:
        try:  # teardown is best-effort, even after a failure
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
    result["assertions"] = runner.assertions
    result["evidence"] = runner.evidence
    result["fingerprints"] = runner.fingerprints
    if result["status"] == "passed" and any(not a["pass"] for a in runner.assertions):
        result["status"] = "failed"
    total = len(runner.assertions)
    passed = sum(1 for a in runner.assertions if a["pass"])
    result["counts"] = {"total": total, "passed": passed, "failed": total - passed}
    result["finished_at"] = utc_now()
    update_trust(wf_path, workflow, result)
    return result, wf_path


def write_record(result: dict, wf_path: Path):
    """results/<workflow>.<YYYY-MM-DD>.md next to the workflow's site/project."""
    results_dir = wf_path.parent.parent / "results"
    results_dir.mkdir(exist_ok=True)
    date = result["finished_at"][:10]
    path = results_dir / f"{result['workflow']}.{date}.md"
    lines = [
        f"# {result['workflow']} — run {date}",
        "",
        f"- **Status:** {result['status']}",
        f"- **Started:** {result['started_at']}  **Finished:** {result['finished_at']}",
        f"- **Runner:** scripts/run.py (headless, no LLM)",
        f"- **Parameters:** `{json.dumps(result['parameters'])}`",
        "",
        "| # | Assertion | Expect | Actual | Pass |",
        "|---|-----------|--------|--------|------|",
    ]
    for i, a in enumerate(result["assertions"], 1):
        lines.append(
            f"| {i} | {a['id']} | `{a['expect']}` | `{a['actual']}` | "
            f"{'✅' if a['pass'] else '❌'} |"
        )
    if result["error"]:
        lines += ["", f"**Error:** {result['error']}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("workflow", help="workflow name (filename stem or its name: field)")
    ap.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                    help="workflow parameter (repeatable)")
    ap.add_argument("--root", default=None,
                    help="map repository to run against (default: this repo)")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    ap.add_argument("--record", action="store_true",
                    help="write the results/<workflow>.<date>.md record")
    ap.add_argument("--yes-write", action="store_true",
                    help="pre-authorize the 'write' class where policy says ask")
    ap.add_argument("--yes-destructive", action="store_true",
                    help="pre-authorize the 'destructive' class where policy says ask")
    ap.add_argument("--yes-auth", action="store_true",
                    help="pre-authorize automated login where policy says ask")
    ap.add_argument("--persona", default=None,
                    help="persona to run as (default: the site's only persona, if any)")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve() if args.root else FRAMEWORK_ROOT
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
    try:
        result, wf_path = run_workflow(root, args.workflow, cli_params, args.headed,
                                       pre_authorized, args.persona)
    except RunError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.record:
        record = write_record(result, wf_path)
        print(f"record: {record}", file=sys.stderr)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        c = result["counts"]
        print(f"{result['workflow']}: {result['status']} "
              f"({c['passed']}/{c['total']} assertions passed)")
        for a in result["assertions"]:
            print(f"  {'PASS' if a['pass'] else 'FAIL'}  {a['id']}  "
                  f"expect={a['expect']!r} actual={a['actual']!r}")
        if result["error"]:
            print(f"  error: {result['error']}")
    return {"passed": 0, "failed": 1, "error": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
