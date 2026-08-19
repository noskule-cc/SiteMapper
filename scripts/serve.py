"""Serve the dashboard live (#31).

    python scripts/serve.py [--root PATH] [--port 8765]

The same overview page, served from localhost with a thin JSON API — the page
detects the API and its run buttons become real. Opened as a plain file (or
as an Artifact, where CSP blocks fetch) the very same page stays static with
copy-paste commands: one page, two modes.

The permission gate stays server-side in Python — the browser is untrusted
UI. The button is the `ask` channel: a `read-only` run just runs; where
policy says `ask`, the server answers 409 with the question a TTY would have
asked, and the page's confirmation click sends consent for THAT run only.
`deny` is refused here no matter what the page sends. See docs/PERMISSIONS.md.

Bound to 127.0.0.1: one operator, no auth, never exposed. Stdlib only — the
server adds no dependencies (the runner it launches needs Playwright).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inventory  # noqa: E402
import overview  # noqa: E402
import run as runner  # noqa: E402

FRAMEWORK = Path(__file__).resolve().parent.parent
ROOT = FRAMEWORK
RUN_TIMEOUT_S = 900

TEXT_TYPES = {".html": "text/html", ".md": "text/plain", ".yaml": "text/plain",
              ".yml": "text/plain", ".txt": "text/plain", ".py": "text/plain",
              ".js": "text/plain", ".json": "application/json"}
BIN_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml",
             ".gif": "image/gif"}


def collect():
    inventory.set_root(str(ROOT))
    return {"sites": inventory.collect_sites(),
            "projects": inventory.collect_projects(),
            "workflows": inventory.collect_workflows()}


class Handler(BaseHTTPRequestHandler):
    server_version = "SiteMapperServe/1"

    # -- plumbing ----------------------------------------------------------
    def send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, code: int, obj):
        self.send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                  "application/json; charset=utf-8")

    def log_message(self, fmt, *args):  # quieter default log line
        sys.stderr.write("  " + (fmt % args) + "\n")

    # -- GET ---------------------------------------------------------------
    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/docs", "/docs/", "/docs/overview.html"):
            return self.page()
        if path == "/api/inventory":
            return self.send_json(200, collect())
        if path == "/api/meta":
            meta = {"tree": ROOT.name, "framework": ROOT == FRAMEWORK}
            if ROOT == FRAMEWORK:
                jobs = (FRAMEWORK / "docs" / "JOBS.md").read_text(encoding="utf-8")
                m = re.search(r"https://claude\.ai/code/artifact/[0-9a-f-]+", jobs)
                deployed = self.deployed_state()
                if m:  # the standing shareable URL — framework page only
                    meta["share_url"] = m.group(0)
                meta["deployed"] = deployed
                # Uniform chip data (#36): currency by the auto-deploy contract
                # (artifact tracks origin/main), not by publish hash.
                meta["artifact"] = {"url": m.group(0) if m else None,
                                    "published_at": None, "current": deployed}
            else:
                art = self.map_dashboard()
                if art["url"]:  # the map repo's own PRIVATE artifact (#34)
                    meta["share_url"] = art["url"]
                meta["artifact"] = art
            return self.send_json(200, meta)
        if path == "/api/results":
            data = collect()["workflows"]
            return self.send_json(200, [
                {"name": w["name"], "owner": w["owner"], "trust": w["trust"],
                 "effect": w["effect"], "verified_at": w["verified_at"],
                 "results": w["results"]} for w in data])
        return self.static(path)

    def page(self):
        overview.set_root(str(ROOT))
        inventory.set_root(str(ROOT))
        html_text = overview.render()  # fresh from the collectors, never stale
        # The page lives at /docs/overview.html so its ../ links resolve; a
        # request for / just gets the same content at that path semantics.
        self.send(200, html_text.encode("utf-8"), "text/html; charset=utf-8")

    def static(self, path: str):
        """Read-only file serving inside ROOT, so the page's relative links
        (../sites/..., ../projects/...) work. Traversal-guarded."""
        target = (ROOT / path.lstrip("/")).resolve()
        if not str(target).startswith(str(ROOT.resolve())) or not target.is_file():
            return self.send_json(404, {"error": f"not found: {path}"})
        ext = target.suffix.lower()
        if ext in TEXT_TYPES:
            return self.send(200, target.read_bytes(),
                             TEXT_TYPES[ext] + "; charset=utf-8")
        if ext in BIN_TYPES:
            return self.send(200, target.read_bytes(), BIN_TYPES[ext])
        return self.send_json(404, {"error": f"file type not served: {ext}"})

    _fetch_at = 0.0

    def deployed_state(self) -> bool:
        """Is the published page current? With deploy-on-push automation the
        standing artifact tracks origin/main, so 'deployed' means: no local
        changes to the page's inputs, and HEAD is pushed. Gray share link
        otherwise — 'the shared page does not have your changes yet'."""
        import time
        try:
            if time.time() - Handler._fetch_at > 300:  # refresh origin/main ref
                subprocess.run(["git", "-C", str(ROOT), "fetch", "--quiet"],
                               capture_output=True, timeout=20)
                Handler._fetch_at = time.time()
            dirty = subprocess.run(
                ["git", "-C", str(ROOT), "status", "--porcelain", "--",
                 "sites", "projects", "schema", "scripts", "docs", "config.yaml"],
                capture_output=True, text=True, timeout=20).stdout.strip()
            head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, timeout=20).stdout
            remote = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "origin/main"],
                capture_output=True, text=True, timeout=20).stdout
            return not dirty and head.strip() == remote.strip() and bool(head.strip())
        except Exception:
            return False

    # -- POST /api/deploy ----------------------------------------------------
    @staticmethod
    def map_artifact_url() -> str | None:
        """A map repository's own dashboard artifact, registered in its
        config.yaml as `dashboard: artifact_url:`. None until the first
        publish writes it back. Read by regex, not a YAML parser — this
        server stays stdlib-only."""
        cfg = ROOT / "config.yaml"
        if not cfg.is_file():
            return None
        m = re.search(r"artifact_url:\s*"
                      r"(https://claude\.ai/code/artifact/[0-9a-f-]+)",
                      cfg.read_text(encoding="utf-8"))
        return m.group(1) if m else None

    @staticmethod
    def map_dashboard() -> dict:
        """#36: the map repo's artifact registration plus currency — is the
        published snapshot's hash the hash this page would build to now?
        current is None when unknowable (nothing published, no hash recorded
        at publish time, or no git remote to build deploy links from)."""
        art = {"url": None, "published_at": None, "current": None}
        cfg = ROOT / "config.yaml"
        if not cfg.is_file():
            return art
        text = cfg.read_text(encoding="utf-8")
        m = re.search(r"artifact_url:\s*"
                      r"(https://claude\.ai/code/artifact/[0-9a-f-]+)", text)
        if not m:
            return art
        art["url"] = m.group(1)
        m = re.search(r"published_at:\s*\"?([0-9][0-9-]+)", text)
        if m:
            art["published_at"] = m.group(1)
        m = re.search(r"published_hash:\s*(sha256:[0-9a-f]+)", text)
        if m:
            try:
                overview.set_root(str(ROOT))
                inventory.set_root(str(ROOT))
                fresh = overview.render(base=overview.github_base(),
                                        fragment=True)
                art["current"] = overview.content_hash(fresh) == m.group(1)
            except SystemExit:
                pass  # github_base exits without a remote; deploy would too
        return art

    def deploy(self, consent: set):
        """Prepare the dashboard's shareable build and hand off to the
        /deploy-dashboard skill. Artifact publishing is interactive-only
        (off in headless agent contexts by design), so the button cannot
        publish by itself — it builds, and an interactive agent session
        publishes.

        Framework page: builds freely — public content, standing URL.
        Map repository (#34): local by default. Building for deploy is gated
        by the same ask channel as a mutating run — the server states the
        question, the confirmation click consents to THIS build only — and
        the publish target is that repository's OWN private artifact
        (registered in its config.yaml), never the framework's standing URL.
        The artifact is private to the operator's account; sharing it is the
        guardrail's line, and that stays a human decision made elsewhere."""
        if ROOT == FRAMEWORK:
            jobs = (FRAMEWORK / "docs" / "JOBS.md").read_text(encoding="utf-8")
            m = re.search(r"https://claude\.ai/code/artifact/[0-9a-f-]+", jobs)
            if not m:
                return self.send_json(500, {"error":
                    "no standing artifact URL registered in docs/JOBS.md"})
            url = m.group(0)
            note = ("Build ready. Publishing needs an interactive agent session "
                    "(artifact publishing is off in headless contexts by design): "
                    "run /deploy-dashboard in Claude Code — it publishes this "
                    "build to the standing URL.")
        else:
            if "publish-dashboard" not in consent:
                return self.send_json(409, {"ask": "publish-dashboard",
                    "question":
                    f"'{ROOT.name}' is a map repository — its dashboard stays "
                    "local by default. Build it for publishing to its own "
                    "PRIVATE Claude artifact (visible to your account only; "
                    "never the framework's standing URL, never to be shared)? "
                    "Publishing itself still happens in an interactive agent "
                    "session."})
            url = self.map_artifact_url()
            note = ("Build ready. Run /deploy-dashboard in a Claude Code "
                    "session started in THIS map repository (it carries the "
                    "skill) — it publishes this build to the repo's own "
                    "private artifact. " + (
                    "Registered URL: " + url if url else
                    "No artifact registered yet in config.yaml — the first "
                    "publish creates one and writes `dashboard: artifact_url:` "
                    "back.") +
                    " Never share that artifact; redeploying does not scrub "
                    "its version history (docs/PERMISSIONS.md).")
        out = ROOT / ".runner" / "deploy" / "dashboard-artifact.html"
        overview.set_root(str(ROOT))
        inventory.set_root(str(ROOT))
        info = overview.deploy_build(str(out))  # stamped page + build-info.json
        return self.send_json(200, {
            "prepared": str(out),
            "url": url,
            "command": "/deploy-dashboard",
            "note": note,
            "build": info,
        })

    # -- POST /api/run/<workflow> ------------------------------------------
    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self.send_json(400, {"error": "body must be JSON"})
        consent = set(body.get("consent") or [])
        if path == "/api/deploy":
            return self.deploy(consent)
        m = re.match(r"^/api/run/([A-Za-z0-9._-]+)$", path)
        if not m:
            return self.send_json(404, {"error": "unknown endpoint"})
        params = body.get("params") or {}
        return self.run_workflow(m.group(1), params, consent)

    def run_workflow(self, name: str, params: dict, consent: set):
        # Pre-check with the runner's own gate logic so the page can render
        # the ask BEFORE anything launches. The subprocess enforces it again —
        # the server never widens what run.py itself would allow.
        try:
            wf_path, data = runner.find_workflow(ROOT, name)
        except runner.RunError as exc:
            return self.send_json(404, {"error": str(exc)})
        wf = (data or {}).get("workflow", {})
        if wf.get("mode") != "deterministic":
            return self.send_json(400, {"error":
                f"'{name}' is mode: {wf.get('mode') or 'unset'} — it needs an LLM "
                "host, not the runner. Use the copy button and /run it in a session."})
        action_class = runner.EFFECT_CLASS.get(wf.get("effect"))
        if not action_class:
            return self.send_json(400, {"error":
                f"effect: {wf.get('effect') or 'undeclared'} — declare "
                "read-only | mutating | destructive (schema/workflow.yaml)"})
        verdict, source = "allow", ""
        involved = [s for s in ([wf.get("site")] if wf.get("site") else
                                list(wf.get("sites") or []))
                    if isinstance(s, str) and not s.startswith("$")]
        for site_name in involved:
            try:
                settings = runner.resolve_settings(
                    ROOT, runner.Site(ROOT, site_name), None)
            except runner.RunError as exc:
                return self.send_json(400, {"error": str(exc)})
            v = runner.permission_verdict(settings, action_class)
            if runner.STRICTNESS[v] > runner.STRICTNESS[verdict]:
                env = (settings.get("policy") or {}).get("environment", "?")
                verdict, source = v, f"site '{site_name}' (environment: {env})"
        if verdict == "deny":
            return self.send_json(403, {"error":
                f"permission denied: '{wf.get('effect')}' needs class "
                f"'{action_class}', which is 'deny' for {source}. Policy, not a "
                "bug — docs/PERMISSIONS.md."})
        if verdict == "ask" and action_class not in consent:
            return self.send_json(409, {"ask": action_class, "question":
                f"'{name}' is {wf.get('effect')} and {source} says ask. "
                "Run it this once?"})

        is_test = any(s.get("action") == "assert" for s in wf.get("steps") or [])
        cmd = [sys.executable, str(FRAMEWORK / "scripts" / "run.py"), name, "--json"]
        if ROOT != FRAMEWORK:
            cmd += ["--root", str(ROOT)]
        if is_test:
            cmd.append("--record")
        for key, value in params.items():
            cmd += ["--param", f"{key}={value}"]
        for cls in consent & {"write", "destructive", "auth"}:
            cmd.append(f"--yes-{cls}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", timeout=RUN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return self.send_json(500, {"error": f"run exceeded {RUN_TIMEOUT_S}s"})
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return self.send_json(500, {"error":
                (proc.stderr.strip() or proc.stdout.strip() or
                 f"runner exited {proc.returncode} with no output")})
        return self.send_json(200, {"result": result,
                                    "record": is_test,
                                    "exit": proc.returncode})


def main():
    global ROOT
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", help="serve this map repository instead of the framework")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    if args.root:
        ROOT = Path(args.root).resolve()
        if not (ROOT / "sites").is_dir():
            sys.exit(f"{ROOT} has no sites/ — not a map repository?")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"dashboard: http://127.0.0.1:{args.port}/  (tree: {ROOT})")
    print("Ctrl+C stops it. Localhost only, by design.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
