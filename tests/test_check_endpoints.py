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

    def test_a_token_pasted_as_a_key_is_refused_unprinted(self):
        self.assertRefused(f'      "{FAKE_TOKEN}": 1\n', "<token-like> is not an endpoint key")

    def test_a_literal_query_value_is_refused(self):
        done = check('    - name: x\n      method: GET\n'
                     '      url_pattern: "/issues?q=is:open&page={page}"\n'
                     '      effect: read-only\n')
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("endpoints[1].url_pattern query 'q' has a literal value", done.stdout)
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
