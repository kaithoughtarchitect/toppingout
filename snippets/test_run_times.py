"""Tests for run_times.py. Stdlib only:  python test_run_times.py"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_times  # noqa: E402

WHOLE = "tests/a.py ....\n============ 100 passed, 2 failed, 3 skipped in 600.00s (0:10:00) ============\n"
PART = "tests/a.py ..\n=================== 10 passed in 60.50s ===================\n"
UNIT = "......\n----------------------------------------------------------------------\nRan 6 tests in 1.5s\n\nOK\n"
DUR = ("============================ slowest 30 durations =============================\n"
       "12.50s call     tests/x.py::test_slow\n0.40s setup    tests/y.py::test_fast\n" + WHOLE)


class TestTime(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def put(self, rel, text):
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def test_whole_and_other_split_and_copies_count_once(self):
        self.put("t0/g1.txt", WHOLE)
        self.put("bvh/saved-base/base.txt", WHOLE)          # an identical copy: one run, not two
        self.put("wo1/affected.txt", PART)
        out = run_times.report([self.d])
        self.assertIn("runs 2, 0:11 in all", out)
        self.assertIn("whole-suite runs 1, 0:10", out)
        self.assertIn("other runs 1, 0:01", out)

    def test_unittest_summary_and_files_without_a_run(self):
        self.put("a/unit.txt", UNIT)
        self.put("a/report.txt", "WORK ORDER 3 DONE\n")
        self.assertIn("runs 1,", run_times.report([self.d]))

    def test_slowest_tests_from_durations(self):
        self.put("t-final/g1.txt", DUR)
        out = run_times.report([self.d])
        self.assertIn("12.50s tests/x.py::test_slow", out)
        self.assertLess(out.index("test_slow"), out.index("test_fast"))

    def test_counts_exclude_skipped(self):
        self.assertEqual(run_times.run_of(WHOLE), (102, 600.0))

    def test_empty_and_bad_folder(self):
        self.assertEqual(run_times.report([self.d]), "runs 0")
        self.assertEqual(run_times.main([str(self.d / "nope")]), 2)


if __name__ == "__main__":
    unittest.main()
