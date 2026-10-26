import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parent.parent / "scripts" / "check.py"

HEAD = """\
page:
  name: Issues List
  url_pattern: /issues
  purpose: list issues
  elements:
    - name: search-input
      type: input
      locator: { strategy: css, value: "#q" }
    - name: page-number
      type: input
      locator: { strategy: css, value: "#p" }
  endpoints:
"""
CLEAN = """\
    - name: search_issues
      method: GET
      url_pattern: "/issues?q={query}&page={page}"
      inputs: [search-input]
      returns: [meta, payload]
      effect: read-only
"""
FAKE_TOKEN = "ghp_" + "Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1Jd5Fg0Ys"


def entry(url="/x", name="x", method="GET", effect="read-only", extra=""):
    return (f"    - name: {name}\n      method: {method}\n      effect: {effect}\n"
            f"      url_pattern: {url}\n{extra}")


def check(body):
    with tempfile.TemporaryDirectory() as tmp:
        pages = Path(tmp) / "sites" / "demo" / "pages"
        pages.mkdir(parents=True)
        (pages / "issues-list.yaml").write_text(HEAD + body, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CHECK), "--root", tmp, "--only", "endpoints"],
            capture_output=True, text=True)


# Real API shapes that must pass: the re-verifier's 18 legitimate endpoints.
LEGITIMATE = [
    entry("/api/v2/issues/{id}/comments", "list_comments", extra=(
        "      inputs: [search-input]\n      returns: [comments, total_count]\n")),
    entry("/graphql", "graphql", "POST", "mutating", "      returns: [data, errors]\n"),
    entry('"https://api.github.com/repos/{owner}/{repo}/pulls?state={state}&per_page={n}'
          '&page={p}"', "list_pulls", extra="      inputs: [page-number]\n      returns: []\n"),
    entry('"/api/v2beta/search?q={query}"', "search_v2beta",
          extra="      inputs: [search-input]\n      returns: [items, next_cursor]\n"),
    entry("/oauth2/v1/userinfo", "oauth2_userinfo", extra="      returns: [sub, email, name]\n"),
    entry('"https://s3.eu-central-1.amazonaws.com/{bucket}?list-type=2&prefix={prefix}"',
          "s3_list", extra="      returns: [ListBucketResult]\n"),
    entry("/api/v1/projects/{project_id}/labels/{label_id}", "delete_label", "DELETE",
          "destructive"),
    entry('"https://gitlab.example.com:8443/api/v4/projects/{id}/issues/{iid}'
          '/resource_label_events"', "issue_events",
          extra="      returns: [id, user, created_at, label, action]\n"),
    entry("/api/v1/issues.json", "s", extra=(
        '  gotchas:\n    - "views.json loads saved views, not issues; do not propose it"\n'
        '    - "The /api/v1/issues.json call returns 30 items per page; use per_page up to'
        ' 100"\n')),
    entry('"/rest/api/2/search?jql={jql}"'),
    entry('"/rest/api/3/issue/{key}"'),
    entry("/api/2.0/clusters/list"),
    entry('"/2/tweets/{id}"'),
    entry('"/issues/{id}.json"'),
    entry('"/2015-03-31/functions/{name}/invocations"'),
    entry("/api/getUserInfo"),
    entry('"/s3/{bucket}?list-type={lt}&prefix={p}"'),
    entry('"/api/v1/search?q={q}&format=json"'),
    entry('"/api/articles?include=author,comments"'),
    entry('"/graphql?operationName=GetViewer"'),
    entry('"/api/items?sort=-created_at"'),
    entry("/api/v1/getUserProfileSettings2024"),
    entry('"https://github.com/_filter/issue_fields?repo={repo}"', "issue_fields",
          extra="      returns: [issue_fields]\n"),
]

GOTCHA_PROSE = [
    "Send X-GitHub-Api-Version: 2022-11-28", "Pass since=2024-01-01 to filter by date",
    "Requires api-version=2023-11-15", "Max per_page=100; default 30",
    "Returns sha values like the commit id", "Responds 429 after 5000 requests per hour",
    "Ids are integers; the cursor is an opaque string",
    "Typing does NOT filter; Enter navigates to ?q=<term>",
    "Open and Closed are <a href='#'> controls, re-read on 2026-10-09",
]

# probe: (page body after `endpoints:`, failure it must print, value it must not print)
MUST_FAIL = {
    "aws key in path": (entry('"/s3/AKIAIOSFODNN7EXAMPLE/list"'),
                        "url_pattern has a path segment shaped like a token", "AKIA"),
    "16-hex key in path": (entry('"/api/k/3f9a1c7e2b4d6f80/items"'),
                           "url_pattern has a path segment shaped like a token", "3f9a1c7e"),
    "uuid in path": (entry('"/sess/550e8400-e29b-41d4-a716-446655440000/items"'),
                     "url_pattern has a path segment shaped like a token", "550e8400"),
    "session id in path": (entry("/sess/a3k9vq2m7x1zp4w8r6t0y5u2ns/items"),
                           "url_pattern has a path segment shaped like a token", "a3k9vq2m"),
    "token in a path placeholder": (
        entry("/repos/{ghs_16C7e42F292c6912E7710c838347Ae178B4a}/x"),
        "url_pattern has a {placeholder} that is not a short lower-case name", "16C7e42F"),
    "token in a query placeholder": (entry('"/x?sid={Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1J}"'),
                                     "url_pattern has a {placeholder} that is not", "Q7xk2"),
    "session id as a placeholder name": (entry('"/s/{el4ukv0kqbvoirg7nkp4dncpk3}/x"'),
                                         "url_pattern has a {placeholder} that is not",
                                         "el4ukv0k"),
    "session id as a query placeholder": (entry('"/x?PHPSESSID={el4ukv0kqbvoirg7nkp4dncpk3}"'),
                                          "url_pattern has a {placeholder} that is not",
                                          "el4ukv0k"),
    "hex as a placeholder name": (entry('"/x?sid={deadbeefcafebabe}"'),
                                  "url_pattern has a {placeholder} that is not", "deadbeef"),
    "stripe key as a placeholder name": (entry('"/x/{sk_live_abcdefghijklmnopqrstu}"'),
                                         "url_pattern has a {placeholder} that is not",
                                         "sk_live"),
    "long number as a query value": (entry('"/x?otp=48291736501"'),
                                     "query 'otp' needs a {placeholder} value", "48291736501"),
    "fragment": (entry('"/cb#access_token=s3cr3t.T0k3n.v4lue"'),
                 "url_pattern has a fragment", "s3cr3t"),
    "query without =": (entry('"/issues?s3cr3tT0ken99"'),
                        "has a query key that is not a plain name", "s3cr3t"),
    "plain query key without =": (entry('"/issues?draft"'),
                                  "query 'draft' needs a {placeholder} value", None),
    "query with ;": (entry('"/issues?q={q};sid=abc123xyz"'), "query uses ';'", "abc123"),
    "placeholder as query key": (entry('"/issues?q={q}&{api_key}=x"'),
                                 "has a query key that is not a plain name", "api_key"),
    "secret as query key": (entry('"/issues?sk-live-4f8a9b={v}"'),
                            "has a query key that is not a plain name", "sk-live"),
    "literal query value": (entry('"/issues?q=is:open&page={page}"'),
                            "query 'q' needs a {placeholder} value", "is:open"),
    "token as host label": (entry('"https://tok-a1b2c3d4e5.api.example.com/x"'),
                            "has a host label shaped like a token", "tok-a1b2"),
    "user and password": (entry('"https://user:pa55word@api.example.com/x"'),
                          "carries a user or password before the host", "pa55word"),
    "token as port": (entry('"https://api.example.com:abc123tok/x"'),
                      "host or port that does not parse", "abc123tok"),
    "port out of range": (entry('"https://api.example.com:99999/x"'),
                          "host or port that does not parse", "99999"),
    "unparsable host": (entry('"https://[Q7xk2Lm9Rt4Vw8Zp3/x"'),
                        "host or port that does not parse", "Q7xk2"),
    "dict in returns": (entry(extra='      returns: [{Authorization: "Bearer ab12cd34ef56"}]\n'),
                        "returns is not a list of strings", "ab12cd34"),
    "token in returns": (entry(extra='      returns: ["csrf a1b2c3d4e5f6g7h8"]\n'),
                         "returns holds something that is not a response key name", "a1b2c3"),
    "dict as url_pattern": (entry('{path: /x, cookie: "sid=abc123def456ghi789jkl012mno"}'),
                            "url_pattern is not a string", "abc123"),
    "dict in inputs": (entry(extra="      inputs: [{cookie: abc}]\n"),
                       "inputs is not a list of strings", "cookie"),
    "secret as name": (entry(name='"sid=9f8e7d6c5b4a"'),
                       "name is not a snake_case identifier", "9f8e7d"),
    "description is free text": (entry(extra='      description: "send sid%3D9f8e7d6c5b4a"\n'),
                                 "description is not an endpoint key", "9f8e7d"),
    "header as a key": (entry(extra='      Cookie: "sid=9f8e7d6c5b4a"\n'),
                        "Cookie is not an endpoint key", "9f8e7d"),
    "yaml merge key": (entry(extra='      <<: {cookie: "sid=Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1Jd5"}\n'),
                       "cookie is not an endpoint key", "Q7xk2"),
    "token pasted as a key": (entry(extra=f'      "{FAKE_TOKEN}": 1\n'),
                              "<not shown> is not an endpoint key", FAKE_TOKEN),
    "cookie in a gotcha": (entry(extra=(
        '  gotchas:\n    - "views.json returned 403 until Cookie: user_session='
        'Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1J was sent"\n')), "gotchas holds a secret header", "Q7xk2"),
    "json header in a gotcha": (entry(extra=(
        "  gotchas:\n    - 'send {\"x-api-key\": \"Kx81Pq92abc\"}'\n")),
        "gotchas holds a secret header", "Kx81Pq92"),
    "json cookie in a gotcha": (entry(extra=(
        "  gotchas:\n    - \"needs {'cookie': 'sid=abcdefgh'}\"\n")),
        "gotchas holds a secret header", "abcdefgh"),
    "multi-line cookie in a gotcha": (entry(extra=(
        "  gotchas:\n    - |\n      works only with\n      Cookie:\n        sid=9f8e7d6c5b4a\n")),
        "gotchas holds a secret header", "9f8e7d"),
    "bearer in a gotcha": (entry(extra='  gotchas:\n    - "Authorization: Bearer abc1234"\n'),
                           "gotchas holds a secret header", "abc1234"),
    "basic credentials in a gotcha": (entry(extra=(
        '  gotchas:\n    - "log in with Basic dXNlcjpwYXNzd29yZA"\n')),
        "gotchas holds a secret header", "dXNlcj"),
    "github token in a gotcha": (entry(extra=(
        '  gotchas:\n    - "ghs_16C7e42F292c6912E7710c838347Ae178B4a works"\n')),
        "gotchas holds a secret header", "16C7e42F"),
    "gotchas as one string": (entry(extra=(
        '  gotchas: "403 until Cookie: user_session=Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1J"\n')),
        "gotchas is not a list of strings", "Q7xk2"),
    "dict in gotchas": (entry(extra=(
        '  gotchas:\n    - {views.json: "Cookie: user_session=Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1J"}\n')),
        "gotchas is not a list of strings", "Q7xk2"),
    "secret in settings": (entry(extra=(
        '  settings: {note: "Cookie: user_session=Q7xk2Lm9Rt4Vw8Zp3Nc6Hb1J"}\n')),
        "settings holds a secret header", "Q7xk2"),
    "undeclared effect": (entry(effect="sideways"), "effect is not one of", None),
    "input that is no element": (entry(extra="      inputs: [gone-input]\n"),
                                 "inputs names 'gone-input'", None),
}


class CheckEndpointsTest(unittest.TestCase):
    def test_a_clean_block_passes(self):
        done = check(CLEAN)
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("[endpoints] ok", done.stdout)

    def test_every_legitimate_api_shape_passes(self):
        for body in LEGITIMATE:
            with self.subTest(body.splitlines()[3]):
                done = check(body)
                self.assertEqual(done.returncode, 0, done.stdout)

    def test_ordinary_gotcha_prose_passes(self):
        done = check(CLEAN + "  gotchas:\n"
                     + "".join(f'    - "{g}"\n' for g in GOTCHA_PROSE))
        self.assertEqual(done.returncode, 0, done.stdout)

    def test_every_bypass_is_refused_without_its_value(self):
        for probe, (body, failure, value) in MUST_FAIL.items():
            with self.subTest(probe):
                done = check(body)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn(failure, done.stdout)
                self.assertNotIn("Traceback", done.stderr)
                if value:
                    self.assertNotIn(value, done.stdout + done.stderr)

    def test_a_page_that_does_not_parse_prints_no_value(self):
        done = check(CLEAN + '    - name: "x\n      sid: 9f8e7d6c5b4aQ7xk\n')
        self.assertNotIn("Traceback", done.stderr)
        self.assertNotIn("9f8e7d6c5b4aQ7xk", done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
