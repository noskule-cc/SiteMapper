import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FRAMEWORK = SCRIPTS.parent

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

    async def test_lists_the_four_tools_and_one_run_tool_per_runnable_workflow(self):
        [listed] = await self.session(lambda s: s.list_tools())
        tools = {t["name"]: (t["annotations"]["readOnlyHint"],
                             t["annotations"]["destructiveHint"], t["_meta"])
                 for t in (tool.model_dump(by_alias=True) for tool in listed.tools)}
        self.assertEqual(tools, {
            "list_workflows": (True, False, None),
            "describe_workflow": (True, False, None),
            "preflight": (True, False, None),
            "run_workflow": (False, True, None),
            "run-edit": (False, False, {"teamos/lock": "lab/-"}),
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
             ("nap", "deterministic", "read-only", "run-nap"),
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

    async def test_an_ask_without_consent_starts_nothing(self):
        res, _ = await self.call("run-edit")
        self.assertEqual((res.structured_content["status"],
                          res.structured_content["needs_consent"]),
                         ("needs-consent", ["write"]))
        self.assertFalse(self.runs.exists())

    async def test_one_run_consent_answers_the_ask(self):
        res, _ = await self.call("run-edit", consent=["write"])
        self.assertEqual(res.structured_content["status"], "passed")

    async def test_a_deny_starts_nothing(self):
        res, _ = await self.call("run-wipe", consent=["destructive"])
        self.assertEqual(res.structured_content["status"], "denied")
        self.assertFalse(self.runs.exists())

    async def test_a_missing_parameter_is_a_tool_error_naming_it(self):
        res, _ = await self.call("run-nap")
        self.assertEqual((res.is_error, res.content[0].text),
                         (True, "Error executing tool run-nap: required parameter 'size' "
                                "missing — pass --param size=..."))


if __name__ == "__main__":
    unittest.main()
