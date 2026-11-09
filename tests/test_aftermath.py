"""Aftermath rendering tests (Phase 0, Bug 1): the week report must
render end-to-end with evidence present. The v0.3.0 grouped COUNT query
lost class/kind and crashed _md_proof/_html_proof with KeyError."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from test_plumbing import DhritiTestCase, daily_payload


class TestWeekReport(DhritiTestCase):
    def _seed_week(self):
        """One sealed day, one session, one machine-checked command
        accepted — enough evidence to crash the old renderer."""
        self.seal_today()
        day = self.days.ensure_day(self.today)
        self.days.try_open(day)
        session = self.sessions.start(day["id"], "the task",
                                      '[{"kind":"command"}]')
        self.sessions.seal(session["id"])
        self.sessions.arming(session["id"])
        self.sessions.activate(session["id"])
        ev = self.evidence.machine_check_command(
            session["id"], "python3 -c \"print('ok')\"")
        self.assertEqual(ev["verdict"], "ACCEPTED")

    def test_week_report_renders(self):
        """Bug 1: week report with evidence raises KeyError('class')
        on the v0.3.0 grouped query."""
        self._seed_week()
        report = self.aftermath.week_report(self.today.isoformat())
        md = report["markdown"]
        self.assertIn("MACHINE_CHECKED/command", md)
        # html renders too (same data, second renderer)
        self.assertIn("MACHINE_CHECKED/command", report["html"])

    def test_day_report_renders_with_evidence(self):
        self._seed_week()
        day = self.days.get(self.today)
        report = self.aftermath.day_report(day)
        self.assertIn("MACHINE_CHECKED/command", report["markdown"])


if __name__ == "__main__":
    unittest.main()
