"""check.py's deployment_names: a map repository's denylist guards the
framework's tracked files, and the framework itself carries no list (#81)."""
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

CHECK = Path(__file__).resolve().parent.parent / "scripts" / "check.py"
IN_THE_FRAMEWORK = "two roots, deliberately"  # a comment in check.py itself


def check(denylist: str | None) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        if denylist is not None:
            (Path(tmp) / "framework-denylist.txt").write_text(denylist, encoding="utf-8")
        return subprocess.run([sys.executable, str(CHECK), "--root", tmp,
                               "--only", "deployment_names"],
                              capture_output=True, encoding="utf-8", timeout=60,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})


class DeploymentNamesTest(unittest.TestCase):
    def test_a_listed_term_in_a_framework_file_fails_without_showing_it(self):
        proc = check(f"# names\n{IN_THE_FRAMEWORK.upper()}\n")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("framework scripts/check.py:", proc.stdout)
        self.assertNotIn(IN_THE_FRAMEWORK, proc.stdout.lower())

    def test_terms_the_framework_lacks_pass(self):
        absent = uuid.uuid4().hex  # a literal here would put the term in a tracked file
        proc = check(f"# a comment-only line\n{absent}\n")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("[deployment_names] ok", proc.stdout)

    def test_a_map_repository_without_a_denylist_or_terms_skips(self):
        for denylist in (None, "# only a comment\n"):
            proc = check(denylist)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertIn("[deployment_names] skipped", proc.stdout)


if __name__ == "__main__":
    unittest.main()
