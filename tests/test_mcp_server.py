import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FRAMEWORK = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    ClientSession = None

SLOW = """\
import sys, time
time.sleep(float(sys.argv[1]))
print("slept")
"""

SITE = """\
site:
  name: lab
  base_url: https://lab.invalid
  scripts:
    - name: slow.py
"""


def workflow(name: str, effect: str, steps: str, extra: str = "") -> str:
    return (f"workflow:\n  name: {name}\n  description: |\n    {name} for the server test\n"
            f"    second line\n  site: lab\n  mode: deterministic\n  effect: {effect}\n"
            f"{extra}  steps:\n{steps}")


WAIT = ("    - action: script\n      script: slow.py\n      value: \"0\"\n"
        "      capture: slept\n      description: Sleep a moment\n"
        "    - action: human\n      kind: approve\n      description: |\n"
        "        Check the nap\n        in detail\n      reason: a person looks\n")
WRITE = "    - action: script\n      script: slow.py\n      value: \"0\"\n"
HOLD = "    - action: script\n      script: slow.py\n      value: \"60\"\n"
ROAM = ("    - action: script\n      site: $where\n      script: slow.py\n      value: \"0\"\n"
        "      capture: slept\n")


def make_tree(base: Path) -> Path:
    root = base / "SiteMapper"
    shutil.copytree(FRAMEWORK / "sites" / "sitemapper-demo", root / "sites" / "sitemapper-demo")
    (root / "projects").mkdir()
    lab = root / "sites" / "lab"
    (lab / "workflows").mkdir(parents=True)
    (lab / "scripts").mkdir()
    (lab / "site.yaml").write_text(SITE, encoding="utf-8")
    (lab / "scripts" / "slow.py").write_text(SLOW, encoding="utf-8")
    flows = {
        "nap": workflow("nap", "read-only", WAIT, "  parameters:\n    - name: size\n"
                        "      type: select\n      options: [small, big]\n      required: true\n"
                        "      description: How long\n    - name: note\n      type: text\n"
                        "      default: none\n"),
        "edit": workflow("edit", "mutating", WRITE),
        "wipe": workflow("wipe", "destructive", WRITE),
        "think": workflow("think", "read-only", WRITE).replace("deterministic", "agentic"),
        "hold": workflow("hold", "read-only", HOLD),
        "roam": workflow("roam", "read-only", ROAM,
                         "  parameters:\n    - name: where\n      type: text\n"
                         "      required: true\n"),
    }
    for name, text in flows.items():
        (lab / "workflows" / f"{name}.yaml").write_text(text, encoding="utf-8")
    return root


@unittest.skipIf(ClientSession is None, "mcp is not installed (pip install mcp)")
class McpServerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = make_tree(Path(self.tmp.name))
        self.runs = Path(self.tmp.name) / "runs"

    async def session(self, *calls):
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(SCRIPTS / "mcp_server.py"), "--root", str(self.root),
                  "--runs", str(self.runs)])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            return [await call(s) for call in calls]

    async def call(self, tool: str, **args):
        progress = []

        async def on_progress(value, total, message):
            progress.append((value, total, message))

        [res] = await self.session(lambda s: s.call_tool(
            tool, args, read_timeout_seconds=300, progress_callback=on_progress))
        return res, progress

    async def test_lists_the_five_tools_and_one_run_tool_per_runnable_workflow(self):
        [listed] = await self.session(lambda s: s.list_tools())
        tools = {t["name"]: (t["annotations"]["readOnlyHint"],
                             t["annotations"]["destructiveHint"], t["_meta"])
                 for t in (tool.model_dump(by_alias=True) for tool in listed.tools)}
        self.assertEqual(tools, {
            "list_workflows": (True, False, None),
            "describe_workflow": (True, False, None),
            "preflight": (True, False, None),
            "run_workflow": (False, True, None),
            "finish_run": (False, False, None),
            "run-edit": (False, False, {"teamos/lock": "lab/-"}),
            "run-hold": (True, False, {"teamos/lock": "lab/-"}),
            "run-nap": (True, False, {"teamos/lock": "lab/-"}),
            "run-wipe": (False, True, {"teamos/lock": "lab/-"}),
            "run-search-issues": (True, False, {"teamos/lock": "sitemapper-demo/-"}),
        })

    async def test_list_workflows_names_every_workflow_of_the_tree(self):
        res, _ = await self.call("list_workflows")
        self.assertEqual(
            [(w["name"], w["mode"], w["effect"], w["tool"])
             for w in res.structured_content["result"]],
            [("edit", "deterministic", "mutating", "run-edit"),
             ("hold", "deterministic", "read-only", "run-hold"),
             ("nap", "deterministic", "read-only", "run-nap"),
             ("roam", "deterministic", "read-only", None),
             ("think", "agentic", "read-only", None),
             ("wipe", "deterministic", "destructive", "run-wipe"),
             ("search-issues", "deterministic", "read-only", "run-search-issues"),
             ("smart-issue", "agentic", "mutating", None)])

    async def test_describe_gives_the_parameters_schema_effect_and_step_labels(self):
        res, _ = await self.call("describe_workflow", name="nap")
        self.assertEqual(res.structured_content, {
            "name": "nap", "owner": "lab",
            "description": "nap for the server test\nsecond line",
            "mode": "deterministic", "effect": "read-only",
            "parameters": {"type": "object", "required": ["size"], "properties": {
                "size": {"type": "string", "description": "How long",
                         "enum": ["small", "big"]},
                "note": {"type": "string", "default": "none"}}},
            "steps": [
                {"number": 1, "phase": "steps", "action": "script", "label": "Sleep a moment"},
                {"number": 2, "phase": "steps", "action": "human", "label": "Check the nap"}],
        })

    async def test_describe_search_issues(self):
        res, _ = await self.call("describe_workflow", name="search-issues")
        described = res.structured_content
        self.assertEqual((described["effect"], described["mode"], described["parameters"],
                          len(described["steps"]), described["steps"][0]),
                         ("read-only", "deterministic",
                          {"type": "object", "properties": {}, "required": []}, 10,
                          {"number": 1, "phase": "steps", "action": "navigate",
                           "label": "Open the issues list (deep-link via url_pattern)"}))

    async def test_runs_search_issues_to_passed(self):
        res, progress = await self.call("run-search-issues")
        self.assertEqual((res.is_error, res.structured_content["status"], len(progress)),
                         (False, "passed", 10), res.content)

    async def test_a_run_stops_at_the_person_step_and_is_recorded_as_ui(self):
        res, progress = await self.call("run_workflow", name="nap", params={"size": "small"})
        out = res.structured_content
        self.assertEqual((out["status"], out["waiting_for"], out["error"]),
                         ("waiting", {"step": 2, "label": "Check the nap\nin detail\n",
                                      "reason": "a person looks"}, ""))
        self.assertEqual(progress, [(1.0, 2.0, "Sleep a moment"), (2.0, 2.0, "Check the nap")])
        lines = [json.loads(line) for line in
                 next((self.runs / "SiteMapper").glob("index.*.jsonl")).read_text(
                     encoding="utf-8").splitlines()]
        self.assertEqual([(line["run_id"], line["status"], line["trigger"]) for line in lines],
                         [(out["run_id"], "running", "ui"), (out["run_id"], "waiting", "ui")])

    async def test_finish_run_ends_a_waiting_run_once(self):
        res, _ = await self.call("run_workflow", name="nap", params={"size": "small"})
        run_id = res.structured_content["run_id"]
        approve = {"run_id": run_id, "status": "passed", "by": "BEB"}
        first, again, other = await self.session(
            lambda s: s.call_tool("finish_run", approve),
            lambda s: s.call_tool("finish_run", approve),
            lambda s: s.call_tool("finish_run", {**approve, "status": "failed"}),
        )
        self.assertEqual((first.structured_content["status"], first.structured_content["changed"],
                          again.structured_content["changed"]), ("passed", True, False))
        self.assertTrue(other.is_error)
        self.assertIn("is passed, not waiting", other.content[0].text)
        lines = [json.loads(line) for line in
                 next((self.runs / "SiteMapper").glob("index.*.jsonl")).read_text(
                     encoding="utf-8").splitlines()]
        self.assertEqual([(line["status"], line.get("answered_by")) for line in lines],
                         [("running", None), ("waiting", None), ("passed", "BEB")])

    async def test_an_ask_without_consent_starts_nothing(self):
        res, _ = await self.call("run-edit")
        out = res.structured_content
        self.assertEqual((out["status"], out["needs_consent"], out["class"], out["next"]),
                         ("needs-consent", ["write"], "refused",
                          "call again with consent write to run edit this once"))
        self.assertFalse(self.runs.exists())

    async def test_one_run_consent_answers_the_ask(self):
        res, _ = await self.call("run-edit", consent=["write"])
        self.assertEqual(res.structured_content["status"], "passed")

    async def test_a_deny_starts_nothing(self):
        res, _ = await self.call("run-wipe", consent=["destructive"])
        self.assertEqual(res.structured_content["status"], "denied")
        self.assertFalse(self.runs.exists())

    async def test_a_missing_parameter_is_an_input_result_naming_it(self):
        res, _ = await self.call("run-nap")
        out = res.structured_content
        self.assertEqual((res.is_error, out["status"], out["class"], out["next"], out["error"],
                          out["run_id"]),
                         (False, "error", "input", "run nap again with --param size=...",
                          "required parameter 'size' missing — pass --param size=...", None))

    async def test_a_workflow_whose_site_is_a_parameter_runs_through_run_workflow(self):
        res, _ = await self.call("run_workflow", name="roam", params={"where": "lab"})
        self.assertEqual(res.structured_content["status"], "passed", res.content)

    async def test_an_undeclared_parameter_is_refused_before_anything_starts(self):
        res, _ = await self.call("run-edit", params={"bogus": "1"}, consent=["write"])
        self.assertEqual((res.is_error, res.content[0].text),
                         (True, "Error executing tool run-edit: 'edit' declares no parameter "
                                "bogus; it takes: none"))
        self.assertFalse(self.runs.exists())

    async def test_a_run_past_its_timeout_is_stopped_with_a_named_error(self):
        started = time.perf_counter()
        res, _ = await self.call("run-hold", timeout_s=3)
        self.assertEqual((res.is_error, res.content[0].text.splitlines()[0]),
                         (True, "Error executing tool run-hold: 'hold' ran longer than 3 s "
                                "and was stopped; last output:"))
        self.assertLess(time.perf_counter() - started, 30)


class FakeContext:
    async def report_progress(self, value, total, message):
        pass


@unittest.skipIf(ClientSession is None, "mcp is not installed (pip install mcp)")
class StartRunTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import mcp_server
        self.server = mcp_server
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        root = make_tree(Path(self.tmp.name))
        self.pidfile = Path(self.tmp.name) / "grandchild.pid"
        test = self

        class FakeRunner(mcp_server.Tree):
            def command(self, name, params, persona, pre):
                return [sys.executable, "-c", test.child]

        self.tree = FakeRunner(root, root / "projects", Path(self.tmp.name) / "runs")

    async def start(self, child: str):
        self.child = child
        return await self.server.start_run(self.tree, "hold", {}, None, [], FakeContext())

    async def test_a_timed_out_run_logs_no_invalid_state_error(self):
        with self.assertNoLogs("asyncio", level="ERROR"):
            with self.assertRaises(self.server.ToolError):
                self.child = "import time; time.sleep(60)"
                await self.server.start_run(self.tree, "hold", {}, None, [], FakeContext(), 1)
            await asyncio.sleep(2)

    async def test_a_timeout_that_is_not_positive_is_refused(self):
        with self.assertRaises(self.server.ToolError) as caught:
            await self.server.start_run(self.tree, "hold", {}, None, [], FakeContext(), 0)
        self.assertEqual(str(caught.exception), "timeout_s must be more than 0, got 0")

    async def test_a_long_stderr_line_does_not_stop_the_run(self):
        out = await self.start(
            "import sys, json; sys.stderr.write('x' * 2_000_000 + chr(10)); "
            "print(json.dumps({'status': 'passed'}))")
        self.assertEqual(out["status"], "passed")

    async def test_the_class_and_next_step_reach_the_tool_result(self):
        out = await self.start(
            "import json; print(json.dumps({'status': 'error', 'class': 'drift', "
            "'next': '/repair hold', 'error': '[steps] gone'}))")
        self.assertEqual((out["status"], out["class"], out["next"], out["error"]),
                         ("error", "drift", "/repair hold", "[steps] gone"))
        self.assertIsNone(out["replay"])

    async def test_the_fixture_replay_reaches_the_tool_result(self):
        out = await self.start(
            "import json; print(json.dumps({'status': 'failed', 'class': 'input', "
            "'failure': {'replay': {'status': 'passed', 'inputs': {'term': 'known'}}}}))")
        self.assertEqual((out["class"], out["replay"]),
                         ("input", {"status": "passed", "inputs": {"term": "known"}}))

    async def test_output_that_is_not_json_is_a_named_error_with_the_last_lines(self):
        with self.assertRaises(self.server.ToolError) as caught:
            await self.start("import sys; print('oops', file=sys.stderr); print('not json')")
        self.assertEqual(str(caught.exception),
                         "run.py exited 0 without a result (JSONDecodeError); last output:\noops")

    async def test_a_result_without_status_is_a_named_error(self):
        with self.assertRaises(self.server.ToolError) as caught:
            await self.start("import json; print(json.dumps({'error': ''}))")
        self.assertEqual(str(caught.exception),
                         "run.py exited 0 without a result (KeyError); last output:\n")

    async def test_a_grandchild_holding_the_pipe_does_not_block_the_result(self):
        started = time.perf_counter()
        out = await self.start(
            "import subprocess, sys, json, pathlib; "
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
            f"pathlib.Path(r'{self.pidfile}').write_text(str(p.pid)); "
            "print(json.dumps({'status': 'passed'}), flush=True)")
        self.assertEqual(out["status"], "passed")
        self.assertLess(time.perf_counter() - started, 20)
        self.assertFalse(alive(int(self.pidfile.read_text())))

    @unittest.skipUnless(sys.platform == "win32", "the Job Object is Windows only")
    async def test_a_failed_resume_stops_the_child_and_closes_the_job(self):
        closed, pids = [], []
        real_close = self.server.win32api.CloseHandle
        real_contain = self.server.contain

        def spy_contain(pid):
            pids.append(pid)
            return real_contain(pid)

        def spy_close(handle):
            closed.append(handle)
            return real_close(handle)

        with (mock.patch.object(self.server, "NtResumeProcess", lambda handle: -1073741823),
              mock.patch.object(self.server.win32api, "CloseHandle", spy_close),
              mock.patch.object(self.server, "contain", spy_contain)):
            with self.assertRaises(self.server.ToolError) as caught:
                await self.start("print('never')")
        self.assertEqual(str(caught.exception),
                         "run.py could not be contained, so it was stopped: NtResumeProcess "
                         "returned NTSTATUS 0xC0000001")
        self.assertEqual(len(closed), 2)
        self.assertFalse(alive(pids[0]))

    @unittest.skipUnless(sys.platform == "win32", "the Job Object is Windows only")
    async def test_a_failed_job_assignment_stops_the_child(self):
        def refuse(job, handle):
            raise self.server.win32api.error(5, "AssignProcessToJobObject", "Access is denied.")

        with mock.patch.object(self.server.win32job, "AssignProcessToJobObject", refuse):
            with self.assertRaises(self.server.ToolError) as caught:
                await self.start("print('never')")
        self.assertEqual(str(caught.exception),
                         "run.py could not be contained, so it was stopped: (5, "
                         "'AssignProcessToJobObject', 'Access is denied.')")


def alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return code.value == 259
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


if __name__ == "__main__":
    unittest.main()
