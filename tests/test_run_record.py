import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
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



CRASH_PY = """\
import sys
print("first line", file=sys.stderr)
print("upstream said 503", file=sys.stderr)
sys.exit(1)
"""

VERIFIED = """\
workflow:
  name: {name}
  site: fixture
  mode: deterministic
  trust: verified
  effect: {effect}
{extra}  steps:
{steps}
"""

CLASSED = {
    "ok": ("read-only", "", QUICK),
    "input": ("read-only", "  parameters:\n    - name: size\n      required: true\n", QUICK),
    "refused": ("mutating", "", QUICK),
    "error": ("read-only", "",
              "    - action: script\n      script: crash.py"),
    "assert": ("read-only", "", STEPS["wrong"]),
    "auth": ("read-only", "", "    - action: navigate\n      value: /issues"),
}

SESSION = """\
persona:
  name: reader
  auth: session
  storage_state: {state}
"""
EXPIRED = {"cookies": [{"name": "s", "value": "x", "domain": "example.invalid", "path": "/",
                        "expires": 1700000000}], "origins": []}


class FailureClassTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self.tmp.name)
        self.root = make_tree(base)
        site = self.root / "sites" / "fixture"
        (site / "site.yaml").write_text(SITE + "    - name: crash.py\n", encoding="utf-8")
        (site / "scripts" / "crash.py").write_text(CRASH_PY, encoding="utf-8")
        state = base / "reader.json"
        state.write_text(json.dumps(EXPIRED), encoding="utf-8")
        (site / "personas").mkdir()
        (site / "personas" / "reader.yaml").write_text(SESSION.format(state=state.as_posix()),
                                                       encoding="utf-8")
        for name, (effect, extra, steps) in CLASSED.items():
            (site / "workflows" / f"c-{name}.yaml").write_text(
                VERIFIED.format(name=f"c-{name}", effect=effect, extra=extra, steps=steps),
                encoding="utf-8")
        self.runs = base / "runs"
        self.env = {**os.environ, "SITEMAPPER_INSTANCE": INSTANCE}
        self.addCleanup(self.tmp.cleanup)

    def run_json(self, cls: str) -> tuple[int, dict, str]:
        proc = subprocess.run(runner(self.root, self.runs, f"c-{cls}", "--json"),
                              env=self.env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60)
        workflow = self.root / "sites" / "fixture" / "workflows" / f"c-{cls}.yaml"
        trust = yaml.safe_load(workflow.read_text(encoding="utf-8"))["workflow"]["trust"]
        return proc.returncode, json.loads(proc.stdout), trust

    def test_a_passing_run_is_ok_with_no_next_step(self):
        code, result, trust = self.run_json("ok")
        self.assertEqual((code, result["status"], result["class"], result["next"], trust),
                         (0, "passed", "ok", "", "verified"))

    def test_a_missing_parameter_is_input_and_names_it(self):
        code, result, trust = self.run_json("input")
        self.assertEqual((code, result["status"], result["class"], result["next"], trust),
                         (2, "error", "input", "run c-input again with --param size=...",
                          "verified"))
        self.assertEqual(result["error"],
                         "required parameter 'size' missing — pass --param size=...")
        self.assertNotIn("trust_change", result)

    def test_an_ask_without_consent_is_refused(self):
        code, result, trust = self.run_json("refused")
        self.assertEqual((code, result["status"], result["class"], result["next"], trust),
                         (2, "error", "refused", "pass --yes-write to consent to this one run",
                          "verified"))

    def test_a_script_that_exits_non_zero_is_error_and_keeps_trust(self):
        code, result, trust = self.run_json("error")
        self.assertEqual((code, result["status"], result["class"], trust),
                         (2, "error", "error", "verified"))
        self.assertEqual(result["next"], "fix script 'crash.py' (its stderr is in `error`), "
                                         "then run c-error again")
        self.assertEqual(result["error"],
                         "[steps] script 'crash.py' failed:\nfirst line\nupstream said 503")
        self.assertEqual((result["failure"]["class"], result["failure"]["next"]),
                         ("error", result["next"]))
        self.assertNotIn("trust_change", result)

    def test_an_expired_session_is_auth_and_keeps_trust(self):
        code, result, trust = self.run_json("auth")
        self.assertEqual((code, result["status"], result["class"], trust),
                         (2, "error", "auth", "verified"))
        self.assertEqual(result["next"], "refresh the session of persona 'reader': run c-auth "
                                         "once --headed with a persona whose auth is human")
        self.assertIn("every cookie in", result["error"])
        self.assertIn("expired, the last at 2023-11-14T22:13:20Z", result["error"])

    def test_a_failed_assertion_is_assert_and_breaks_trust(self):
        code, result, trust = self.run_json("assert")
        self.assertEqual((code, result["status"], result["class"], trust),
                         (1, "failed", "assert", "broken"))
        self.assertEqual(result["next"], "compare assertion .out.equals with the live page "
                                         "before you patch the map")
        self.assertEqual(result["trust_change"], "verified -> broken")


class FinishWaitingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self.tmp.name)
        self.root = make_tree(base)
        self.runs = base / "runs"
        self.env = {**os.environ, "SITEMAPPER_INSTANCE": INSTANCE}
        self.addCleanup(self.tmp.cleanup)

    def run_py(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(RUN_PY), *args, "--root", str(self.root),
                               "--runs", str(self.runs)],
                              env=self.env, capture_output=True, text=True, timeout=60)

    def waiting(self) -> str:
        proc = self.run_py("person", "--record")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return index_lines(self.runs)[-1]["run_id"]

    def finish(self, run_id: str, status: str, by: str = "BEB") -> subprocess.CompletedProcess:
        return self.run_py("--finish", run_id, "--status", status, "--by", by, "--json")

    def test_an_approval_ends_the_run_passed_with_who_answered(self):
        run_id = self.waiting()
        proc = self.finish(run_id, "passed")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        done = json.loads(proc.stdout)
        self.assertEqual((done["status"], done["answered_by"], done["changed"]),
                         ("passed", "BEB", True))

        statuses = [line["status"] for line in index_lines(self.runs)]
        self.assertEqual(statuses, ["running", "waiting", "passed"])
        last = index_lines(self.runs)[-1]
        self.assertEqual((last["answered_by"], last["answered_at"], last["finished_at"]),
                         ("BEB", done["answered_at"], done["answered_at"]))
        self.assertEqual(last["headline"], "passed · approved by BEB")
        run = run_yaml(self.runs, run_id)
        self.assertEqual((run["status"], run["answered_by"]), ("passed", "BEB"))
        self.assertNotIn("waiting_for", run)
        self.assertNotIn("error", run)

    def test_a_rejection_ends_the_run_failed_naming_who_rejected_it(self):
        run_id = self.waiting()
        self.assertEqual(self.finish(run_id, "failed").returncode, 0)
        run = run_yaml(self.runs, run_id)
        self.assertEqual((run["status"], run["error"], run["headline"]),
                         ("failed", "rejected by BEB", "failed · rejected by BEB"))

    def test_finishing_again_with_the_same_answer_changes_nothing(self):
        run_id = self.waiting()
        self.finish(run_id, "passed")
        again = self.finish(run_id, "passed")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertFalse(json.loads(again.stdout)["changed"])
        self.assertEqual(len(index_lines(self.runs)), 3)

    def test_a_run_that_is_not_waiting_is_refused(self):
        run_id = self.waiting()
        self.finish(run_id, "passed")
        other = self.finish(run_id, "failed")
        self.assertEqual(other.returncode, 2)
        self.assertIn(f"run '{run_id}' is passed, not waiting", other.stderr)
        quick = self.run_py("quick", "--record")
        self.assertEqual(quick.returncode, 0, quick.stderr)
        refused = self.finish(index_lines(self.runs)[-1]["run_id"], "passed")
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(len(index_lines(self.runs)), 5)

    def test_an_unknown_run_is_refused(self):
        proc = self.finish("nap.2026-01-01T000000.000Z.-.TEST-PC.abcd", "passed")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no run 'nap.2026-01-01T000000.000Z.-.TEST-PC.abcd' in the index of "
                      "TEST-PC", proc.stderr)

    def test_a_swept_run_gets_the_index_line_alone(self):
        run_id = self.waiting()
        shutil.rmtree(self.runs / "SiteMapper" / "fixture" / run_id)
        self.assertEqual(self.finish(run_id, "failed").returncode, 0)
        last = index_lines(self.runs)[-1]
        self.assertEqual((last["status"], last["answered_by"], last["owner"]),
                         ("failed", "BEB", "fixture"))
        self.assertFalse((self.runs / "SiteMapper" / "fixture" / run_id).exists())


class FinishRaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.runs = Path(self.tmp.name) / "runs"
        self.addCleanup(self.tmp.cleanup)
        sys.path.insert(0, str(RUN_PY.parent))
        self.addCleanup(sys.path.remove, str(RUN_PY.parent))
        os.environ["SITEMAPPER_INSTANCE"] = INSTANCE
        self.addCleanup(os.environ.pop, "SITEMAPPER_INSTANCE")
        import run

        self.run = run

    def waiting(self, n: int) -> str:
        run_id = f"person.2026-10-20T2000{n:02d}.000Z.-.{INSTANCE}.abcd"
        folder = self.runs / "SiteMapper" / "fixture" / run_id
        folder.mkdir(parents=True)
        self.run.write_record(self.runs, INSTANCE, run_id, folder, {
            "lib": "SiteMapper", "owner": "fixture", "workflow": "person", "tier": "-",
            "instance": INSTANCE, "started_at": "2026-10-20T20:00:00.000Z",
            "finished_at": "2026-10-20T20:00:01.000Z", "status": "waiting", "keep": "1d",
            "waiting_for": {"step": 1, "label": "a person approves", "reason": ""},
            "files": ["run.yaml"]})
        return run_id

    def test_two_different_answers_at_once_finish_the_run_exactly_once(self):
        for n in range(20):
            run_id = self.waiting(n)
            outcomes: dict[str, object] = {}
            start = threading.Barrier(2)

            def answer(status: str, by: str):
                start.wait()
                try:
                    outcomes[status] = self.run.finish_waiting(self.runs, run_id, status, by)
                except self.run.RunError as exc:
                    outcomes[status] = exc

            threads = [threading.Thread(target=answer, args=a) for a in
                       (("passed", "A"), ("failed", "B"))]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)

            won = [s for s, o in outcomes.items() if isinstance(o, dict)]
            self.assertEqual(len(won), 1, outcomes)
            lost = next(s for s in outcomes if s not in won)
            self.assertIn("not waiting", str(outcomes[lost]))
            ended = [line for line in index_lines(self.runs)
                     if line["run_id"] == run_id and line["status"] != "waiting"]
            self.assertEqual([line["status"] for line in ended], won)
            self.assertEqual(run_yaml(self.runs, run_id)["status"], won[0])

if __name__ == "__main__":
    unittest.main()
