"""SiteMapper's workflows as an MCP server over stdio (docs/interface.md).

    python scripts/mcp_server.py [--root PATH] [--projects PATH] [--runs PATH]

                              [--run-timeout SECONDS]

Tools: list_workflows, describe_workflow, preflight, run_workflow and finish_run, plus one
run-<workflow> tool per deterministic workflow whose sites are fixed, whose
hints carry that workflow's effect and whose `_meta` carries its lock key. A
run is `run.py <workflow> --json --record --trigger ui` in a child process, so
the permission gate and the run record are the runner's own.
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
RUN_TIMEOUT_S = 30 * 60
DRAIN_S = 5
TAIL_LINES = 10
HINTS = {
    "read-only": ToolAnnotations(readOnlyHint=True, destructiveHint=False),
    "mutating": ToolAnnotations(readOnlyHint=False, destructiveHint=False),
    "destructive": ToolAnnotations(readOnlyHint=False, destructiveHint=True),
}
LOCK_KEY = "teamos/lock"

Consent = Literal["write", "destructive", "auth"]


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    import win32api
    import win32con
    import win32job

    PROCESS_SUSPEND_RESUME = 0x0800
    NtResumeProcess = ctypes.WinDLL("ntdll").NtResumeProcess
    NtResumeProcess.argtypes = [wintypes.HANDLE]
    NtResumeProcess.restype = ctypes.c_long

    def contain(pid: int):
        """A job that kills the run and everything it started (Chrome, scripts)
        when its handle closes, which this server's exit also does. The child
        starts suspended so nothing it spawns can escape before it joins."""
        job = win32job.CreateJobObject(None, "")
        try:
            info = win32job.QueryInformationJobObject(
                job, win32job.JobObjectExtendedLimitInformation)
            info["BasicLimitInformation"]["LimitFlags"] |= (
                win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
            win32job.SetInformationJobObject(
                job, win32job.JobObjectExtendedLimitInformation, info)
            handle = win32api.OpenProcess(
                win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE | PROCESS_SUSPEND_RESUME,
                False, pid)
            try:
                win32job.AssignProcessToJobObject(job, handle)
                status = NtResumeProcess(int(handle))
                if status != 0:
                    raise OSError(f"NtResumeProcess returned NTSTATUS 0x{status & 0xFFFFFFFF:08X}")
            finally:
                win32api.CloseHandle(handle)
        except BaseException:
            win32api.CloseHandle(job)
            raise
        return job

    def end(pid: int, job) -> None:
        win32api.CloseHandle(job)

    CREATE_SUSPENDED = 0x00000004
    SPAWN = {"creationflags": subprocess.CREATE_NO_WINDOW | CREATE_SUSPENDED}
else:
    import signal

    def contain(pid: int):
        return None

    def end(pid: int, job) -> None:
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    SPAWN = {"start_new_session": True}


@dataclasses.dataclass(frozen=True)
class Tree:
    root: Path
    projects: Path
    runs: Path
    run_timeout_s: float = RUN_TIMEOUT_S

    def preflight(self, name: str, params: dict[str, str], persona: str | None,
                  consent: list[str]) -> run.Preflight:
        _, data, owner = run.find_workflow(self.root, self.projects, name)
        workflow = data.get("workflow", {})
        declared = [p["name"] for p in workflow.get("parameters") or []]
        unknown = sorted(set(params) - set(declared))
        if unknown:
            raise run.RunError(f"'{name}' declares no parameter {', '.join(unknown)}; "
                               f"it takes: {', '.join(declared) or 'none'}")
        return run.preflight(self.root, workflow, owner, params, persona, frozenset(consent))

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


class RunProtocol(asyncio.SubprocessProtocol):
    """Collects stdout and queues stderr lines. `exited` resolves when run.py
    exits, even while a process it started still holds a pipe open."""

    def __init__(self):
        loop = asyncio.get_running_loop()
        self.exited = loop.create_future()
        self.stdout = bytearray()
        self.lines: asyncio.Queue[str | None] = asyncio.Queue()
        self._pending = b""

    def pipe_data_received(self, fd: int, data: bytes):
        if fd == 1:
            self.stdout += data
            return
        *lines, self._pending = (self._pending + data).split(b"\n")
        for raw in lines:
            self.lines.put_nowait(raw.decode("utf-8", "replace").rstrip())

    def process_exited(self):
        if not self.exited.done():
            self.exited.set_result(None)

    def connection_lost(self, exc):
        if self._pending.strip():
            self.lines.put_nowait(self._pending.decode("utf-8", "replace").rstrip())
        self.lines.put_nowait(None)


def fixed_sites(workflow: dict) -> bool:
    refs = [workflow.get("site"), *(workflow.get("sites") or []),
            *(step.get("site") for step in tree.steps_of(workflow))]
    return not workflow.get("tiers") and not any("$" in str(r) for r in refs if r)


def tail(messages: list[str]) -> str:
    return "\n".join(m for m in messages[-TAIL_LINES:] if m)


async def start_run(tree_: Tree, name: str, params: dict[str, str], persona: str | None,
                    consent: list[str], ctx: Context,
                    timeout_s: float | None = None) -> dict[str, Any]:
    if timeout_s is not None and timeout_s <= 0:
        raise ToolError(f"timeout_s must be more than 0, got {timeout_s:g}")
    try:
        pre = tree_.preflight(name, params, persona, consent)
    except run.RunError as exc:
        raise ToolError(str(exc)) from exc
    if pre.outcome == "deny":
        return {"status": "denied", "class": "refused", "next": run.next_step("refused", name),
                "preflight": dataclasses.asdict(pre)}
    if pre.needs_consent:
        return {"status": "needs-consent", "class": "refused",
                "next": f"call again with consent {pre.needs_consent} to run {name} this once",
                "needs_consent": pre.needs_consent, "preflight": dataclasses.asdict(pre)}

    transport, child = await asyncio.get_running_loop().subprocess_exec(
        RunProtocol, *tree_.command(name, params, persona, pre),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}, **SPAWN)
    pid = transport.get_pid()
    try:
        job = contain(pid)
    except Exception as exc:
        transport.kill()
        await asyncio.wait([child.exited], timeout=DRAIN_S)
        transport.close()
        raise ToolError(f"run.py could not be contained, so it was stopped: {exc}") from exc
    transport.get_pipe_transport(0).close()

    record, messages = None, []

    async def pump_stderr():
        nonlocal record
        while (line := await child.lines.get()) is not None:
            step = STEP_LINE.match(line)
            if step:
                await ctx.report_progress(int(step[1]), int(step[2]), step[3])
            elif line.startswith("record: "):
                record = Path(line.removeprefix("record: "))
            else:
                messages.append(line.removeprefix("error: ")[:2000])

    pump = asyncio.ensure_future(pump_stderr())
    limit = tree_.run_timeout_s if timeout_s is None else timeout_s
    ended = False
    try:
        try:
            async with asyncio.timeout(limit):
                await child.exited
        except TimeoutError:
            raise ToolError(f"'{name}' ran longer than {limit:g} s and was stopped; "
                            f"last output:\n{tail(messages)}") from None
        end(pid, job)
        ended = True
        await asyncio.wait([pump], timeout=DRAIN_S)
    finally:
        pump.cancel()
        if not ended:
            end(pid, job)
        transport.close()
    out = bytes(child.stdout)
    try:
        result = json.loads(out)
        status = result["status"]
    except (ValueError, TypeError, KeyError) as exc:
        reason = f" ({type(exc).__name__})" if out.strip() else ""
        raise ToolError(f"run.py exited {transport.get_returncode()} without a result{reason}; "
                        f"last output:\n{tail(messages)}") from None
    return {"run_id": record.name if record else None, "status": status,
            "class": result.get("class"), "next": result.get("next") or "",
            "waiting_for": result.get("waiting_for"), "error": result.get("error") or "",
            "record": str(record) if record else None}


def runner_for(tree_: Tree, name: str):
    async def run_this(ctx: Context, params: dict[str, str] | None = None,
                       persona: str | None = None, consent: list[Consent] | None = None,
                       timeout_s: float | None = None) -> dict[str, Any]:
        return await start_run(tree_, name, params or {}, persona, consent or [], ctx,
                               timeout_s)
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
                           persona: str | None = None, consent: list[Consent] | None = None,
                           timeout_s: float | None = None) -> dict[str, Any]:
        """Run a workflow and return its run_id, status, class, next and waiting_for.

        `consent` answers an `ask` for this run only. Without it an ask returns
        status needs-consent and starts nothing; a deny returns status denied.
        Progress arrives per step. The lock key is the preflight's. A run
        longer than `timeout_s` (default: the server's --run-timeout) is stopped."""
        return await start_run(tree_, name, params or {}, persona, consent or [], ctx,
                               timeout_s)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                             idempotentHint=True), structured_output=True)
    def finish_run(run_id: str, status: Literal["passed", "failed"], by: str) -> dict[str, Any]:
        """End a waiting run at a person's answer: passed after an approval, failed after
        a rejection, with who answered. Finishing it again with the same answer changes
        nothing; a run that is not waiting is refused."""
        try:
            return run.finish_waiting(tree_.runs, run_id, status, by)
        except run.RunError as exc:
            raise ToolError(str(exc)) from exc

    for path, owner, wf in workflows:
        name = wf.get("name") or path.stem
        if (wf.get("mode") != "deterministic" or wf.get("effect") not in HINTS
                or not fixed_sites(wf)):
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
    ap.add_argument("--run-timeout", type=float, default=RUN_TIMEOUT_S,
                    help=f"seconds before a run is stopped (default: {RUN_TIMEOUT_S})")
    args = ap.parse_args(argv)
    if args.run_timeout <= 0:
        ap.error(f"--run-timeout must be more than 0, got {args.run_timeout:g}")
    root = Path(args.root).resolve() if args.root else run.FRAMEWORK_ROOT
    build(Tree(root, Path(tree.projects_root(str(root), args.projects)),
               Path(tree.runs_root(str(root), args.runs)), args.run_timeout)).run("stdio")


if __name__ == "__main__":
    main()
