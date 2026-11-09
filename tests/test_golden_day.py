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
            # §9.4: the demo exercises the v0.4/v0.5/v0.6 surfaces —
            # health lines, a backup, a vidura line
            ok_lines = [line for line in proc.stdout.splitlines()
                        if line.startswith("health: [ok  ]")]
            self.assertGreaterEqual(len(ok_lines), 3,
                                    f"health [ok  ] lines: {ok_lines}")
            self.assertIn("backup:", proc.stdout)
            self.assertIn("vidura:", proc.stdout)
            self.assertIn("journal:", proc.stdout)
            # real artifacts on disk
            self.assertTrue((out / "dhriti.sqlite3").exists())
            reports = list((out / "reports").glob("aftermath-*.html"))
            self.assertTrue(reports, "no aftermath report written")
            self.assertTrue((out / "ledger_export.json").exists())


if __name__ == "__main__":
    unittest.main()
