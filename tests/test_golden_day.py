"""Golden-day fixture (toolkit #9): the shipped demo must run clean,
end to end, as a real subprocess — exit 0, real artifacts on disk."""
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestGoldenDay(unittest.TestCase):
    def test_demo_runs_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo-home"
            proc = subprocess.run(
                [sys.executable,
                 str(ROOT / "examples" / "demo" / "run_demo.py"),
                 "--home", str(out)],
                capture_output=True, text=True, timeout=180)
            self.assertEqual(proc.returncode, 0,
                             f"demo failed:\n{proc.stdout[-2000:]}\n"
                             f"{proc.stderr[-2000:]}")
            self.assertIn("DEMO COMPLETE", proc.stdout)
            # real artifacts on disk
            self.assertTrue((out / "dhriti.sqlite3").exists())
            reports = list((out / "reports").glob("aftermath-*.html"))
            self.assertTrue(reports, "no aftermath report written")
            self.assertTrue((out / "ledger_export.json").exists())


if __name__ == "__main__":
    unittest.main()
