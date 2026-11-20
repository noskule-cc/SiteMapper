"""A project's environments: what a run on a tier sees as $env, when the runner
refuses before the first step, and what check.py fails."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run  # noqa: E402

ENVIRONMENTS = """\
  environments:
    dev:
      user: bot
      pools:
        serials:
          free: ["A1", "A2"]
          used: { "A0": { by: earlier run } }
      mailboxes: { inbox: box }
      allows: { signing: true, customer_mail: false }
    prod:
      user: bot
      pools:
        serials: { free: [], used: {} }
      mailboxes: { inbox: box }
      allows: { signing: "partner 1 only" }
"""

WORKFLOW = """\
workflow:
  name: env-echo
  mode: deterministic
  effect: read-only
  consumes: [serials]
  tiers:
    required: [dev]
    allowed: [dev, prod]
  parameters:
    - { name: environment, type: select, options: [dev, prod], required: true }
    - { name: serial, type: text, required: false, default: "$env.pools.serials.next" }
  fixtures:
    dev: { tracker: demo-dev }
    prod: { tracker: demo }
  steps:
    - action: script
      site: $tracker
      script: echo.py
      value: "$env.user $serial $env.base_url $env.mailboxes.inbox"
      capture: seen
"""


def make_tree(base: Path, environments: str = ENVIRONMENTS, workflow: str = WORKFLOW) -> Path:
    root = base / "SiteMapper"
    for site, url in (("demo", "https://prod.invalid"), ("demo-dev", "https://dev.invalid")):
        (root / "sites" / site).mkdir(parents=True)
        (root / "sites" / site / "site.yaml").write_text(
            f"site:\n  name: {site}\n  base_url: {url}\n  settings:\n    policy:\n"
            f"      environment: {'prod' if site == 'demo' else 'dev'}\n", encoding="utf-8")
    (root / "apps" / "demo").mkdir(parents=True)
    (root / "apps" / "demo" / "app.yaml").write_text(
        "app:\n  name: Demo\n  tiers:\n    prod: demo\n    dev: demo-dev\n", encoding="utf-8")
    (root / "config.yaml").write_text(
        "settings:\n  mailboxes:\n    box: someone@example.invalid\n", encoding="utf-8")
    project = root / "projects" / "env-checks"
    (project / "workflows").mkdir(parents=True)
    (project / "scripts").mkdir()
    (project / "scripts" / "echo.py").write_text(
        "import json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8")
    (project / "project.yaml").write_text(
        "project:\n  name: Env checks\n  kind: test\n  app: demo\n"
        "  workflows: [env-echo.yaml]\n"
        "  scripts:\n    - { name: echo.py, description: prints its arguments as JSON }\n"
        + environments, encoding="utf-8")
    (project / "workflows" / "env-echo.yaml").write_text(workflow, encoding="utf-8")
    return root


class RunnerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)

    def run_on(self, tier: str, params=None, **tree_args):
        root = make_tree(self.base, **tree_args)
        return run.run_workflow(root, root / "projects", "env-echo",
                                {"environment": tier, **(params or {})}, headed=False)[0]

    def test_steps_see_the_tiers_environment(self):
        result = self.run_on("dev")
        self.assertEqual(result["status"], "passed", result["error"])
        self.assertEqual(result["captures"]["seen"],
                         ["bot", "A1", "https://dev.invalid", "box"])
        self.assertEqual(result["parameters"]["serial"], "A1")

    def test_a_callers_value_wins_over_an_env_default(self):
        result = self.run_on("dev", {"serial": "A2"})
        self.assertEqual(result["captures"]["seen"][1], "A2")

    def test_an_empty_consumed_pool_refuses_the_run(self):
        with self.assertRaisesRegex(run.RunError, "pool 'serials' of environment 'prod' "
                                                  "has no free entry"):
            self.run_on("prod")

    def test_a_tier_without_an_entry_refuses_the_run(self):
        with self.assertRaisesRegex(run.RunError, "no environments.prod entry"):
            self.run_on("prod", environments=ENVIRONMENTS.split("    prod:")[0])

    def test_describe_lists_each_tiers_environment(self):
        root = make_tree(self.base)
        described = run.describe_workflow(root, root / "projects", "env-echo")
        self.assertEqual(described["consumes"], ["serials"])
        dev = described["environments"]["dev"]
        self.assertEqual((dev["site"], dev["base_url"], dev["pools"]["serials"]["next"]),
                         ("demo-dev", "https://dev.invalid", "A1"))
        self.assertIsNone(described["environments"]["prod"]["pools"]["serials"]["next"])


class CheckTest(unittest.TestCase):
    def check(self, environments: str = ENVIRONMENTS, workflow: str = WORKFLOW):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_tree(Path(tmp), environments, workflow)
            return subprocess.run(
                [sys.executable, str(SCRIPTS / "check.py"), "--root", str(root),
                 "--only", "environments"], capture_output=True, text=True, encoding="utf-8")

    def assertFails(self, message: str, **tree_args):
        out = self.check(**tree_args)
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn(message, out.stdout)

    def test_a_complete_block_passes(self):
        out = self.check()
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_an_allowed_tier_without_an_entry_fails(self):
        self.assertFails("tier 'prod' is allowed but project 'env-checks' has no valid "
                         "environments.prod entry",
                         environments=ENVIRONMENTS.split("    prod:")[0])

    def test_a_consumed_pool_missing_on_a_tier_fails(self):
        self.assertFails("consumes pool 'serials', which environments.prod.pools does not have",
                         environments=ENVIRONMENTS.replace(
                             "        serials: { free: [], used: {} }\n", "        other: { free: [] }\n"))

    def test_an_entry_both_free_and_used_fails(self):
        self.assertFails("environments.dev.pools.serials: 'A0' is both free and used",
                         environments=ENVIRONMENTS.replace('["A1", "A2"]', '["A0", "A1"]'))

    def test_an_unknown_mailbox_key_fails(self):
        self.assertFails("environments.dev.mailboxes.inbox: 'nobox' is not a key of "
                         "settings.mailboxes",
                         environments=ENVIRONMENTS.replace("{ inbox: box }\n      allows: "
                                                           "{ signing: true",
                                                           "{ inbox: nobox }\n      allows: "
                                                           "{ signing: true"))

    def test_a_base_url_in_the_entry_fails_and_says_where_it_comes_from(self):
        self.assertFails("environments.dev.base_url is not an environment key "
                         "(user, pools, mailboxes, allows); the base URL is the tier site's",
                         environments=ENVIRONMENTS.replace(
                             "      user: bot\n      pools:\n        serials:\n          free: [\"A1\"",
                             "      base_url: https://dev.invalid\n      user: bot\n      pools:\n"
                             "        serials:\n          free: [\"A1\""))

    def test_an_env_reference_to_nothing_fails(self):
        self.assertFails("$env.mailboxes.outbox names nothing in environments.dev",
                         workflow=WORKFLOW.replace("$env.mailboxes.inbox", "$env.mailboxes.outbox"))


if __name__ == "__main__":
    unittest.main()
