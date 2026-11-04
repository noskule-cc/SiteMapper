"""sweep_runs: which expired run folders go and which stay."""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import tree  # noqa: E402

NOW = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)
LONG_AGO = "2026-11-01T12:00:00Z"


class SweepRunsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.runs = Path(tmp.name)

    def make_run(self, name, **fields):
        folder = self.runs / "SiteMapper" / "owner" / name
        folder.mkdir(parents=True)
        run = {"keep": "1d", "finished_at": LONG_AGO, **fields}
        (folder / "run.yaml").write_text(yaml.safe_dump({"run": run}), encoding="utf-8")
        return folder

    def test_expired_waiting_run_stays(self):
        folder = self.make_run("waiting", status="waiting")
        self.assertEqual(tree.sweep_runs(self.runs, now=NOW), [])
        self.assertTrue(folder.exists())

    def test_expired_answered_and_passed_runs_go(self):
        answered = self.make_run("answered", status="passed", answered_at=LONG_AGO)
        passed = self.make_run("passed", status="passed")
        removed = tree.sweep_runs(self.runs, now=NOW)
        self.assertCountEqual(removed, [answered, passed])
        self.assertFalse(answered.exists() or passed.exists())

    def test_answered_waiting_run_is_swept_from_the_answer(self):
        folder = self.make_run("answered", status="passed", finished_at="2026-11-05T11:00:00Z")
        self.assertEqual(tree.sweep_runs(self.runs, now=NOW), [])
        self.assertTrue(folder.exists())


if __name__ == "__main__":
    unittest.main()
