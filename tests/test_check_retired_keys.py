import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parent.parent / "scripts" / "check.py"


def check(policy: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "sites" / "demo"
        site.mkdir(parents=True)
        (site / "site.yaml").write_text(
            "site:\n  name: demo\n  base_url: https://demo.invalid\n"
            f"  settings:\n    policy:\n{policy}", encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(CHECK), "--root", tmp, "--only", "schema"],
            capture_output=True, text=True)


class RetiredPolicyKeyTest(unittest.TestCase):
    def test_safe_to_submit_forms_fails_and_names_the_fix(self):
        out = check("      safe_to_submit_forms: true\n")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("sites/demo/site.yaml: settings.policy.safe_to_submit_forms is retired"
                      " - delete it", out.stdout)

    def test_permissions_write_passes(self):
        out = check("      permissions: { write: ask }\n")
        self.assertEqual(out.returncode, 0, out.stdout)


if __name__ == "__main__":
    unittest.main()
