"""SiteMapper's workflows as an MCP server over stdio (docs/interface.md).

    python scripts/mcp_server.py [--root PATH] [--projects PATH] [--runs PATH]

Tools: list_workflows, describe_workflow, preflight and run_workflow, plus one
run-<workflow> tool per deterministic workflow whose hints carry that
workflow's effect and whose `_meta` carries its lock key. A run is
`run.py <workflow> --json --record --trigger ui` in a child process, so the
permission gate and the run record are the runner's own.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa: E402
import tree  # noqa: E402

RUN_PY = Path(__file__).resolve().parent / "run.py"
STEP_LINE = re.compile(r"^step (\d+)/(\d+): (.*)$")
HINTS = {
    "read-only": ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    "mutating": ToolAnnotations(readOnlyHint=False, destructiveHint=False),
    "destructive": ToolAnnotations(readOnlyHint=False, destructiveHint=True),
}
LOCK_KEY = "teamos/lock"

Consent = Literal["write", "destructive", "auth"]


if sys.platform == "win32":
    import ctypes

    import win32api
    import win32con
    import win32job

    PROCESS_SUSPEND_RESUME = 0x0800

    def contain(proc: asyncio.subprocess.Process):
        """A job that kills the run and everything it started (Chrome, scripts)
        when its handle closes, which this server's exit also does. The child
        starts suspended so nothing it spawns can escape before it joins."""
        job = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        info["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, info)
        handle = win32api.OpenProcess(
            win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE | PROCESS_SUSPEND_RESUME,
            False, proc.pid)
        try:
            win32job.AssignProcessToJobObject(job, handle)
            ctypes.windll.ntdll.NtResumeProcess(int(handle))
        finally:
            win32api.CloseHandle(handle)
        return job

    def end(proc: asyncio.subprocess.Process, job) -> None:
        win32api.CloseHandle(job)

    CREATE_SUSPENDED = 0x00000004
    SPAWN = {"creationflags": subprocess.CREATE_NO_WINDOW | CREATE_SUSPENDED}
else:
    import signal

    def contain(proc: asyncio.subprocess.Process):
        return None

    def end(proc: asyncio.subprocess.Process, job) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    SPAWN = {"start_new_session": True}


@dataclasses.dataclass(frozen=True)
class Tree:
    root: Path
    projects: Path
    runs: Path

    def preflight(self, name: str, params: dict[str, str], persona: str | None,
                  consent: list[str]) -> run.Preflight:
        _, data, owner = run.find_workflow(self.root, self.projects, name)
        return run.preflight(self.root, data.get("workflow", {}), owner, params, persona,
                             frozenset(consent))

    def command(self, name: str, params: dict[str, str], persona: str | None,
                pre: run.Preflight) -> list[str]:
        cmd = [sys.executable, str(RUN_PY), name, "--json", "--record", "--trigger", "ui",
               "--root", str(self.root), "--projects", str(self.projects),
               "--runs", str(self.runs)]
        cmd += [arg for key, value in params.items() for arg in ("--param", f"{key}={value}")]
        if persona:
            cmd += ["--persona", persona]
        return cmd + [f"--yes-{cls}" for cls in pre.consent
                      if cls in pre.classes and pre.classes[cls].verdict == "ask"]


async def start_run(tree_: Tree, name: str, params: dict[str, str], persona: str | None,
                    consent: list[str], ctx: Context) -> dict[str, Any]:
    try:
        pre = tree_.preflight(name, params, persona, consent)
    except run.RunError as exc:
        raise ToolError(str(exc)) from exc
    if pre.outcome == "deny":
        return {"status": "denied", "preflight": dataclasses.asdict(pre)}
    if pre.needs_consent:
        return {"status": "needs-consent", "needs_consent": pre.needs_consent,
                "preflight": dataclasses.asdict(pre)}

    proc = await asyncio.create_subprocess_exec(
        *tree_.command(name, params, persona, pre),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **SPAWN)
    try:
        job = contain(proc)
    except BaseException:
        proc.kill()
        raise
    proc.stdin.close()
    stdout = asyncio.ensure_future(proc.stdout.read())
    try:
        record, messages = None, []
        async for raw in proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip()
            step = STEP_LINE.match(line)
            if step:
                await ctx.report_progress(int(step[1]), int(step[2]), step[3])
            elif line.startswith("record: "):
                record = Path(line.removeprefix("record: "))
            else:
                messages.append(line.removeprefix("error: "))
        out = await stdout
        await proc.wait()
    finally:
        stdout.cancel()
        end(proc, job)
        if proc.returncode is None:
            await proc.wait()
    if not out.strip():
        raise ToolError("\n".join(m for m in messages if m) or f"run.py exited {proc.returncode}")
    result = json.loads(out)
    return {"run_id": record.name if record else None, "status": result["status"],
            "waiting_for": result.get("waiting_for"), "error": result.get("error") or "",
            "record": str(record) if record else None}


def runner_for(tree_: Tree, name: str):
    async def run_this(ctx: Context, params: dict[str, str] | None = None,
                       persona: str | None = None,
                       consent: list[Consent] | None = None) -> dict[str, Any]:
        return await start_run(tree_, name, params or {}, persona, consent or [], ctx)
    return run_this


def build(tree_: Tree) -> MCPServer:
    server = MCPServer("sitemapper")
    reading = HINTS["read-only"]
    workflows = [(path, owner, (run.load_yaml(path) or {}).get("workflow") or {})
                 for path, owner in run.iter_workflows(tree_.root, tree_.projects)]

    run_tools: dict[str, str] = {}

    @server.tool(annotations=reading, structured_output=True)
    def list_workflows() -> list[dict[str, Any]]:
        """Every workflow of the tree: name, owner, sites, mode, effect, summary,
        and the run tool when it can run headless."""
        out = []
        for path, owner, wf in workflows:
            name = wf.get("name") or path.stem
            sites = [s for s in [wf.get("site"), *(wf.get("sites") or [])] if s]
            summary = str(wf.get("description") or "").strip().splitlines()
            out.append({"name": name, "owner": owner.name, "sites": sites,
                        "mode": wf.get("mode"), "effect": wf.get("effect"),
                        "summary": summary[0] if summary else "",
                        "tool": run_tools.get(name)})
        return out

    @server.tool(annotations=reading, structured_output=True)
    def describe_workflow(name: str) -> dict[str, Any]:
        """A workflow's parameters as a JSON schema, its effect, and its steps' labels."""
        try:
            return run.describe_workflow(tree_.root, tree_.projects, name)
        except run.RunError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(annotations=reading, structured_output=True)
    def preflight(name: str, params: dict[str, str] | None = None, persona: str | None = None,
                  consent: list[Consent] | None = None) -> dict[str, Any]:
        """What a run would be allowed to do: each action class's decision and
        rule, the outcome, needs_consent, and the lock key. Starts nothing."""
        try:
            return dataclasses.asdict(tree_.preflight(name, params or {}, persona, consent or []))
        except run.RunError as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(annotations=HINTS["destructive"], structured_output=True)
    async def run_workflow(name: str, ctx: Context, params: dict[str, str] | None = None,
                           persona: str | None = None,
                           consent: list[Consent] | None = None) -> dict[str, Any]:
        """Run a workflow and return its run_id, status and waiting_for.

        `consent` answers an `ask` for this run only. Without it an ask returns
        status needs-consent and starts nothing; a deny returns status denied.
        Progress arrives per step. The lock key is the preflight's."""
        return await start_run(tree_, name, params or {}, persona, consent or [], ctx)

    for path, owner, wf in workflows:
        name = wf.get("name") or path.stem
        if wf.get("mode") != "deterministic" or wf.get("effect") not in HINTS:
            continue
        try:
            lock = run.preflight(tree_.root, wf, owner, {}).lock_key
        except run.RunError as exc:
            print(f"mcp_server: no run tool for '{name}': {exc}", file=sys.stderr)
            continue

        run_tools[name] = f"run-{name}"
        server.add_tool(
            runner_for(tree_, name), name=run_tools[name],
            description=f"Run '{name}' ({wf['effect']}). Parameters: describe_workflow.",
            annotations=HINTS[wf["effect"]], meta={LOCK_KEY: lock}, structured_output=True)

    return server


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None, help="map repository (default: this repo)")
    ap.add_argument("--projects", default=None, help="the projects tree, when not inside --root")
    ap.add_argument("--runs", default=None, help="the runs store, when not inside --root")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else run.FRAMEWORK_ROOT
    build(Tree(root, Path(tree.projects_root(str(root), args.projects)),
               Path(tree.runs_root(str(root), args.runs)))).run("stdio")


if __name__ == "__main__":
    main()
