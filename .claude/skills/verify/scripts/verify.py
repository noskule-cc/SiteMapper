"""Drive a disposable SiteMapper dashboard (scripts/serve.py) in a real browser.

Run from the SiteMapper checkout:
    python .claude/skills/verify/scripts/verify.py <command> ...

Commands:
    up [--from <map root>] [--port N]   copy the maps into scratch, serve the dashboard
    doctor                              is the running copy worth driving?
    drive <step> [<step> ...]           browser steps, see STEPS
    down                                stop the server, delete the copy, keep the evidence
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

FRAMEWORK = Path(__file__).resolve().parents[4]
BASE = Path(tempfile.gettempdir()) / "sitemapper-verify"
STATE = BASE / "state.json"
# .runner holds saved logins and screenshots; runs is history. A copy needs neither.
SKIP = shutil.ignore_patterns(".git", ".runner", "runs", "*.log", "*.png", "*.xlsx", "*.zip")
COPIED = ("sites", "apps", "projects", "schema", "config.yaml")
STEPS = """steps, applied in order:
    goto:<path>            open a dashboard path, e.g. goto:/  or a full URL, e.g. file:///...
    within:<name>          scope later steps to the process row with a link of exactly this
                           name (a workflow or script), else to the card (article) whose
                           heading contains it; within: alone scopes back to the whole page
    click:<role>:<name>    click by ARIA role and exact accessible name, e.g. click:button:workflow
    fill:<label>:<text>    type into the first field whose label or placeholder contains <label>
    expect:<text>          fail unless the page shows this text within 5 s
    await:<text>           the same, but waits up to 10 min: for the result of a run
    absent:<text>          fail if the page shows this text
    wait:<seconds>         wait, e.g. for a run the page started
    shot:<label>           save <label>.png, <label>.aria.yaml and <label>.txt as evidence

A click on a button whose name contains "run" is refused unless the copy was made
from the framework checkout: only the demo site's workflows may run from here."""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            errors="replace",
        ).stdout
        return f'"{pid}"' in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _answers(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/meta", timeout=5) as r:
            return r.status == 200 and "tree" in json.loads(r.read())
    except (OSError, ValueError):
        return False


def _snapshot(source: Path) -> dict[str, float]:
    return {
        str(p): p.stat().st_mtime
        for top in ("runs", ".runner", *COPIED)
        for p in (source / top).rglob("*")
        if p.is_file()
    }


def _load() -> dict:
    if not STATE.exists():
        sys.exit("no verification instance: run `up` first")
    return json.loads(STATE.read_text(encoding="utf-8"))


def up(args: argparse.Namespace) -> None:
    if STATE.exists() and _alive(_load()["pid"]):
        sys.exit(f"a verification server already runs ({STATE}); run `down` first")
    source = (args.source or FRAMEWORK).resolve()
    if not (source / "sites").is_dir():
        sys.exit(f"{source} has no sites/: not a map root")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    copy, evidence = BASE / stamp / "maps", BASE / "evidence" / stamp
    evidence.mkdir(parents=True)
    copy.mkdir(parents=True)
    for name in COPIED:
        src = source / name
        if src.is_dir():
            shutil.copytree(src, copy / name, ignore=SKIP)
        elif src.is_file():
            shutil.copy2(src, copy / name)
    # Without these the server would resolve them beside the copy, outside it.
    (copy / "projects").mkdir(exist_ok=True)
    (copy / "runs").mkdir()
    port = args.port or _free_port()
    log = (evidence / "server.log").open("w", encoding="utf-8")
    flags = (
        subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if os.name == "nt" else 0
    )
    cmd = [sys.executable, str(FRAMEWORK / "scripts" / "serve.py"), "--root", str(copy)]
    proc = subprocess.Popen(
        [*cmd, "--port", str(port)],
        cwd=FRAMEWORK,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )
    state = {
        "pid": proc.pid,
        "port": port,
        "copy": str(copy),
        "source": str(source),
        "framework": source == FRAMEWORK,
        "evidence": str(evidence),
        "source_state": _snapshot(source),
    }
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    for _ in range(60):
        if _answers(port):
            print(f"ready: http://127.0.0.1:{port}/  copy {copy}  evidence {evidence}")
            return
        if proc.poll() is not None:
            sys.exit(f"server exited with {proc.returncode}; see {evidence / 'server.log'}")
        time.sleep(1)
    sys.exit(f"server did not answer on port {port} within 60 s; see {evidence / 'server.log'}")


def doctor(_: argparse.Namespace) -> None:
    s = _load()
    copy = Path(s["copy"])
    meta = {}
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{s['port']}/api/meta", timeout=5) as r:
            meta = json.loads(r.read())
    except (OSError, ValueError):
        pass
    checks = {
        f"process {s['pid']} runs": _alive(s["pid"]),
        f"port {s['port']} serves the dashboard API": bool(meta),
        "the server's tree is the scratch copy": meta.get("tree") == copy.name,
        "runs land inside the copy": (copy / "runs").is_dir(),
        "the copy holds no saved logins (.runner)": not (copy / ".runner" / "state").exists(),
    }
    for name, ok in checks.items():
        print(f"{'OK  ' if ok else 'FAIL'} {name}")
    runs = "allowed (demo site only)" if s["framework"] else "REFUSED (copy of a map repository)"
    print(f"Run buttons: {runs}")
    print(f"url http://127.0.0.1:{s['port']}/  evidence {s['evidence']}")
    sys.exit(0 if all(checks.values()) else 1)


def drive(args: argparse.Namespace) -> None:
    from playwright.sync_api import Error, sync_playwright

    s = _load()
    url, evidence = f"http://127.0.0.1:{s['port']}", Path(s["evidence"])
    failed = False
    with sync_playwright() as p:
        browser = None
        for channel in ("chrome", "msedge", None):
            try:
                browser = p.chromium.launch(channel=channel) if channel else p.chromium.launch()
                break
            except Error:
                continue
        if browser is None:
            sys.exit("no browser: install Chrome or Edge, or run `playwright install chromium`")
        page = browser.new_page(locale="en-US", viewport={"width": 1280, "height": 900})
        page.set_default_timeout(15_000)
        scope = page
        for step in args.steps:
            kind, _, rest = step.partition(":")
            try:
                if kind == "goto":
                    page.goto(rest if "://" in rest else url + rest)
                    page.wait_for_load_state("networkidle")
                    ok = True
                elif kind == "within":
                    row = page.locator(".proc").filter(
                        has=page.get_by_role("link", name=rest, exact=True)
                    )
                    card = page.get_by_role("article").filter(
                        has=page.get_by_role("heading", name=rest)
                    )
                    scope = (row if row.count() else card).first if rest else page
                    ok = scope.count() > 0 if rest else True
                elif kind == "click":
                    role, _, name = rest.partition(":")
                    if role == "button" and "run" in name.lower() and not s["framework"]:
                        sys.exit(f"refused {step!r}: the copy is of {s['source']}, not the framework")
                    scope.get_by_role(role, name=name, exact=True).first.click()
                    page.wait_for_load_state("networkidle")
                    ok = True
                elif kind == "fill":
                    label, _, text = rest.partition(":")
                    field = scope.get_by_label(label).or_(scope.get_by_placeholder(label))
                    field.first.fill(text)
                    ok = True
                elif kind in ("expect", "absent", "await"):
                    try:
                        scope.get_by_text(rest).first.wait_for(
                            timeout=600_000 if kind == "await" else 5000
                        )
                        shown = True
                    except Error:
                        shown = False
                    ok = not shown if kind == "absent" else shown
                elif kind == "wait":
                    page.wait_for_timeout(float(rest) * 1000)
                    ok = True
                elif kind == "shot":
                    page.screenshot(path=evidence / f"{rest}.png", full_page=True)
                    (evidence / f"{rest}.aria.yaml").write_text(
                        page.locator("body").aria_snapshot(), encoding="utf-8"
                    )
                    (evidence / f"{rest}.txt").write_text(
                        f"{page.url}\n\n{page.inner_text('body')}", encoding="utf-8"
                    )
                    ok = True
                else:
                    sys.exit(f"unknown step {step!r}\n{STEPS}")
            except Error as e:
                print(f"FAIL {step}: {str(e).splitlines()[0]}")
                failed = True
                break
            failed |= not ok
            print(f"{'PASS' if ok else 'FAIL'} {step}")
        browser.close()
    print(f"evidence {evidence}")
    sys.exit(1 if failed else 0)


def down(_: argparse.Namespace) -> None:
    s = _load()
    if _alive(s["pid"]):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(s["pid"]), "/T", "/F"], capture_output=True)
        else:
            os.kill(s["pid"], 15)
    for _ in range(10):
        if not _alive(s["pid"]):
            break
        time.sleep(0.5)
    shutil.rmtree(Path(s["copy"]).parent, ignore_errors=True)
    touched = _snapshot(Path(s["source"])) != s["source_state"]
    STATE.unlink()
    print(f"stopped {s['pid']}, removed {Path(s['copy']).parent}")
    print(f"source maps, runs and .runner {'CHANGED during the run' if touched else 'unchanged'}")
    print(f"evidence kept in {s['evidence']}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=STEPS, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    p_up = sub.add_parser("up")
    p_up.add_argument("--from", dest="source", type=Path)
    p_up.add_argument("--port", type=int)
    sub.add_parser("doctor")
    p_drive = sub.add_parser(
        "drive", epilog=STEPS, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p_drive.add_argument("steps", nargs="+")
    sub.add_parser("down")
    args = parser.parse_args()
    {"up": up, "doctor": doctor, "drive": drive, "down": down}[args.command](args)


if __name__ == "__main__":
    main()
