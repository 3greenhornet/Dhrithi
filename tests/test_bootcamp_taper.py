"""Bootcamp evidence + taper computation (never by date alone)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from dhriti.models import TaperStage

from test_plumbing import DhritiTestCase, daily_payload


class TestBootcamp(DhritiTestCase):
    def test_start_requires_valid_length(self):
        with self.assertRaises(ValueError):
            self.bootcamp.start(45)
        bc = self.bootcamp.start(30)
        self.assertEqual(bc["planned_days"], 30)

    def test_no_double_bootcamp(self):
        self.bootcamp.start(30)
        with self.assertRaises(ValueError):
            self.bootcamp.start(60)

    def test_no_taper_before_min_days(self):
        self.bootcamp.start(30)
        rec = self.bootcamp.compute_taper()
        self.assertEqual(rec["recommended_stage"], TaperStage.FULL_LOCK)
        self.assertIn("fewer than", rec["reason"])

    def test_taper_needs_evidence_thresholds(self):
        self.bootcamp.start(30)
        self.clock.advance(days=31)
        # no days, no sessions -> thresholds not met
        rec = self.bootcamp.compute_taper()
        self.assertEqual(rec["recommended_stage"], TaperStage.FULL_LOCK)
        self.assertEqual(rec["reason"], "evidence thresholds not met")

    def test_taper_with_good_evidence(self):
        self.seal_today()
        self.bootcamp.start(30)
        day = self.days.ensure_day(self.today)
        from dhriti.models import DayState
        self.db.update("day", day["id"], {
            "state": DayState.CLOSED_COMPLETE.value, "targets_met": 1})
        # a successful session with accepted evidence
        contract = self.contracts.for_day(self.today.isoformat())
        sess = self.sessions.create(day["id"], contract["id"], "t")
        self.walk_to_active(sess["id"])
        self.db.insert("evidence", {
            "id": "ev1", "session_id": sess["id"], "class": "SUBMITTED",
            "kind": "file", "submitted_at": self.clock.iso(),
            "detail_json": "{}", "verdict": "ACCEPTED",
            "verdict_reason": "test", "checked_at": self.clock.iso()})
        from dhriti.models import SessionState
        self.sessions.finish(sess["id"], SessionState.SUCCESS)
        self.clock.advance(days=31)
        rec = self.bootcamp.compute_taper()
        self.assertEqual(rec["reason"], "evidence thresholds met")
        self.assertEqual(rec["recommended_stage"], 2)

    def test_break_glass_frequency_blocks_taper(self):
        self.bootcamp.start(30)
        self.clock.advance(days=31)
        # two confirmed breaks in the last week (cooldown respected:
        # 3h passes between them, both stay inside the 7-day window)
        for i in range(2):
            record = self.breaks.initiate(None)
            self.clock.advance(minutes=1)
            self.breaks.confirm(record["id"],
                                f"reason number {i} is long enough")
            self.clock.advance(hours=3)
        rec = self.bootcamp.compute_taper()
        self.assertEqual(rec["reason"],
                         "break-glass frequency above threshold")


if __name__ == "__main__":
    unittest.main()


class TestBootcampRestart(DhritiTestCase):
    def test_restart_does_not_count_old_days(self):
        """Bug 4 (Phase 0): a restarted bootcamp must not inherit the
        previous bootcamp's days and sessions."""
        # bootcamp 1 with a compliant day
        self.bootcamp.start(30)
        self.seal_today()
        day = self.days.ensure_day(self.today)
        self.days.try_open(day)
        contract = self.contracts.for_day(self.today.isoformat())
        session = self.sessions.create(day["id"], contract["id"], "t1")
        self.walk_to_active(session["id"])
        from dhriti.models import SessionState
        self.sessions.finish(session["id"], SessionState.SUCCESS)
        self.clock.advance(days=40)
        self.bootcamp.graduate()
        # bootcamp 2 starts fresh: zero days inside its window
        self.bootcamp.start(30)
        summary = self.bootcamp.evidence_summary()
        self.assertEqual(summary["days_with_day"], 0)
        self.assertEqual(summary["proof_rate"], 0.0)
        self.assertEqual(summary["compliance_rate"], 0.0)
