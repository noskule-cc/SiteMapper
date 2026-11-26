import io
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import store_login  # noqa: E402

PERSONA = """persona:
  name: bot
  auth: automated
  credential_ref:
    username: keyring:SiteMapper/bot-user
    password: keyring:SiteMapper/bot
"""


class StoreLoginTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "sites" / "s" / "personas").mkdir(parents=True)
        (root / "sites" / "s" / "personas" / "bot.yaml").write_text(PERSONA, encoding="utf-8")
        self.root = root
        self.vault = {}
        fake = types.SimpleNamespace(
            set_password=lambda s, n, v: self.vault.__setitem__((s, n), v))
        self.patch = mock.patch.dict(sys.modules, {"keyring": fake})
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def run_main(self, user, password):
        out = io.StringIO()
        with mock.patch("builtins.input", return_value=user) as asked_user, \
                mock.patch("getpass.getpass", return_value=password) as asked_pw, \
                redirect_stdout(out):
            code = store_login.main(["s", "bot", "--root", str(self.root)])
        return code, out.getvalue(), asked_user, asked_pw

    def test_asks_username_in_clear_and_password_hidden(self):
        code, out, asked_user, asked_pw = self.run_main("alice", "s3cret")
        self.assertEqual(code, 0)
        asked_user.assert_called_once_with("Username: ")
        asked_pw.assert_called_once_with("Password (hidden): ")
        self.assertEqual(self.vault, {("SiteMapper", "bot-user"): "alice",
                                      ("SiteMapper", "bot"): "s3cret"})

    def test_never_prints_a_value(self):
        _, out, _, _ = self.run_main("alice", "s3cret")
        self.assertNotIn("alice", out)
        self.assertNotIn("s3cret", out)

    def test_empty_input_stores_nothing(self):
        code, _, _, _ = self.run_main("", "s3cret")
        self.assertEqual(code, 2)
        self.assertEqual(self.vault, {})


if __name__ == "__main__":
    unittest.main()
