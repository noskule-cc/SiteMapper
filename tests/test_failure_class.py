"""Which class a failure gets, driven through the runner's own methods with a
stubbed page, so drift and auth are pinned without a live site."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run  # noqa: E402

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright._impl._errors import TargetClosedError as PlaywrightClosed
except ImportError:
    PlaywrightError = None

ELEMENT_STEP = {"action": "read", "page": "list", "element": "table"}


class FakeLocator:
    def __init__(self, page, value):
        self.page, self.value = page, value
        self.first = self

    def fill(self, text):
        self.page.act(self.value, "fill")

    def click(self):
        self.page.act(self.value, "click")

    def wait_for(self, state=None, timeout=None):
        self.page.act(self.value, "wait_for")

    def input_value(self):
        return self.page.field

    def press_sequentially(self, text, delay=0):
        pass

    def evaluate(self, js, arg):
        return self.page.grid


class FakePage:
    """Raises `fail[(css, verb)]` when that locator does that."""

    def __init__(self, fail=None, field="", grid=None):
        self.fail, self.field, self.grid = fail or {}, field, grid
        self.url = "https://site.invalid/list"
        self.keyboard = self

    def locator(self, value):
        return FakeLocator(self, value)

    def act(self, value, verb):
        if (value, verb) in self.fail:
            raise self.fail[(value, verb)]

    def press(self, key):
        pass

    def goto(self, url):
        pass

    def wait_for_timeout(self, ms):
        pass

    def wait_for_load_state(self, state=None):
        pass


def bare_runner(page=None) -> run.Runner:
    runner = run.Runner.__new__(run.Runner)
    runner._last_page, runner.pw_page, runner.snapshot = "list", page, {}  # arrived
    runner.DEFAULT_TIMEOUT_MS = 0
    return runner


def failing(runner: run.Runner, step: dict, body) -> run.RunError | BaseException:
    setattr(runner, f"do_{step['action']}", lambda _step: body())
    try:
        runner.run_step(step)
    except BaseException as exc:
        return exc
    raise AssertionError("run_step did not fail")


class StepFailureTest(unittest.TestCase):
    def test_a_table_header_that_matches_no_column_is_drift(self):
        runner = bare_runner(FakePage())
        table = FakeLocator(runner.pw_page, "table")
        runner.pw_page.grid = {"headers": ["Title"], "rows": [["Issue 1"]]}
        exc = failing(runner, ELEMENT_STEP, lambda: runner._read_cell(table, "Issue 1", "State"))
        self.assertEqual((exc.cls, str(exc)),
                         ("drift", "header 'State' matches 0 of the columns ['Title'], expected 1"))

    def test_a_row_the_table_lacks_is_drift(self):
        runner = bare_runner(FakePage(grid={"headers": ["Title"], "rows": []}))
        table = FakeLocator(runner.pw_page, "table")
        exc = failing(runner, ELEMENT_STEP, lambda: runner._read_cell(table, "Issue 9", "Title"))
        self.assertEqual((exc.cls, str(exc)), ("drift", "0 rows contain 'Issue 9', expected 1"))

    def test_a_field_that_reverts_the_value_is_drift(self):
        runner = bare_runner(FakePage(field="old"))
        field = FakeLocator(runner.pw_page, "#search")
        exc = failing(runner, {"action": "input", "page": "list", "element": "search"},
                      lambda: runner._ensure_value(field, "new"))
        self.assertEqual(exc.cls, "drift")
        self.assertTrue(str(exc).startswith("field did not accept 'new' (reads 'old')"))

    @unittest.skipIf(PlaywrightError is None, "playwright is not installed")
    def test_a_playwright_error_on_an_element_is_drift(self):
        def fill():
            raise PlaywrightError("Error: Element is not an <input>, <textarea> or "
                                  "[contenteditable] element")
        exc = failing(bare_runner(), {"action": "input", "page": "list", "element": "search"},
                      fill)
        self.assertEqual((type(exc), exc.cls), (run.RunError, "drift"))
        self.assertTrue(str(exc).startswith("Error: Error: Element is not an <input>"), str(exc))

    @unittest.skipIf(PlaywrightError is None, "playwright is not installed")
    def test_a_playwright_timeout_on_an_element_is_drift(self):
        def click():
            raise PlaywrightTimeout("Locator.click: Timeout 10000ms exceeded.")
        exc = failing(bare_runner(), {"action": "click", "page": "list", "element": "save"},
                      click)
        self.assertEqual((exc.cls, str(exc)),
                         ("drift", "TimeoutError: Locator.click: Timeout 10000ms exceeded."))

    @unittest.skipIf(PlaywrightError is None, "playwright is not installed")
    def test_a_browser_that_went_away_mid_click_stays_the_runners(self):
        gone = [PlaywrightClosed("Locator.click: Target page, context or browser has been "
                                 "closed"),
                PlaywrightError("Locator.click: Target crashed"),
                PlaywrightError("Locator.fill: Execution context was destroyed, most likely "
                                "because of a navigation"),
                PlaywrightError("Locator.click: net::ERR_CONNECTION_RESET")]
        for exc in gone:
            def click(exc=exc):
                raise exc
            caught = failing(bare_runner(), {"action": "click", "page": "list",
                                             "element": "save"}, click)
            self.assertIs(caught, exc)

    @unittest.skipIf(PlaywrightError is None, "playwright is not installed")
    def test_a_playwright_error_without_an_element_stays_the_runners(self):
        def goto():
            raise PlaywrightError("net::ERR_NAME_NOT_RESOLVED")
        exc = failing(bare_runner(), {"action": "navigate", "value": "https://x.invalid"}, goto)
        self.assertIs(type(exc), PlaywrightError)


class Recorded:
    """The parts of a Runner that execute reads, with a fingerprint mismatch."""
    assertions, evidence, snapshot = [], [], {}

    def __init__(self, raise_exc=None):
        self.raise_exc = raise_exc
        self.fingerprints = {}

    def run_step(self, step, phase="steps", index=0, number=0):
        self.fingerprints["list"] = "mismatch"
        if self.raise_exc:
            raise self.raise_exc

    def build_failure(self):
        return {}

    def stop(self):
        pass


class FingerprintTest(unittest.TestCase):
    def execute(self, runner) -> tuple[dict, str]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        wf_path = Path(tmp.name) / "watch.yaml"
        wf_path.write_text("workflow:\n  name: watch\n  mode: deterministic\n"
                           "  trust: verified\n", encoding="utf-8")
        workflow = {"name": "watch", "trust": "verified",
                    "steps": [{"action": "script", "script": "noop.py"}]}
        result = {"workflow": "watch", "status": "passed", "error": ""}
        run.execute(runner, workflow, run.Bindings(workflow, {}), wf_path, "site", result)
        return result, wf_path.read_text(encoding="utf-8")

    def test_a_fingerprint_mismatch_on_a_passing_run_is_drift(self):
        result, text = self.execute(Recorded())
        self.assertEqual((result["status"], result["class"], result["next"]),
                         ("passed", "drift", "/repair watch"))
        self.assertIn("trust: broken", text)

    def test_a_fingerprint_mismatch_explains_a_runner_error(self):
        result, text = self.execute(Recorded(ValueError("boom")))
        self.assertEqual((result["status"], result["class"]), ("error", "drift"))
        self.assertIn("trust: broken", text)


LOGIN_SITE = "site:\n  name: shop\n  base_url: https://shop.invalid\n"
LOGIN_PAGE = """\
page:
  name: login
  url_pattern: /login
  elements:
    - {name: user, locator: {strategy: css, value: "#user"}}
    - {name: pass, locator: {strategy: css, value: "#pass"}}
    - {name: go, locator: {strategy: css, value: "#go"}}
"""
PERSONA = {"name": "bot", "auth": "automated", "fresh_login": True,
           "login": {"page": "login", "username_element": "user",
                     "password_element": "pass", "submit_element": "go"}}


class LoginTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "sites" / "shop" / "pages").mkdir(parents=True)
        (self.root / "sites" / "shop" / "site.yaml").write_text(LOGIN_SITE, encoding="utf-8")
        (self.root / "sites" / "shop" / "pages" / "login.yaml").write_text(LOGIN_PAGE,
                                                                          encoding="utf-8")

    def log_in(self, persona: dict, page: FakePage) -> run.RunError:
        runner = bare_runner(page)
        runner.root, runner.persona, runner.login_failed = self.root, persona, False
        with self.assertRaises(run.RunError) as caught:
            runner.log_in("shop", ("user", "secret"))
        self.assertTrue(runner.login_failed)
        return caught.exception

    @unittest.skipIf(PlaywrightError is None, "playwright is not installed")
    def test_a_login_element_that_times_out_is_drift(self):
        exc = self.log_in(PERSONA, FakePage(
            {("#user", "fill"): PlaywrightTimeout("Locator.fill: Timeout 10000ms exceeded.")}))
        self.assertEqual((exc.cls, run.next_step(exc.cls, "buy", exc.hint)),
                         ("drift", "/repair buy"))
        self.assertTrue(str(exc).startswith("login.username_element 'user' on page 'login'"))

    def test_a_login_element_the_map_lacks_is_drift(self):
        exc = self.log_in({**PERSONA, "login": {**PERSONA["login"], "submit_element": "send"}},
                          FakePage())
        self.assertEqual(exc.cls, "drift")
        self.assertIn("maps no element 'send'", str(exc))

    def test_a_rejected_login_is_auth(self):
        exc = self.log_in(PERSONA, FakePage({("#pass", "wait_for"): ValueError("still shown")}))
        self.assertEqual((exc.cls, run.next_step(exc.cls, "buy", exc.hint)),
                         ("auth", "check the credentials of persona 'bot'; the runner did "
                                  "not retry"))

    def test_a_navigate_to_a_page_with_placeholders_is_input(self):
        (self.root / "sites" / "shop" / "pages" / "order.yaml").write_text(
            "page:\n  name: order\n  url_pattern: /orders/{id}\n", encoding="utf-8")
        runner = bare_runner(FakePage())
        runner.root, runner.sites, runner.default_site = self.root, {}, "shop"
        runner.bindings = run.Bindings({}, {})
        exc = failing(runner, {"action": "navigate", "page": "order"},
                      lambda: run.Runner.do_navigate(runner, {"page": "order"}))
        self.assertEqual((exc.cls, run.next_step(exc.cls, "buy", exc.hint)),
                         ("input", "run buy again with a navigate step whose `value:` fills "
                                   "the placeholders"))

    def test_a_failure_outside_the_map_and_the_login_is_error(self):
        page = FakePage()
        page.goto = lambda url: (_ for _ in ()).throw(OSError("network unreachable"))
        exc = self.log_in(PERSONA, page)
        self.assertEqual((exc.cls, str(exc)),
                         ("error", "OSError: network unreachable (no screenshot taken: the "
                                   "failure was in the login)"))


class StateExpiredTest(unittest.TestCase):
    PAST, FUTURE = 1700000000, time.time() + 86400

    def expired(self, cookies, origins=()) -> str:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        state = Path(tmp.name) / "state.json"
        state.write_text(json.dumps({"cookies": [{"name": f"c{i}", "expires": e}
                                                 for i, e in enumerate(cookies)],
                                     "origins": list(origins)}), encoding="utf-8")
        return run.state_expired(state)

    def test_every_cookie_expired_and_no_local_storage_is_expired(self):
        self.assertEqual(self.expired([self.PAST - 60, self.PAST]), "2023-11-14T22:13:20Z")

    def test_one_live_cookie_keeps_the_state(self):
        self.assertEqual(self.expired([self.PAST, self.FUTURE]), "")

    def test_a_browser_session_cookie_keeps_the_state(self):
        self.assertEqual(self.expired([self.PAST, -1]), "")

    def test_a_local_storage_session_without_cookies_keeps_the_state(self):
        token = {"origin": "https://app.invalid",
                 "localStorage": [{"name": "token", "value": "jwt"}]}
        self.assertEqual(self.expired([], [token]), "")

    def test_expired_cookies_beside_analytics_local_storage_are_expired(self):
        analytics = {"origin": "https://app.invalid",
                     "localStorage": [{"name": "_ga_seen", "value": "1"}]}
        self.assertEqual(self.expired([self.PAST], [analytics]), "2023-11-14T22:13:20Z")

    def test_a_state_without_cookies_is_not_expired(self):
        self.assertEqual(self.expired([]), "")


if __name__ == "__main__":
    unittest.main()
