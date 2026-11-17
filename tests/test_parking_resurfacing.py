"""Parking lot resurfacing (v0.6.0): the parking lot as the
inversion of the feed — capture, evening surfacing, age-based
resurfacing, anti-drift, approved-to-contract, break-glass linkage."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from dhriti.timeutil import parse_iso
from dhriti.models import SessionState

from test_plumbing import DhritiTestCase, daily_payload


class TestKinds(DhritiTestCase):
    def test_four_kinds_accepted(self):
        for kind in ("question", "resource", "desire", "association"):
            self.parking.park("q", kind=kind)

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.parking.park("q", kind="junk")
        self.assertIn("kind must be one of", str(ctx.exception))

    def test_sparked_by_url_recorded(self):
        self.parking.park("the thing",
                          sparked_by_url="https://youtube.com/x")
        events = self.ledger.events(event_type="curiosity_topic_parked")
        self.assertIn("https://youtube.com",
                      events[0]["observed_payload"])


class TestEvening(DhritiTestCase):
    def test_evening_returns_today_items_only(self):
        today = self.clock.now_utc().strftime("%Y-%m-%d")
        self.parking.park("today q")
        self.clock.advance(days=1)
        # park a second item tomorrow
        self.parking.park("tomorrow q")
        items = self.parking.evening(today)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["question"], "today q")

    def test_evening_surface_records_event(self):
        today = self.clock.now_utc().strftime("%Y-%m-%d")
        self.parking.park("q1")
        self.parking.park("q2")
        items = self.parking.surface_evening(today)
        self.assertEqual(len(items), 2)
        events = self.ledger.events(
            event_type="parking_evening_surfaced")
        self.assertEqual(len(events), 1)
        self.assertIn('"count":2', events[0]["observed_payload"])

    def test_evening_surface_idempotent(self):
        today = self.clock.now_utc().strftime("%Y-%m-%d")
        self.parking.park("q")
        first = self.parking.surface_evening(today)
        second = self.parking.surface_evening(today)
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])


class TestResurfacingOlder(DhritiTestCase):
    def test_older_than_finds_aged_items(self):
        self.parking.park("aged q")
        self.clock.advance(days=5)
        items = self.parking.older_than(3)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["question"], "aged q")

    def test_surface_review_marks_and_records(self):
        self.parking.park("aged q")
        self.clock.advance(days=5)
        items = self.parking.surface_review(min_age_days=3)
        self.assertEqual(len(items), 1)
        # already marked, so second call returns nothing
        second = self.parking.surface_review(min_age_days=3)
        self.assertEqual(second, [])

    def test_disposed_items_not_resurfaced(self):
        row = self.parking.park("disposed q")
        self.parking.dispose(row["id"], "dropped",
                             note="read it, done with it")
        self.clock.advance(days=5)
        self.assertEqual(self.parking.older_than(3), [])


class TestApprovedToContract(DhritiTestCase):
    def test_approved_item_link_recorded(self):
        row = self.parking.park("to approve")
        self.parking.dispose(row["id"], "approved")
        self.days.ensure_day("2026-11-03")
        self.parking.dispose_approved_to_contract(row["id"],
                                                  "2026-11-03")
        events = self.ledger.events(
            event_type="parking_approved_to_contract")
        self.assertEqual(len(events), 1)

    def test_sealed_contract_refused(self):
        row = self.parking.park("to approve")
        self.parking.dispose(row["id"], "approved")
        self.seal_today()
        with self.assertRaises(ValueError) as ctx:
            self.parking.dispose_approved_to_contract(
                row["id"], "2026-11-02")
        self.assertIn("already sealed", str(ctx.exception))

    def test_unapproved_item_refused(self):
        row = self.parking.park("not approved yet")
        self.days.ensure_day("2026-11-03")
        with self.assertRaises(ValueError):
            self.parking.dispose_approved_to_contract(
                row["id"], "2026-11-03")


class TestAntiDrift(DhritiTestCase):
    def test_flood_detected(self):
        for i in range(10):
            self.parking.park(f"q{i}")
        anti = self.parking.anti_drift()
        self.assertTrue(anti["flood"])
        self.assertEqual(len(self.ledger.events(
            event_type="parking_flood")), 1)

    def test_graveyard_detected(self):
        # the mechanism's threshold is 5 undisposed 30+ day items; the
        # spec's example parked one — recorded in DECISIONS_PROPOSED.
        for i in range(5):
            self.parking.park(f"old q {i}")
        self.clock.advance(days=35)
        anti = self.parking.anti_drift()
        self.assertTrue(anti["graveyard"])
        self.assertEqual(anti["graveyard_count"], 5)
        self.assertEqual(len(self.ledger.events(
            event_type="parking_graveyard")), 1)


class TestAftermathIntegration(DhritiTestCase):
    def test_evening_block_when_earned(self):
        self.seal_today()
        day = self.days.today()
        day = self.days.try_open(
            day, self.contracts.for_day(day["date"]))
        self.parking.park("the thing that popped up", kind="question",
                          sparked_by_url="https://youtube.com/x")
        self.parking.surface_evening("2026-11-02")
        # simulate targets met by setting directly
        self.db.execute("UPDATE day SET targets_met=1 WHERE date=?",
                        ("2026-11-02",))
        md = self.aftermath.day_report("2026-11-02")["md"]
        self.assertIn("## The evening is yours", md)
        self.assertIn("[question] the thing that popped up", md)
        self.assertIn("sparked by: https://youtube.com/x", md)

    def test_no_evening_block_when_not_earned(self):
        self.seal_today()
        self.parking.park("q")
        md = self.aftermath.day_report("2026-11-02")["md"]
        self.assertNotIn("## The evening is yours", md)

    def test_week_report_lists_older_items_with_age(self):
        self.parking.park("aged")
        self.clock.advance(days=5)
        md = self.aftermath.week_report("2026-11-02")["md"]
        self.assertIn("[question] aged (5 days)", md)


class TestBreakGlassFromParked(DhritiTestCase):
    def test_break_links_to_parked_item(self):
        session = self.sessions.create("d1", "c1")
        self.walk_to_active(session["id"])
        row = self.parking.park("curiosity to explore")
        rec = self.breaks.initiate(session["id"])
        self.clock.advance(seconds=70)
        self.breaks.confirm(
            rec["id"], "want to explore a parked curiosity",
            session_finish=lambda sid: self.sessions.finish(
                sid, SessionState.BREAK_GLASS),
            parked_item_id=row["id"])
        events = self.ledger.events(
            event_type="break_glass_confirmed")
        self.assertIn(row["id"], events[0]["observed_payload"])


if __name__ == "__main__":
    unittest.main()
