"""Vidura: the spaced-review scheduler for the user's own answers
(v0.5.0). The SM-2 variant is tested against the exact behaviors
docs/VIDURA.md §3 documents."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from test_plumbing import DhritiTestCase, daily_payload


class TestScheduler(DhritiTestCase):
    def setUp(self):
        super().setUp()
        self.vidura = self.vidura
        self.item = self.vidura.add(
            "research_answer", "does Arrays.asList reverse in place?",
            "no; write the swap loop yourself")

    def test_add_schedules_for_tomorrow(self):
        self.assertEqual(self.item["reps"], 0)
        self.assertEqual(self.item["interval_days"], 0.0)
        self.assertEqual(self.item["ease_factor"], 2.5)
        # due tomorrow
        self.assertEqual(self.item["due_at"], "2026-11-03T04:30:00Z")

    def test_easy_first_review_is_one_day(self):
        """D-1: the first good or easy on a new item produces a 1-day
        interval; the SM-2 multiplication applies from the second
        review onward."""
        row = self.vidura.review(self.item["id"], "easy")
        self.assertEqual(row["interval_days"], 1.0)

    def test_good_first_review_is_one_day(self):
        row = self.vidura.review(self.item["id"], "good")
        self.assertEqual(row["interval_days"], 1.0)

    def test_second_review_is_not_six_days(self):
        """D-2: this is an SM-2 variant, not textbook SM-2. Textbook
        jumps to 6 days on the second review; this code jumps to
        interval * EF (~2.3 days)."""
        self.vidura.review(self.item["id"], "good")
        row = self.vidura.review(self.item["id"], "good")
        self.assertLess(row["interval_days"], 6)
        self.assertGreater(row["interval_days"], 2)

    def test_again_resets_reps_and_counts_lapse(self):
        self.vidura.review(self.item["id"], "good")
        row = self.vidura.review(self.item["id"], "again")
        self.assertEqual(row["reps"], 0)
        self.assertEqual(row["lapses"], 1)
        self.assertEqual(row["interval_days"], 1.0)

    def test_hard_grows_by_1_2(self):
        self.vidura.review(self.item["id"], "good")   # interval = 1
        row = self.vidura.review(self.item["id"], "hard")
        self.assertAlmostEqual(row["interval_days"], 1.2, places=3)

    def test_ef_bounds_hold(self):
        row = self.item
        for _ in range(30):
            row = self.vidura.review(row["id"], "hard")
            self.assertGreaterEqual(row["ease_factor"], 1.3)
            self.assertLessEqual(row["ease_factor"], 2.5)

    def test_due_returns_only_due_items(self):
        other = self.vidura.add("note", "q2", "a2")
        due_now = self.vidura.due("2026-11-02T23:59:59Z")
        self.assertEqual(len(due_now), 0)
        due_tomorrow = self.vidura.due("2026-11-03T23:59:59Z")
        self.assertEqual(len(due_tomorrow), 2)

    def test_invalid_grade_refused(self):
        with self.assertRaises(ValueError):
            self.vidura.review(self.item["id"], "meh")


class TestIngest(DhritiTestCase):
    def test_ingest_pass_answers(self):
        session = self.start_session()
        self.passes.open(session["id"], "the question", minutes=5)
        self.passes.return_pass("the answer, typed cold")
        items = self.vidura.ingest_pass_answers(self.today.isoformat())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "research_answer")
        self.assertEqual(items[0]["front"], "the question")
        self.assertEqual(items[0]["back"], "the answer, typed cold")

    def test_ingest_skips_unanswered_passes(self):
        session = self.start_session()
        self.passes.open(session["id"], "q", minutes=5)
        items = self.vidura.ingest_pass_answers(self.today.isoformat())
        self.assertEqual(items, [])

class TestIdentityLine(DhritiTestCase):
    def test_identity_line_is_not_ingested(self):
        """Bug B: the identity card was unsolvable — its 'front' was
        just a date. It is no longer a Vidura item."""
        self.config["vidura"]["enabled"] = True
        self.seal_today()
        contract = self.contracts.for_day(self.today.isoformat())
        with self.assertRaises(AttributeError):
            # the method no longer exists
            self.vidura.ingest_identity_line(contract)

    def test_identity_appears_at_top_of_day_report(self):
        self.seal_today()
        report = self.aftermath.day_report(self.today.isoformat())
        identity = self.contracts.for_day(
            self.today.isoformat())["payload"]["identity_statement"]
        md = report["md"]
        # the identity line comes before "Contract (written cold)"
        self.assertLess(md.index(identity), md.index("Contract (written cold)"))

    def test_ingest_records_identity_not_spaced_event(self):
        """The record shows the decision was made, not forgotten."""
        self.config["vidura"]["enabled"] = True
        self.seal_today()
        import argparse
        from dhriti.cli import cmd_vidura_ingest
        ctx = self.make_cli_context()
        try:
            cmd_vidura_ingest(
                argparse.Namespace(date=self.today.isoformat()), ctx)
        finally:
            ctx.close()
        events = self.ledger.events(
            event_type="vidura_identity_not_spaced")
        self.assertEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()
