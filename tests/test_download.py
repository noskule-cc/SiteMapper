"""The `download` and `hover` steps against a real browser and a local page that serves a file.

Skipped when Playwright or Chrome is missing, like the runner itself needs them."""
import functools
import http.server
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PAYLOAD = b"imsi;bytes\n999000000000001;42\n"
PAGE = b"""<html><body>
<a id="report" href="/data/report.csv" download>Report</a>
<button id="nothing" onclick="1+1">Nothing</button>
<div id="menu" onmouseenter="document.getElementById('sub').style.display='block'">Menu</div>
<div id="sub" style="display:none">Submenu</div>
</body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/data/report.csv":
            body, kind = PAYLOAD, "text/csv"
            extra = ("Content-Disposition", 'attachment; filename="report-2026-11-25.csv"')
        else:
            body, kind, extra = PAGE, "text/html", ("X-Page", "1")
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header(*extra)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Site:
    """Just enough of run.Site for build_locator's element lookup."""
    name = "local"

    def element(self, page, name):
        return {"name": name, "locator": {"strategy": "css", "value": f"#{name}"}}


class FakeBindings:
    def __init__(self):
        self.captures = {}

    def resolve(self, text):
        return text


@unittest.skipIf(sync_playwright is None, "Playwright is not installed")
class DownloadStep(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(channel="chrome", headless=True)
        except Exception as exc:
            cls.pw.stop()
            cls.server.shutdown()
            raise unittest.SkipTest(f"Chrome is not available: {str(exc).splitlines()[0]}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()

    def runner(self, downloads):
        runner = run.Runner.__new__(run.Runner)
        runner.context = self.browser.new_context(accept_downloads=True)
        runner.pw_page = runner.context.new_page()
        runner.pw_page.goto(self.url)
        runner.bindings = FakeBindings()
        runner.downloads = downloads
        runner.site = lambda step: Site()
        runner._element = lambda step, site: site.element(step["page"], step["element"])
        runner.DOWNLOAD_TIMEOUT_MS = 2000
        self.addCleanup(runner.context.close)
        return runner

    def test_saves_the_file_into_the_run_folder_and_captures_the_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.runner(Path(tmp) / "downloads")
            runner.do_download({"action": "download", "page": "p", "element": "report",
                                "capture": "report_csv"})
            saved = Path(runner.bindings.captures["report_csv"])
            self.assertEqual(saved, Path(tmp) / "downloads" / "report-2026-11-25.csv")
            self.assertEqual(saved.read_bytes(), PAYLOAD)

    def test_without_a_run_folder_it_saves_into_a_temp_dir(self):
        runner = self.runner(None)
        runner.do_download({"action": "download", "page": "p", "element": "report",
                            "capture": "report_csv"})
        saved = Path(runner.bindings.captures["report_csv"])
        self.addCleanup(lambda: saved.unlink() or saved.parent.rmdir())
        self.assertEqual(saved.read_bytes(), PAYLOAD)

    def test_a_click_that_starts_no_download_fails_the_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = self.runner(Path(tmp))
            with self.assertRaises(Exception) as caught:
                runner.do_download({"action": "download", "page": "p", "element": "nothing"})
            self.assertIn("Timeout", type(caught.exception).__name__)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_hover_opens_a_menu_that_opens_on_hover(self):
        runner = self.runner(None)
        self.assertFalse(runner.pw_page.locator("#sub").is_visible())
        runner.do_hover({"action": "hover", "page": "p", "element": "menu"})
        self.assertTrue(runner.pw_page.locator("#sub").is_visible())

    def test_the_actions_are_known_and_mechanical(self):
        for action in ("download", "hover"):
            self.assertIn(action, run.tree.ACTIONS)
            self.assertIn(action, run.MECHANICAL_ACTIONS)


if __name__ == "__main__":
    unittest.main()
