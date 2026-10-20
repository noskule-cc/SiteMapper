import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import yaml

RUN_PY = Path(__file__).resolve().parent.parent / "scripts" / "run.py"
INSTANCE = "TEST-PC"

SITE = """\
site:
  name: fixture
  base_url: https://example.invalid
  scripts:
    - name: wait.py
      description: sleeps for the seconds it is given
"""

WAIT_PY = """\
import sys, time
time.sleep(float(sys.argv[1]))
print("done")
"""

WORKFLOW = """\
workflow:
  name: {name}
  site: fixture
  mode: deterministic
  effect: read-only
  steps:
{steps}
"""

QUICK = "    - action: script\n      script: wait.py\n      value: \"0\"\n      capture: out"
STEPS = {
    "quick": QUICK,
    "slow": "    - action: script\n      script: wait.py\n      value: \"5\"",
    "person": "    - action: human\n      description: a person approves",
    "broken": "    - action: script\n      script: missing.py",
    "wrong": QUICK + "\n    - action: assert\n      element: out\n      expect: {equals: other}",
}


def make_tree(base: Path) -> Path:
    root = base / "SiteMapper"
    (root / "sites" / "fixture" / "scripts").mkdir(parents=True)
    (root / "sites" / "fixture" / "workflows").mkdir()
    (root / "projects").mkdir()
    (root / "config.yaml").write_text(
        "settings:\n  policy:\n    permissions:\n      read: allow\n", encoding="utf-8")
    (root / "sites" / "fixture" / "site.yaml").write_text(SITE, encoding="utf-8")
    (root / "sites" / "fixture" / "scripts" / "wait.py").write_text(WAIT_PY, encoding="utf-8")
    for name, steps in STEPS.items():
        (root / "sites" / "fixture" / "workflows" / f"{name}.yaml").write_text(
            WORKFLOW.format(name=name, steps=steps), encoding="utf-8")
    return root


def runner(root: Path, runs: Path, workflow: str, *flags: str) -> list[str]:
    return [sys.executable, str(RUN_PY), workflow, "--root", str(root),
            "--runs", str(runs), *flags]


def index_lines(runs: Path) -> list[dict]:
    path = runs / "SiteMapper" / f"index.{INSTANCE}.jsonl"
    if not path.exists():
        return []
    whole = path.read_text(encoding="utf-8").rpartition("\n")[0]
    return [json.loads(line) for line in whole.splitlines()]


def run_yaml(runs: Path, run_id: str) -> dict:
    path = runs / "SiteMapper" / "fixture" / run_id / "run.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))["run"]


class RunRecordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self.tmp.name)
        self.root = make_tree(base)
        self.runs = base / "runs"
        self.env = {**os.environ, "SITEMAPPER_INSTANCE": INSTANCE}
        self.addCleanup(self.tmp.cleanup)

    def run_to_end(self, workflow: str, *flags: str) -> subprocess.CompletedProcess:
        return subprocess.run(runner(self.root, self.runs, workflow, *flags),
                              env=self.env, capture_output=True, text=True, timeout=60)

    def test_recorded_run_writes_running_then_final_line_with_one_run_id(self):
        proc = self.run_to_end("quick", "--record")
        self.assertEqual(proc.returncode, 0, proc.stderr)

        first, final = index_lines(self.runs)
        self.assertEqual(first["run_id"], final["run_id"])
        self.assertEqual(first["status"], "running")
        self.assertNotIn("finished_at", first)
        self.assertEqual(final["status"], "passed")
        self.assertEqual(final["started_at"], first["started_at"])
        self.assertEqual(final["pid"], first["pid"])
        self.assertIn("finished_at", final)

        run = run_yaml(self.runs, final["run_id"])
        self.assertEqual(run["status"], "passed")
        self.assertEqual(run["files"], ["run.yaml", "result.json"])
        self.assertEqual(run["summary"], [{"label": "out", "value": "done"}])

    def test_killed_run_leaves_the_running_record_with_its_pid(self):
        proc = subprocess.Popen(runner(self.root, self.runs, "slow", "--record"),
                                env=self.env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 30
        while not index_lines(self.runs) and time.monotonic() < deadline:
            time.sleep(0.1)
        proc.kill()
        proc.wait(timeout=30)

        [line] = index_lines(self.runs)
        self.assertEqual(line["status"], "running")
        self.assertEqual(line["pid"], proc.pid)
        run = run_yaml(self.runs, line["run_id"])
        self.assertEqual(run["status"], "running")
        self.assertEqual(run["pid"], proc.pid)
        self.assertNotIn("finished_at", run)
        self.assertEqual(run["files"], ["run.yaml"])

    def test_run_stopping_at_a_person_step_ends_waiting(self):
        proc = self.run_to_end("person", "--record")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        statuses = [line["status"] for line in index_lines(self.runs)]
        self.assertEqual(statuses, ["running", "waiting"])
        run = run_yaml(self.runs, index_lines(self.runs)[1]["run_id"])
        self.assertEqual(run["waiting_for"],
                         {"step": 1, "label": "a person approves", "reason": ""})

    def test_run_failing_at_a_step_ends_error(self):
        proc = self.run_to_end("broken", "--record")
        self.assertEqual(proc.returncode, 2, proc.stderr)
        statuses = [line["status"] for line in index_lines(self.runs)]
        self.assertEqual(statuses, ["running", "error"])

    def test_run_failing_an_assertion_ends_failed(self):
        proc = self.run_to_end("wrong", "--record")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        statuses = [line["status"] for line in index_lines(self.runs)]
        self.assertEqual(statuses, ["running", "failed"])

    def wait_for_running(self, proc: subprocess.Popen) -> dict:
        deadline = time.monotonic() + 30
        while not index_lines(self.runs) and time.monotonic() < deadline:
            time.sleep(0.1)
        [line] = index_lines(self.runs)
        return line

    def test_run_whose_folder_is_swept_mid_run_still_ends_passed(self):
        proc = subprocess.Popen(runner(self.root, self.runs, "slow", "--record"),
                                env=self.env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        line = self.wait_for_running(proc)
        shutil.rmtree(self.runs / "SiteMapper" / "fixture" / line["run_id"])
        self.assertEqual(proc.wait(timeout=60), 0)

        self.assertEqual([l["status"] for l in index_lines(self.runs)], ["running", "passed"])
        self.assertEqual(run_yaml(self.runs, line["run_id"])["status"], "passed")

    def test_runner_failing_after_the_steps_ends_error_not_running(self):
        workflow = self.root / "sites" / "fixture" / "workflows" / "wrong.yaml"
        workflow.chmod(stat.S_IREAD)
        self.addCleanup(workflow.chmod, stat.S_IREAD | stat.S_IWRITE)
        proc = self.run_to_end("wrong", "--record")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("PermissionError", proc.stderr)

        first, final = index_lines(self.runs)
        self.assertEqual((first["status"], final["status"]), ("running", "error"))
        run = run_yaml(self.runs, final["run_id"])
        self.assertEqual(run["status"], "error")
        self.assertTrue(run["error"].startswith("runner stopped: PermissionError"), run["error"])
        self.assertIn("finished_at", run)

    def test_run_without_record_writes_nothing(self):
        proc = self.run_to_end("quick")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.runs.exists())


if __name__ == "__main__":
    unittest.main()
