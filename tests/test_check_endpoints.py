import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parent.parent / "scripts" / "check.py"

PAGE = """\
page:
  name: Issues List
  url_pattern: /issues
  elements:
    - name: search-input
      type: input
      locator: {{ strategy: css, value: "#q" }}
  endpoints:
    - name: search-issues
      method: GET
      url_pattern: "/issues?q={{query}}&page={{page}}"
      inputs: [search-input]
      returns: [meta, payload]
      effect: read-only
{extra}"""

FAKE_TOKEN = "ghp_" + "Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1Jd5Fg0Ys"

SECOND = "    - name: {name}\n      method: GET\n      effect: read-only\n      url_pattern: {url}\n"

# probe: (lines after the clean first entry, the failure it must print, the value it must not)
PROBES = {
    "aws key in path": (SECOND.format(name="x", url='"/s3/AKIAIOSFODNN7EXAMPLE/list"'),
                        "endpoints[1].url_pattern has a literal path segment", "AKIA"),
    "letters-only key in path": (
        SECOND.format(name="x", url='"/api/key/abcdefghijklmnopqrstuvwxyzabcdef/items"'),
        "endpoints[1].url_pattern has a literal path segment", "abcdefghijkl"),
    "16-hex key in path": (SECOND.format(name="x", url='"/api/k/3f9a1c7e2b4d6f80/items"'),
                           "endpoints[1].url_pattern has a literal path segment", "3f9a1c7e"),
    "uuid in path": (
        SECOND.format(name="x", url='"/sess/550e8400-e29b-41d4-a716-446655440000/items"'),
        "endpoints[1].url_pattern has a literal path segment", "550e8400"),
    "fragment": (SECOND.format(name="x", url='"/cb#access_token=s3cr3t.T0k3n.v4lue"'),
                 "endpoints[1].url_pattern has a fragment", "s3cr3t"),
    "query without =": (SECOND.format(name="x", url='"/issues?s3cr3tT0ken99"'),
                        "endpoints[1].url_pattern has a query key that is not word-like",
                        "s3cr3t"),
    "query with ;": (SECOND.format(name="x", url='"/issues?q={q};sid=abc123xyz"'),
                     "endpoints[1].url_pattern query uses ';'", "abc123"),
    "placeholder as query key": (SECOND.format(name="x", url='"/issues?q={q}&{api_key}=x"'),
                                 "endpoints[1].url_pattern has a query key that is not word-like",
                                 "api_key"),
    "secret as query key": (SECOND.format(name="x", url='"/issues?sk-live-4f8a9b={v}"'),
                            "endpoints[1].url_pattern has a query key that is not word-like",
                            "sk-live"),
    "token as host label": (SECOND.format(name="x", url='"https://tok-a1b2c3d4e5.api.example.com/x"'),
                            "endpoints[1].url_pattern has a host label that is not word-like",
                            "tok-a1b2"),
    "dict in returns": (SECOND.format(name="x", url="/x")
                        + '      returns: [{Authorization: "Bearer abcdefgh12345678"}]\n',
                        "endpoints[1].returns is not a list of strings", "abcdefgh1234"),
    "dict as description": (SECOND.format(name="x", url="/x")
                            + '      description: {cookie: "user_session=abcdefgh12345678"}\n',
                            "endpoints[1].description is not a string", "abcdefgh1234"),
    "dict as url_pattern": (
        SECOND.format(name="x", url='{path: /x, cookie: "sid=abc123def456ghi789jkl012mno"}'),
        "endpoints[1].url_pattern is not a string", "abc123"),
    "dict in inputs": (SECOND.format(name="x", url="/x") + "      inputs: [{cookie: abc}]\n",
                       "endpoints[1].inputs is not a list of strings", "cookie"),
    "cookie and api key headers in description": (
        SECOND.format(name="x", url="/x")
        + '      description: "send Cookie: sid=9f8e7d6c5b4a; X-Api-Key: Kx81Pq92"\n',
        "endpoints[1].description holds a header", "9f8e7d"),
    "api key header in description": (
        SECOND.format(name="x", url="/x") + '      description: "X-Api-Key: 7f3k9q2m1x8z"\n',
        "endpoints[1].description holds a header", "7f3k9q"),
    "short bearer": (SECOND.format(name="x", url="/x")
                     + '      description: "Authorization: Bearer abc1234"\n',
                     "endpoints[1].description holds a header", "abc1234"),
    "basic credentials": (SECOND.format(name="x", url="/x")
                          + '      description: "Authorization: Basic dXNlcjpwYXNz"\n',
                          "endpoints[1].description holds a header", "dXNlcj"),
    "dotted token assignment": (SECOND.format(name="x", url="/x")
                                + '      description: "token=ab12.cd34.ef56.gh78.ij90.kl12"\n',
                                "endpoints[1].description holds a header", "ab12.cd34"),
    "secret as name": (SECOND.format(name='"sid=9f8e7d6c5b4a"', url="/y"),
                       "endpoints[1].name holds a header", "9f8e7d"),
    "yaml merge key": (SECOND.format(name="x", url="/x")
                       + '      <<: {cookie: "sid=Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1Jd5"}\n',
                       "endpoints[1].cookie is not an endpoint key", "Q7xk2"),
    "cookie in a gotcha": (
        '  gotchas:\n    - "views.json returned 403 until Cookie: user_session='
        'Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1J was sent"\n',
        "issues-list.yaml: gotchas[0] holds a header", "Q7xk2"),
}


def check(extra=""):
    with tempfile.TemporaryDirectory() as tmp:
        pages = Path(tmp) / "sites" / "demo" / "pages"
        pages.mkdir(parents=True)
        (pages / "issues-list.yaml").write_text(PAGE.format(extra=extra), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CHECK), "--root", tmp, "--only", "endpoints"],
            capture_output=True, text=True)


class CheckEndpointsTest(unittest.TestCase):
    def assertRefused(self, extra, key):
        done = check(extra)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn(f"sites/demo/pages/issues-list.yaml: endpoints[0].{key}", done.stdout)
        self.assertNotIn(FAKE_TOKEN, done.stdout)

    def test_a_clean_block_passes(self):
        done = check()
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("[endpoints] ok", done.stdout)

    def test_a_header_value_is_refused(self):
        self.assertRefused(f'      headers: {{ x-fetch-nonce: "{FAKE_TOKEN}" }}\n', "headers")

    def test_a_cookie_value_is_refused(self):
        self.assertRefused(f'      cookies: "user_session={FAKE_TOKEN}"\n', "cookies")

    def test_a_bearer_string_is_refused(self):
        self.assertRefused('      description: "send Bearer abcdefgh12345678"\n', "description")

    def test_an_opaque_token_in_a_known_key_is_refused(self):
        self.assertRefused(f'      description: "{FAKE_TOKEN}"\n', "description")

    def test_every_audit_probe_is_refused_without_its_value(self):
        for probe, (extra, failure, value) in PROBES.items():
            with self.subTest(probe):
                done = check(extra)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn(failure, done.stdout)
                self.assertNotIn(value, done.stdout + done.stderr)

    def test_the_spike_endpoints_and_the_demo_gotchas_pass(self):
        done = check(
            SECOND.format(name="issue-fields",
                          url='"https://github.com/_filter/issue_fields?repo={repo}"')
            + "      returns: [issue_fields]\n"
            + SECOND.format(name="saved-views", url="/issues/views.json")
            + "      returns: [savedViews, viewerCanManageViews]\n"
            + '  gotchas:\n    - "Typing does NOT filter; Enter navigates to ?q=<term>"\n'
            + "    - \"Open and Closed are <a href='#'> controls, re-read on 2026-10-09\"\n")
        self.assertEqual(done.returncode, 0, done.stdout)

    def test_a_token_pasted_as_a_key_is_refused_unprinted(self):
        self.assertRefused(f'      "{FAKE_TOKEN}": 1\n', "<not shown> is not an endpoint key")

    def test_a_literal_query_value_is_refused(self):
        done = check('    - name: x\n      method: GET\n'
                     '      url_pattern: "/issues?q=is:open&page={page}"\n'
                     '      effect: read-only\n')
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("endpoints[1].url_pattern query 'q' has no {placeholder} value", done.stdout)
        self.assertNotIn("query 'page'", done.stdout)
        self.assertNotIn("is:open", done.stdout)

    def test_an_undeclared_effect_is_refused(self):
        done = check('    - name: x\n      method: POST\n      url_pattern: /issues\n')
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("endpoints[1].effect is not one of", done.stdout)

    def test_an_input_that_is_not_an_element_is_refused(self):
        done = check('    - name: x\n      method: GET\n      url_pattern: /issues\n'
                     '      inputs: [gone-input]\n      effect: read-only\n')
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("endpoints[1].inputs names 'gone-input'", done.stdout)


if __name__ == "__main__":
    unittest.main()
