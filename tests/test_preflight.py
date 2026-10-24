import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run  # noqa: E402

FRAMEWORK_CONFIG = (run.FRAMEWORK_ROOT / "config.yaml").as_posix()

SITES = {
    "prod": "site:\n  name: prod\n  base_url: https://prod.invalid\n",
    "stage": (
        "site:\n  name: stage\n  base_url: https://stage.invalid\n"
        "  settings:\n    policy:\n      environment: staging\n"
        "      permissions: { write: allow, auth: allow }\n"
    ),
}

WORKFLOWS = {
    "read-prod": ("prod", "read-only", ["script"]),
    "write-prod": ("prod", "mutating", ["script"]),
    "wipe-prod": ("prod", "destructive", ["script"]),
    "write-both": ("stage", "mutating", ["script", "script@prod"]),
    "read-stage-browser": ("stage", "read-only", ["navigate"]),
}

PERSONA = """\
persona:
  name: bot
  auth: automated
  fresh_login: true
  credential_ref: { username: "env:NOPE_USER", password: "env:NOPE_PASS" }
  login: { page: login, username_element: u, password_element: p, submit_element: s }
"""


def step(spec: str) -> str:
    action, _, site = spec.partition("@")
    lines = [f"    - action: {action}"]
    if site:
        lines.append(f"      site: {site}")
    lines.append("      script: noop.py" if action == "script" else "      page: home")
    return "\n".join(lines)


def make_tree(base: Path) -> Path:
    root = base / "SiteMapper"
    (root / "projects").mkdir(parents=True)
    for name, text in SITES.items():
        (root / "sites" / name / "workflows").mkdir(parents=True)
        (root / "sites" / name / "site.yaml").write_text(text, encoding="utf-8")
    (root / "sites" / "stage" / "personas").mkdir()
    (root / "sites" / "stage" / "personas" / "bot.yaml").write_text(PERSONA, encoding="utf-8")
    for name, (site, effect, steps) in WORKFLOWS.items():
        body = "\n".join(step(s) for s in steps)
        (root / "sites" / site / "workflows" / f"{name}.yaml").write_text(
            f"workflow:\n  name: {name}\n  site: {site}\n  mode: deterministic\n"
            f"  effect: {effect}\n  steps:\n{body}\n", encoding="utf-8")
    return root


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = make_tree(Path(self.tmp.name))
        self.stage_yaml = (self.root / "sites" / "stage" / "site.yaml").as_posix()

    def preflight(self, name: str, consent=frozenset()) -> run.Preflight:
        _, data, owner = run.find_workflow(self.root, self.root / "projects", name)
        return run.preflight(self.root, data["workflow"], owner, {}, consent=consent)

    def cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "run.py"), *args, "--root", str(self.root)],
            input="", capture_output=True, encoding="utf-8", timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})

    def test_read_only_on_production_is_allowed(self):
        self.assertEqual(self.preflight("read-prod"), run.Preflight(
            workflow="read-prod", effect="read-only", tier="-", sites=["prod"],
            persona=None, lock_key="prod/-",
            classes={"read": run.Decision("allow", "prod", "production", FRAMEWORK_CONFIG)},
            consent=[], needs_consent=[], outcome="allow"))

    def test_write_on_production_asks(self):
        self.assertEqual(self.preflight("write-prod"), run.Preflight(
            workflow="write-prod", effect="mutating", tier="-", sites=["prod"],
            persona=None, lock_key="prod/-",
            classes={"write": run.Decision("ask", "prod", "production", FRAMEWORK_CONFIG)},
            consent=[], needs_consent=["write"], outcome="ask"))

    def test_destructive_on_production_is_denied(self):
        self.assertEqual(self.preflight("wipe-prod"), run.Preflight(
            workflow="wipe-prod", effect="destructive", tier="-", sites=["prod"],
            persona=None, lock_key="prod/-",
            classes={"destructive": run.Decision("deny", "prod", "production",
                                                 FRAMEWORK_CONFIG)},
            consent=[], needs_consent=[], outcome="deny"))

    def test_strictest_site_decides_a_run_over_two_sites(self):
        self.assertEqual(self.preflight("write-both"), run.Preflight(
            workflow="write-both", effect="mutating", tier="-", sites=["stage", "prod"],
            persona="bot", lock_key="prod+stage/bot",
            classes={"write": run.Decision("ask", "prod", "production", FRAMEWORK_CONFIG)},
            consent=[], needs_consent=["write"], outcome="ask"))

    def test_one_run_consent_answers_the_ask_without_changing_the_verdict(self):
        self.assertEqual(self.preflight("write-prod", frozenset({"write"})), run.Preflight(
            workflow="write-prod", effect="mutating", tier="-", sites=["prod"],
            persona=None, lock_key="prod/-",
            classes={"write": run.Decision("ask", "prod", "production", FRAMEWORK_CONFIG)},
            consent=["write"], needs_consent=[], outcome="allow"))

    def test_automated_login_adds_the_auth_class_from_the_lead_site(self):
        self.assertEqual(self.preflight("read-stage-browser"), run.Preflight(
            workflow="read-stage-browser", effect="read-only", tier="-", sites=["stage"],
            persona="bot", lock_key="stage/bot",
            classes={"read": run.Decision("allow", "stage", "staging", FRAMEWORK_CONFIG),
                     "auth": run.Decision("allow", "stage", "staging", self.stage_yaml)},
            consent=[], needs_consent=[], outcome="allow"))

    def test_cli_prints_the_preflight_as_json_and_exits_zero_on_ask(self):
        proc = self.cli("write-prod", "--preflight", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {
            "workflow": "write-prod", "effect": "mutating", "tier": "-", "sites": ["prod"],
            "persona": None, "lock_key": "prod/-",
            "classes": {"write": {"verdict": "ask", "site": "prod",
                                  "environment": "production", "source": FRAMEWORK_CONFIG}},
            "consent": [], "needs_consent": ["write"], "outcome": "ask"})

    def test_cli_preflight_of_a_missing_workflow_names_it_and_fails(self):
        proc = self.cli("no-such-workflow", "--preflight", "--json")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("error: no workflow named 'no-such-workflow'", proc.stderr)

    def test_gate_refuses_a_non_interactive_ask_and_a_deny(self):
        asked = self.cli("write-prod")
        self.assertEqual(asked.returncode, 2)
        self.assertEqual(asked.stderr.strip(),
                         "error: class 'write' is 'ask' for site 'prod' (environment: "
                         "production), and this run is non-interactive — `ask` degrades "
                         "to deny. Pass --yes-write to pre-authorize.")
        denied = self.cli("wipe-prod")
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(denied.stderr.strip(),
                         "error: permission denied: effect 'destructive' needs class "
                         "'destructive' which is 'deny' for site 'prod' (environment: "
                         "production). This is policy, not a bug — see docs/permissions.md.")

    def test_a_denied_run_with_json_prints_a_refused_result(self):
        denied = self.cli("wipe-prod", "--json")
        self.assertEqual(denied.returncode, 2)
        result = json.loads(denied.stdout)
        self.assertEqual((result["workflow"], result["status"], result["class"],
                          result["next"], result["counts"]),
                         ("wipe-prod", "error", "refused",
                          "ask the site's owner whether this run may happen "
                          "(docs/permissions.md)", {"total": 0, "passed": 0, "failed": 0}))
        self.assertTrue(result["error"].startswith("permission denied: effect 'destructive'"))


if __name__ == "__main__":
    unittest.main()
