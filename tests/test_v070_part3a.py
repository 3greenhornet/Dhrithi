"""v0.7.0 Part 3 tests, batch 1: the break-glass friction ladder
(§3.11), the life mirror (§3.2), declared bounds (§3.3), the
search-escape detector (§3.4)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from dhriti.break_glass_friction import (FrictionLadder, TIERS,
                                         is_prose, word_count)
from dhriti.life_mirror import LifeMirrorService
from dhriti.search_escape import (SearchEscapeDetector,
                                  extract_query)
from dhriti.mirror.store import MirrorStore

from test_plumbing import DhritiTestCase, daily_payload


class TestProseCheck(unittest.TestCase):
    def test_word_count(self):
        self.assertEqual(word_count("one two three"), 3)

    def test_prose_requires_min_words(self):
        self.assertFalse(is_prose("too short", min_words=20))

    def test_prose_requires_substantial_words(self):
        # 20 one/two-char words: keysmash, not prose
        keysmash = " ".join(["ab"] * 20)
        self.assertFalse(is_prose(keysmash, min_words=20))

    def test_real_reason_is_prose(self):
        reason = ("I am opening the blocked site because the build "
                  "error links to a fix posted on the vendor forum "
                  "and the docs mirror is down today")
        self.assertTrue(is_prose(reason, min_words=20))


class TestTierComputation(DhritiTestCase):
    def _confirm_break(self, reason="a real reason long enough to "
                      "count as honest prose for the ladder"):
        record = self.breaks.initiate(None)
        self.clock.advance(seconds=70)
        self.breaks.confirm(record["id"], reason)

    def test_baseline_at_zero_breaks(self):
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        self.assertEqual(ladder.current_tier(), "baseline")

    def test_tier_rises_with_breaks(self):
        self.config["break_glass_friction"]["escalation"][
            "tier_up_after_breaks_in_30_days"] = 2
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        # 2 breaks (threshold * 1) -> tier 1: text
        for _ in range(2):
            self._confirm_break()
            self.clock.advance(hours=3)
        self.assertEqual(ladder.current_tier(), "text")
        # 4 breaks (threshold * 2) -> tier 2: communication
        for _ in range(2):
            self._confirm_break()
            self.clock.advance(hours=3)
        self.assertEqual(ladder.current_tier(), "communication")
        # 8+ breaks -> the cap: physical
        for _ in range(8):
            self._confirm_break()
            self.clock.advance(hours=3)
        self.assertEqual(ladder.current_tier(), "physical")

    def test_tier_decays_when_breaks_age_out(self):
        self._confirm_break()
        self.clock.advance(days=31)
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        self.assertEqual(ladder.confirmed_breaks_30d(), 0)
        self.assertEqual(ladder.current_tier(), "baseline")

    def test_month_summary_names_the_escalation(self):
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        summary = ladder.month_summary()
        self.assertEqual(summary["breaks_30d"], 0)
        self.assertEqual(summary["current_tier"], "baseline")


class TestLongText(DhritiTestCase):
    def test_long_text_round_trip(self):
        self.config["break_glass_friction"]["text"][
            "long_random_chars"] = 40
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        text = ladder.generate_long_text("break-1", 40)
        self.assertEqual(len(text), 40)
        self.assertTrue(ladder.verify_long_text("break-1", 40, text))
        self.assertFalse(ladder.verify_long_text("break-1", 40,
                                                 text + "x"))
        # deterministic per break: the same break shows the same text
        self.assertEqual(ladder.generate_long_text("break-1", 40),
                         text)


class TestOtp(DhritiTestCase):
    def test_otp_issue_verify_expiry_replay(self):
        self.config["break_glass_friction"]["communication"][
            "otp_enabled"] = True
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        issued = ladder.issue_otp("break-1")
        code = issued["code"]
        # wrong code fails
        self.assertFalse(ladder.verify_otp("break-1", "000000"))
        # right code passes
        self.assertTrue(ladder.verify_otp("break-1", code))
        # single-use: a replay fails
        self.assertFalse(ladder.verify_otp("break-1", code))
        # expiry: an old code fails
        issued2 = ladder.issue_otp("break-2")
        self.clock.advance(minutes=6)
        self.assertFalse(ladder.verify_otp("break-2",
                                           issued2["code"]))
        # the code itself never enters the ledger
        events = self.ledger.events()
        for row in events:
            self.assertNotIn(issued["code"],
                             row["observed_payload"])


class TestBarcode(DhritiTestCase):
    def test_barcode_register_and_verify(self):
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        ladder.register_barcode("KITCHEN-PANTRY-0042",
                                "the pantry barcode")
        self.assertTrue(ladder.verify_barcode(
            "KITCHEN-PANTRY-0042"))
        self.assertFalse(ladder.verify_barcode("WRONG-CODE"))
        # the code is stored hashed, never in the clear
        row = self.db.query_one("SELECT * FROM barcode")
        self.assertNotIn("KITCHEN-PANTRY-0042", row["code_hash"])


class TestLifeMirror(DhritiTestCase):
    def setUp(self):
        super().setUp()
        self.life = LifeMirrorService(self.db, self.config,
                                      self.clock, self.ledger)

    def test_declare_list_log_remove(self):
        alt = self.life.declare("the book on the corner", "reading",
                                "read 5 pages")
        self.assertTrue(alt["id"])
        self.assertEqual(len(self.life.list()), 1)
        logged = self.life.log(alt["id"])
        self.assertEqual(logged["occurrences"], ["2026-11-02"])
        self.life.remove(alt["id"])
        self.assertEqual(self.life.list(), [])

    def test_declare_rejects_duplicates_and_bad_kinds(self):
        self.life.declare("walk, no podcast", "movement")
        with self.assertRaises(ValueError):
            self.life.declare("walk, no podcast", "movement")
        with self.assertRaises(ValueError):
            self.life.declare("x", "not-a-kind")

    def test_log_is_idempotent_per_day(self):
        alt = self.life.declare("practice the interview aloud",
                                "speaking")
        self.life.log(alt["id"])
        self.life.log(alt["id"])
        self.assertEqual(len(self.life.get(alt["id"])
                             ["occurrences"]), 1)

    def test_week_facts_and_untouched(self):
        reading = self.life.declare("the book on the corner",
                                    "reading", "read 5 pages")
        speaking = self.life.declare("practice the interview aloud",
                                     "speaking")
        walking = self.life.declare("walk, no podcast", "movement")
        self.life.log(reading["id"])
        self.life.log(walking["id"])
        facts = self.life.week_facts("2026-11-02")
        self.assertEqual(facts["total_occurrences"], 2)
        untouched = self.life.untouched_this_week("2026-11-02")
        self.assertEqual(untouched, ["practice the interview "
                                     "aloud"])

    def test_aftermath_life_block(self):
        self.life.declare("the book on the corner", "reading",
                          "read 5 pages")
        self.seal_today()
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("## View: the Mirror", md)
        self.assertIn("The life (declared alternatives)", md)
        self.assertIn("the book on the corner", md)
        self.assertIn("logged 0 of 7 days", md)
        self.assertIn("shows the two numbers", md)

    def test_digest_life_line(self):
        from dhriti.review import build_digest_v070
        self.life.declare("the book on the corner", "reading")
        text = build_digest_v070(self.db, self.ledger,
                                 self.today.isoformat(),
                                 self.config, self.clock)
        self.assertIn("Life: 0 occurrence(s) logged", text)


class TestDeclaredBounds(DhritiTestCase):
    def test_evening_minutes_computed_with_stated_weight(self):
        # one evening navigation (after window_end) to youtube
        self.seal_today()
        self.clock.advance(hours=12)  # past window_end
        self.ledger.record(
            "browser_navigation", source_adapter="extension",
            occurred_at_utc=self.clock.iso(),
            observed={"url": "https://youtube.com/watch?v=x",
                      "title": ""})
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("Declared device bounds", md)
        self.assertIn("Declared bound: 60 minutes", md)
        # the weight is stated: 1 navigation * 3 min
        self.assertIn("3m", md)
        self.assertIn("(This is a measurement, not a verdict.", md)


class TestSearchEscape(DhritiTestCase):
    def test_extract_query(self):
        self.assertEqual(
            extract_query("https://www.google.com/search?q=motivation"),
            "motivation")
        self.assertEqual(
            extract_query("https://www.youtube.com/results?"
                          "search_query=system+design"),
            "system design")
        self.assertIsNone(
            extract_query("https://docs.oracle.com/en/java/"))

    def test_detector_joins_query_to_unopened_pile(self):
        store = MirrorStore(self.db, {"mirror": {}}, self.clock,
                            self.ledger)
        source = store.add_source("youtube_liked", "LL",
                                  "Liked Videos")
        store.upsert_item(source["id"], "v1",
                          "System Design Interview — full course")
        self.ledger.record(
            "browser_navigation", source_adapter="extension",
            occurred_at_utc=self.clock.iso(),
            observed={"url":
                      "https://www.google.com/search?q=system+design",
                      "title": ""})
        detector = SearchEscapeDetector(self.db, self.config,
                                        self.clock, self.ledger)
        escapes = detector.detect(self.today.isoformat())
        self.assertEqual(len(escapes), 1)
        self.assertEqual(escapes[0]["category"], "development")
        self.assertEqual(escapes[0]["unopened_count"], 1)
        # the week summary groups by query
        summary = detector.week_summary(self.today.isoformat())
        self.assertEqual(summary[0]["searches"], 1)

    def test_search_escape_line_in_the_record(self):
        self.config["mirror"]["enabled"] = True
        store = MirrorStore(self.db, self.config, self.clock,
                            self.ledger)
        source = store.add_source("youtube_liked", "LL",
                                  "Liked Videos")
        store.upsert_item(source["id"], "v1",
                          "Motivation — why discipline beats "
                          "motivation")
        self.seal_today()
        self.ledger.record(
            "browser_navigation", source_adapter="extension",
            occurred_at_utc=self.clock.iso(),
            observed={"url":
                      "https://duckduckgo.com/?q=motivation",
                      "title": ""})
        detector = SearchEscapeDetector(self.db, self.config,
                                        self.clock, self.ledger)
        detector.detect(self.today.isoformat())
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("Search escapes this week: 1", md)


if __name__ == "__main__":
    unittest.main()
