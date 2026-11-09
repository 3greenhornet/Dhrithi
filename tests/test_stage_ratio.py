"""D-046 — the stage ratio: the subject's own metric (audience share of
observed navigation), computed deterministically, shown in the
aftermath and the digest, never judged by the software."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhriti.aftermath import AftermathService
from dhriti.ledger import Ledger
from dhriti.stage_ratio import (DEFAULT_AUDIENCE_BAND, consumption_category,
                                drift_split, profile_navigation,
                                stage_ratio)
from dhriti.timeutil import SimulatedClock

from test_plumbing import DhritiTestCase, daily_payload, make_config


class TestClassification(unittest.TestCase):
    def test_consumption_domains_classified(self):
        self.assertEqual(consumption_category(
            "https://www.youtube.com/watch?v=x"), "video")
        self.assertEqual(consumption_category(
            "https://m.youtube.com/shorts/x"), "video")
        self.assertEqual(consumption_category(
            "https://chatgpt.com/c/abc"), "ai_chat")
        self.assertEqual(consumption_category(
            "https://www.reddit.com/r/all"), "social")

    def test_work_and_neutral_domains_are_not_consumption(self):
        # google.com is the Specimen-001 lesson: the domain search needs
        # can never be category-blocked; it is not consumption either.
        self.assertIsNone(consumption_category(
            "https://www.google.com/search?q=x"))
        self.assertIsNone(consumption_category(
            "https://docs.oracle.com/en/java/"))
        self.assertIsNone(consumption_category(""))
        self.assertIsNone(consumption_category("not a url"))


class TestRatio(unittest.TestCase):
    def test_no_observation_is_missing_not_zero(self):
        ratio = stage_ratio({"total": 0, "consumption": 0})
        self.assertFalse(ratio["observed"])
        self.assertIsNone(ratio["audience_share"])  # MISSING != on stage

    def test_share_math_against_the_endorsed_band(self):
        ratio = stage_ratio({"total": 10, "consumption": 2})
        self.assertEqual(ratio["audience_share"], 0.2)
        self.assertTrue(ratio["within_band"])       # 20-30% band edge
        ratio = stage_ratio({"total": 10, "consumption": 9})
        self.assertEqual(ratio["audience_share"], 0.9)  # his own estimate
        self.assertFalse(ratio["within_band"])
        self.assertEqual(DEFAULT_AUDIENCE_BAND, (0.2, 0.3))


class TestWholeDayProfile(DhritiTestCase):
    def test_navigation_split_window_before_after(self):
        day = self.days.ensure_day(self.today)
        # window on 2026-11-02: 04:30 .. 15:30 UTC (10:00 .. 21:00 IST)
        stamps = [
            ("2026-11-02T03:00:00Z", "https://github.com/x"),     # before
            ("2026-11-02T05:00:00Z", "https://www.youtube.com"),  # in window
            ("2026-11-02T05:30:00Z", "https://docs.oracle.com"),  # in window
            ("2026-11-02T16:00:00Z", "https://chatgpt.com"),      # evening
        ]
        for when, url in stamps:
            self.ledger.record(
                "browser_navigation", source_adapter="extension",
                occurred_at_utc=when,
                observed_payload={"url": url, "title": ""})
        profile = profile_navigation(self.db, self.config, self.today, day)
        self.assertEqual(profile["total"], 4)
        self.assertEqual(profile["consumption"], 2)
        self.assertEqual(profile["before_window"], 1)
        self.assertEqual(profile["in_window"], 2)
        self.assertEqual(profile["after_window"], 1)         # the evening
        self.assertEqual(profile["consumption_after_window"], 1)
        ratio = stage_ratio(profile)
        self.assertEqual(ratio["audience_share"], 0.5)

    def test_events_from_other_days_excluded(self):
        day = self.days.ensure_day(self.today)
        self.ledger.record(
            "browser_navigation", source_adapter="extension",
            occurred_at_utc="2026-11-05T05:00:00Z",
            observed_payload={"url": "https://www.youtube.com"})
        profile = profile_navigation(self.db, self.config, self.today, day)
        self.assertEqual(profile["total"], 0)


class TestAftermathAndDigestBlocks(DhritiTestCase):
    def test_day_report_carries_the_ratio_in_his_vocabulary(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        for when, url in (
                ("2026-11-02T05:00:00Z", "https://www.youtube.com"),
                ("2026-11-02T05:30:00Z", "https://docs.oracle.com"),
                ("2026-11-02T16:00:00Z", "https://chatgpt.com"),
                ("2026-11-02T16:30:00Z", "https://chatgpt.com")):
            self.ledger.record(
                "browser_navigation", source_adapter="extension",
                occurred_at_utc=when,
                observed_payload={"url": url, "title": ""})
        clock = SimulatedClock()
        clock.set(self.clock.now_utc())
        aftermath = AftermathService(self.db, self.config, clock,
                                     self.ledger)
        md = aftermath.day_report(day)["markdown"]
        self.assertIn("Stage ratio", md)
        self.assertIn("Audience share of observed navigation", md)
        self.assertIn("(3 of 4 navigations)", md)
        self.assertIn("endorsed band", md)
        self.assertIn("20-30% audience", md)
        self.assertIn("counts, not minutes", md)
        # D-048: the split is visible
        self.assertIn("after window_end (evening)", md)

    def test_digest_carries_the_exchange_line(self):
        from dhriti.review import build_digest
        self.seal_today()
        day = self.days.ensure_day(self.today)
        self.ledger.record(
            "browser_navigation", source_adapter="extension",
            occurred_at_utc="2026-11-02T05:00:00Z",
            observed_payload={"url": "https://www.youtube.com"})
        text = build_digest(self.db, self.ledger,
                            self.today.isoformat(), clock=self.clock,
                            config=self.config)
        self.assertIn("stage ratio", text)
        self.assertIn("audience share of observed navigation", text)
        self.assertIn("endorsed band", text)
        self.assertIn("top consumption categories", text)
        self.assertIn("declared rest vs drift", text)


class TestDriftSplit(unittest.TestCase):
    def test_inside_vs_outside_declared_windows(self):
        declarations = [
            {"created_at": "2026-11-02T16:00:00Z",
             "ends_at": "2026-11-02T16:45:00Z"},
        ]
        events = [
            ("2026-11-02T16:10:00Z", "video"),    # inside -> rest
            ("2026-11-02T18:00:00Z", "ai_chat"),  # outside -> drift
            ("2026-11-02T12:00:00Z", "social"),   # outside -> drift
        ]
        split = drift_split(events, declarations)
        self.assertEqual(split["declared_rest"], 1)
        self.assertEqual(split["drift"], 2)

    def test_no_declarations_means_all_drift(self):
        split = drift_split([("2026-11-02T16:10:00Z", "video")], [])
        self.assertEqual(split["drift"], 1)
        self.assertEqual(split["declared_rest"], 0)


if __name__ == "__main__":
    unittest.main()
