"""Bootcamp evidence + taper computation (never by date alone)."""

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
        sess = self.sessions.start(day["id"], "t", "")
        self.sessions.seal(sess["id"])
        self.sessions.arming(sess["id"])
        self.sessions.activate(sess["id"])
        self.db.insert("evidence", {
            "id": "ev1", "session_id": sess["id"], "class": "SUBMITTED",
            "kind": "file", "submitted_at": self.clock.iso(),
            "detail_json": "{}", "verdict": "ACCEPTED",
            "verdict_reason": "test", "checked_at": self.clock.iso()})
        self.sessions.end_success(sess["id"])
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
            handle = self.break_glass.initiate()
            self.clock.advance(minutes=1)
            self.break_glass.confirm(handle["handle"],
                                     f"reason number {i} is long enough")
            self.clock.advance(hours=3)
        rec = self.bootcamp.compute_taper()
        self.assertEqual(rec["reason"],
                         "break-glass frequency above threshold")


if __name__ == "__main__":
    unittest.main()
