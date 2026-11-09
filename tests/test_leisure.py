"""D-047 — declared leisure: chosen rest vs drift. One-way, typed,
bounded; a label, never a permission. The aftermath shows the two
numbers side by side; the review asks only when a declaration exists."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhriti.aftermath import AftermathService
from dhriti.leisure import LeisureService, MAX_MINUTES
from dhriti.review import REVIEW_QUESTIONS
from dhriti.timeutil import SimulatedClock

from test_plumbing import DhritiTestCase


class TestDeclare(DhritiTestCase):
    def setUp(self):
        super().setUp()
        self.leisure = LeisureService(self.db, self.clock, self.ledger)

    def test_declare_records_activity_length_and_window(self):
        self.clock.set(self.clock.now_utc())
        row = self.leisure.declare("watching one episode, chosen",
                                   45, day_date="2026-11-02")
        self.assertEqual(row["planned_minutes"], 45)
        self.assertEqual(row["created_at"], self.clock.iso())
        self.assertEqual(row["ends_at"], "2026-11-02T05:15:00Z")
        self.assertIn("leisure_declared",
                      [e["event_type"] for e in self.ledger.events()])

    def test_declaration_is_typed_and_bounded(self):
        with self.assertRaises(ValueError):
            self.leisure.declare("   ", 45)
        with self.assertRaises(ValueError):
            self.leisure.declare("rest", 0)
        with self.assertRaises(ValueError):
            self.leisure.declare("rest", MAX_MINUTES + 1)
        with self.assertRaises(ValueError):
            self.leisure.declare("rest", "forever")
        # the honest maximum is allowed
        row = self.leisure.declare("a long evening, declared",
                                   MAX_MINUTES, day_date="2026-11-02")
        self.assertEqual(row["planned_minutes"], MAX_MINUTES)

    def test_label_not_permission_is_stated_in_the_event(self):
        self.leisure.declare("reading fiction", 30, day_date="2026-11-02")
        event = self.ledger.events(event_type="leisure_declared")[0]
        self.assertIn("not a permission", event["action_taken"])
        # the note field never enters the chain (deletion model)
        self.assertNotIn("note", event["observed_payload"])

    def test_for_day_and_between(self):
        self.leisure.declare("a", 30, day_date="2026-11-02")
        self.leisure.declare("b", 30, day_date="2026-11-03")
        self.assertEqual(len(self.leisure.for_day("2026-11-02")), 1)
        self.assertEqual(
            len(self.leisure.between("2026-11-02", "2026-11-09")), 2)


class TestAftermathLeisureBlock(DhritiTestCase):
    def test_declared_rest_next_to_drift_no_verdict(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        # declare 21:30-22:15 IST rest (16:00-16:45 UTC)
        self.db.insert("leisure_declaration", {
            "id": "l1", "created_at": "2026-11-02T16:00:00Z",
            "day_date": "2026-11-02",
            "activity": "one episode, chosen",
            "planned_minutes": 45,
            "ends_at": "2026-11-02T16:45:00Z",
            "note": ""})
        # one navigation inside the window, one outside (drift)
        for when, url in (("2026-11-02T16:10:00Z",
                           "https://www.youtube.com"),
                          ("2026-11-02T18:00:00Z",
                           "https://chatgpt.com")):
            self.ledger.record(
                "browser_navigation", source_adapter="extension",
                occurred_at_utc=when,
                observed={"url": url, "title": ""})
        clock = SimulatedClock()
        clock.set(self.clock.now_utc())
        aftermath = AftermathService(self.db, self.config, clock,
                                     self.ledger)
        md = aftermath.day_report(day["date"])["markdown"]
        self.assertIn("Declared rest vs drift", md)
        self.assertIn("one episode, chosen", md)
        self.assertIn("Declared rest: 1", md)
        self.assertIn("Drift: 1", md)

    def test_no_declarations_shows_the_honest_default(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        clock = SimulatedClock()
        clock.set(self.clock.now_utc())
        aftermath = AftermathService(self.db, self.config, clock,
                                     self.ledger)
        md = aftermath.day_report(day["date"])["markdown"]
        self.assertIn("no leisure declared", md)
        self.assertIn("Drift: 0", md)


class TestConditionalReviewQuestion(unittest.TestCase):
    def test_question_exists_and_the_six_core_stay(self):
        from dhriti.review import CONDITIONAL_QUESTIONS
        self.assertIn("leisure_honored", CONDITIONAL_QUESTIONS)
        keys = {k for k, _ in REVIEW_QUESTIONS}
        self.assertIn("competence_source", keys)
        # the question states the distinction, not a verdict
        prompt = CONDITIONAL_QUESTIONS["leisure_honored"]
        self.assertIn("declared", prompt.lower())


if __name__ == "__main__":
    unittest.main()
