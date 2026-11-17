"""The saved-content mirror (v0.7.0 Part 3 §3.1): ingestion with a
mocked token endpoint, dedupe, re-save, categorization, surfacing,
recall, dismiss/abandon/open/complete, aged-out, one-per-day,
intensity degradation, wall count, the record block."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import unittest

from dhriti.mirror import (MirrorStore, SurfaceService,
                           YouTubeIngest, import_csv, OAuthError)
from dhriti.mirror import events as ev

from test_plumbing import DhritiTestCase, daily_payload


def mirror_config(**overrides):
    cfg = {"enabled": True,
           "ingestion_interval_minutes": 15,
           "max_items_per_ingestion": 500,
           "youtube": {
               "oauth_client_id_env": "DHRITI_YOUTUBE_CLIENT_ID",
               "oauth_client_secret_env":
                   "DHRITI_YOUTUBE_CLIENT_SECRET",
               "oauth_refresh_token_path": "youtube_refresh_token",
               "quota_budget_per_day": 8000},
           "surfacing": {"one_per_day": True,
                         "aged_out_after_days": 180,
                         "degrade_after_consecutive_dismissals": 5,
                         "degrade_to": "title_only",
                         "max_age_days_for_surfacing": 365},
           "decay": {"dismiss_penalty": 0.2, "open_boost": 0.3,
                     "completion_boost": 0.5,
                     "recall_failure_penalty": 0.4,
                     "recall_success_boost": 0.15},
           "privacy": {"store_descriptions": True}}
    cfg.update(overrides)
    return {"mirror": cfg}


class MirrorTestCase(DhritiTestCase):
    def setUp(self):
        super().setUp()
        self.config.update(mirror_config())
        self.store = MirrorStore(self.db, self.config, self.clock,
                                 self.ledger)
        self.source = self.store.add_source(
            "youtube_liked", "LL", "Liked Videos")

    def _seed(self, days_ago=0, title="Dynamic Programming — Full "
              "Course", external="v1"):
        row = self.store.upsert_item(self.source["id"], external,
                                     title)
        if days_ago:
            saved = (self.clock.now_utc()
                     - __import__("datetime").timedelta(
                         days=days_ago)).strftime(
                             "%Y-%m-%dT%H:%M:%SZ")
            self.db.execute(
                "UPDATE content_item SET saved_at_utc=? WHERE id=?",
                (saved, row["id"]))
        return self.store.get_item(row["id"])

    def _closed_day(self, targets_met=True):
        self.seal_today()
        day = self.days.today()
        day = self.days.try_open(day,
                                 self.contracts.for_day(day["date"]))
        # advance past window_end so the evening (surfacing) is live
        self.clock.advance(hours=12)
        self.db.execute("UPDATE day SET state='CLOSED_COMPLETE', "
                        "targets_met=? WHERE date=?",
                        (1 if targets_met else 0, day["date"]))
        return self.days.get(day["date"])


class TestIngest(MirrorTestCase):
    def test_save_and_dedupe(self):
        first = self.store.upsert_item(self.source["id"], "v1",
                                       "Dynamic Programming Course")
        again = self.store.upsert_item(self.source["id"], "v1",
                                       "Dynamic Programming Course")
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(again["times_resaved"], 0)
        self.assertEqual(len(self.ledger.events(
            event_type=ev.CONTENT_ITEM_SAVED)), 1)

    def test_resave_after_24h(self):
        self.store.upsert_item(self.source["id"], "v1", "DP Course")
        self.clock.advance(days=2)
        row = self.store.upsert_item(self.source["id"], "v1",
                                     "DP Course")
        self.assertEqual(row["times_resaved"], 1)
        self.assertEqual(len(self.ledger.events(
            event_type=ev.CONTENT_ITEM_RESAVED)), 1)

    def test_categorization_is_rule_based_and_recorded(self):
        row = self.store.upsert_item(
            self.source["id"], "v1",
            "System Design Interview Prep — full course")
        self.assertEqual(row["category"], "development")
        categorized = self.ledger.events(
            event_type=ev.CONTENT_ITEM_CATEGORIZED)
        self.assertEqual(len(categorized), 1)

    def test_unknown_category_is_honest(self):
        row = self.store.upsert_item(self.source["id"], "v1",
                                     "A movie trailer reaction")
        self.assertIn(row["category"], ("entertainment_misc",
                                        "unknown"))

    def test_quota_accounting_stops_at_budget(self):
        ingest = YouTubeIngest(self.db, self.config, self.home,
                               self.clock, self.ledger)
        ingest.quota_used_today = 7999
        self.assertTrue(ingest._spend_quota("playlistItems.list"))
        self.assertFalse(ingest._spend_quota("playlistItems.list"))
        self.assertEqual(len(self.ledger.events(
            event_type=ev.MIRROR_QUOTA_EXHAUSTED)), 1)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestOAuth(MirrorTestCase):
    def test_pkce_state_machine(self):
        import os
        os.environ["DHRITI_YOUTUBE_CLIENT_ID"] = "test-client"
        os.environ["DHRITI_YOUTUBE_CLIENT_SECRET"] = "test-secret"
        try:
            ingest = YouTubeIngest(self.db, self.config, self.home,
                                   self.clock, self.ledger)
            url, verifier, state = ingest.build_auth_url(
                "http://127.0.0.1:8765/callback")
            self.assertIn("code_challenge_method=S256", url)
            self.assertIn("access_type=offline", url)
            self.assertTrue(verifier)

            tokens = {"refresh_token": "rt-1",
                      "access_token": "at-1"}
            calls = {}

            def fake_http(url, data=None, headers=None, opener=None):
                calls["url"] = url
                calls["data"] = data
                return tokens

            ingest._http = fake_http
            ingest.exchange_code("auth-code-1", verifier,
                                 "http://127.0.0.1:8765/callback")
            self.assertTrue(ingest.has_refresh_token())
            self.assertEqual(calls["data"]["grant_type"],
                             "authorization_code")
            self.assertEqual(calls["data"]["code_verifier"],
                             verifier)
            # 0600 perms best-effort on posix
            self.assertEqual(ingest.refresh_token_path.read_text(),
                             "rt-1")
        finally:
            os.environ.pop("DHRITI_YOUTUBE_CLIENT_ID", None)
            os.environ.pop("DHRITI_YOUTUBE_CLIENT_SECRET", None)

    def test_refresh_and_ingest_with_mock_endpoint(self):
        import os
        os.environ["DHRITI_YOUTUBE_CLIENT_ID"] = "test-client"
        os.environ["DHRITI_YOUTUBE_CLIENT_SECRET"] = "test-secret"
        try:
            ingest = YouTubeIngest(self.db, self.config, self.home,
                                   self.clock, self.ledger)
            ingest.refresh_token_path.write_text("rt-1",
                                                 encoding="utf-8")
            pages = [{"items": [{
                "snippet": {"title": "Compiler theory, part 1",
                            "description": "parsing and automata",
                            "publishedAt": "2026-01-01T00:00:00Z"},
                "contentDetails": {"videoId": "vid-1"}}]},
                {"items": []}]
            refresh = {"access_token": "at-1"}

            def fake_http(url, data=None, headers=None, opener=None):
                if "token" in url:
                    return refresh
                return pages.pop(0)

            ingest._http = fake_http
            report = ingest.ingest(self.store, self.source)
            self.assertTrue(report["ok"])
            self.assertEqual(report["ingested"], 1)
            row = self.store.find_item(self.source["id"], "vid-1")
            self.assertEqual(row["title"], "Compiler theory, part 1")
            self.assertEqual(row["category"], "cs_theory")
        finally:
            os.environ.pop("DHRITI_YOUTUBE_CLIENT_ID", None)
            os.environ.pop("DHRITI_YOUTUBE_CLIENT_SECRET", None)

    def test_oauth_error_without_credentials(self):
        import os
        os.environ.pop("DHRITI_YOUTUBE_CLIENT_ID", None)
        ingest = YouTubeIngest(self.db, self.config, self.home,
                               self.clock, self.ledger)
        with self.assertRaises(OAuthError):
            ingest.build_auth_url("http://127.0.0.1:8765/cb")

    def test_csv_import(self):
        csv_path = self.home / "takeout.csv"
        csv_path.write_text(
            "Title,Video URL\n"
            "Guitar practice routine,https://youtube.com/watch?v=g1\n"
            ",https://youtube.com/watch?v=bAD\n",
            encoding="utf-8")
        source = self.store.add_source("csv_import", "takeout.csv",
                                       "CSV: takeout")
        report = import_csv(self.store, source, csv_path)
        self.assertEqual(report["ingested"], 1)
        self.assertEqual(report["malformed"], 1)


class TestSurfacing(MirrorTestCase):

    def test_suggest_oldest_unopened_first(self):
        self._seed(days_ago=5, external="old")
        self._seed(days_ago=1, external="new")
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        item = surface.suggest()
        self.assertEqual(item["external_id"], "old")

    def test_reference_items_excluded(self):
        ref_source = self.store.add_source(
            "youtube_playlist", "PL-ref", "Reference Playlist",
            intent_class="reference")
        self.store.upsert_item(ref_source["id"], "r1",
                               "Reference documentation")
        self._seed(days_ago=1, external="i1")
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        item = surface.suggest()
        self.assertEqual(item["external_id"], "i1")

    def test_one_per_day(self):
        self._closed_day()
        self._seed(days_ago=1)
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        first = surface.surface(self.days.get(self.today))
        self.assertIsNotNone(first)
        second = surface.surface(self.days.get(self.today))
        self.assertIsNone(second)

    def test_not_eligible_during_open_day(self):
        self.seal_today()
        day = self.days.today()
        self.days.try_open(day, self.contracts.for_day(day["date"]))
        self._seed(days_ago=1)
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        self.assertIsNone(surface.surface(
            self.days.get(self.today)))

    def test_time_budget_narrowing_skips_long_items(self):
        self._seed(days_ago=1)
        self.db.execute(
            "UPDATE content_item SET duration_seconds=? WHERE "
            "external_id='v1'", (3600,))
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        self.assertIsNone(surface.suggest(minutes=10))

    def test_recall_protocol_remember_skip_dont(self):
        item = self._seed(days_ago=1)
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        # a typed recall: recorded as recalled
        verdict = surface.handle_recall(item, "the DP table method")
        self.assertTrue(verdict["recalled"])
        row = self.store.get_item(item["id"])
        self.assertEqual(row["recall_successes"], 1)
        # skip: no penalty path
        verdict = surface.handle_recall(item, "skip")
        self.assertFalse(verdict["recalled"])
        self.assertFalse(verdict["penalized"])
        # honest 'I don't remember': penalized, reveal anyway
        stability_before = row["current_stability_days"]
        verdict = surface.handle_recall(item, "I don't remember")
        self.assertTrue(verdict["penalized"])
        self.assertTrue(verdict["reveal"])
        row = self.store.get_item(item["id"])
        self.assertLess(row["current_stability_days"],
                        stability_before)

    def test_reveal_shows_resave_line(self):
        item = self._seed(days_ago=3)
        self.store.upsert_item(self.source["id"], "v1",
                               "Dynamic Programming — Full Course")
        self.clock.advance(days=2)
        self.store.upsert_item(self.source["id"], "v1",
                               "Dynamic Programming — Full Course")
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        text = surface.reveal(self.store.get_item(item["id"]))
        self.assertIn("saved this 3 times", text)
        self.assertIn("not opened it", text)


class TestChoices(MirrorTestCase):
    def setUp(self):
        super().setUp()
        self.item = self.store.upsert_item(
            self.source["id"], "v1", "System Design Interview")

    def test_dismiss_counts_and_resets_on_open(self):
        self.store.record_choice(self.item["id"], "dismiss")
        row = self.store.get_item(self.item["id"])
        self.assertEqual(row["dismiss_count"], 1)
        self.assertEqual(row["consecutive_dismissals"], 1)

    def test_abandon_requires_reason(self):
        with self.assertRaises(ValueError) as ctx:
            self.store.record_choice(self.item["id"], "abandon",
                                     "short")
        self.assertIn("reason", str(ctx.exception))

    def test_abandon_records_reason(self):
        self.store.record_choice(
            self.item["id"], "abandon",
            "I saved this for a version of me that no longer exists")
        row = self.store.get_item(self.item["id"])
        self.assertIsNotNone(row["abandoned_at"])
        self.assertIn("version of me", row["abandoned_reason"])

    def test_open_requires_reentry_declaration(self):
        with self.assertRaises(ValueError):
            self.store.declare_reentry(self.item["id"], "too short")
        reentry = self.store.declare_reentry(
            self.item["id"],
            "I'm opening this because the JWT test is failing")
        self.assertIsNotNone(reentry["id"])
        # the outcome is recorded cold, later
        outcome = self.store.record_reentry_outcome(
            reentry["id"], "partial")
        self.assertEqual(outcome["outcome"], "partial")

    def test_reentry_outcome_single_write(self):
        reentry = self.store.declare_reentry(
            self.item["id"], "I want to face the pile honestly today")
        self.store.record_reentry_outcome(reentry["id"], "completed")
        with self.assertRaises(ValueError):
            self.store.record_reentry_outcome(reentry["id"],
                                              "abandoned")

    def test_progress_completes_at_90_percent(self):
        self.store.record_progress(self.item["id"], 0.4)
        row = self.store.get_item(self.item["id"])
        self.assertIsNone(row["completed_at"])
        self.store.record_progress(self.item["id"], 0.95)
        row = self.store.get_item(self.item["id"])
        self.assertIsNotNone(row["completed_at"])
        self.assertEqual(len(self.ledger.events(
            event_type=ev.CONTENT_ITEM_COMPLETED)), 1)

    def test_opened_not_completed_shown_by_latest_progress(self):
        self.store.record_choice(self.item["id"], "open")
        self.store.record_progress(self.item["id"], 0.12)
        latest = self.store.latest_progress(self.item["id"])
        self.assertEqual(latest["fraction"], 0.12)


class TestAgingAndDegradation(MirrorTestCase):
    def test_aged_out_leaves_the_ranking(self):
        item = self.store.upsert_item(self.source["id"], "v1",
                                      "Old saved thing")
        old = (self.clock.now_utc()
               - __import__("datetime").timedelta(
                   days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute(
            "UPDATE content_item SET saved_at_utc=? WHERE id=?",
            (old, item["id"]))
        aged = self.store.age_out_old_items()
        self.assertEqual(aged, 1)
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        self.assertIsNone(surface.suggest())

    def test_intensity_degrades_after_consecutive_dismissals(self):
        item = self.store.upsert_item(self.source["id"], "v1",
                                      "Dismissed often")
        for _ in range(5):
            self.store.record_choice(item["id"], "dismiss")
        row = self.store.get_item(item["id"])
        self.assertEqual(row["last_surface_intensity"], "title_only")
        self.assertEqual(len(self.ledger.events(
            event_type=ev.SURFACE_INTENSITY_DEGRADED)), 1)
        # an open restores full intensity
        self.store.record_choice(item["id"], "open")
        row = self.store.get_item(item["id"])
        self.assertEqual(row["last_surface_intensity"], "full")


class TestWallCountAndRecord(MirrorTestCase):
    def test_wall_count_is_a_fact_in_the_policy(self):
        from dhriti.daemon import Daemon
        for i in range(3):
            self.store.upsert_item(self.source["id"], f"v{i}",
                                   f"Item {i}")
        daemon = self.make_daemon(mirror={"enabled": True})
        try:
            payload = {}
            daemon._mirror_wall_count(payload)
            self.assertEqual(payload["mirror_unopened_count"], 3)
            # and None when the mirror is off
            daemon.config["mirror"]["enabled"] = False
            payload = {}
            daemon._mirror_wall_count(payload)
            self.assertIsNone(payload["mirror_unopened_count"])
        finally:
            daemon.release_lock()
            daemon.db.close()

    def test_the_record_block_in_aftermath(self):
        self.config["mirror"]["enabled"] = True
        self.seal_today()
        self.store.upsert_item(self.source["id"], "v1",
                               "Dynamic Programming Course")
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("## View: the Mirror", md)
        self.assertIn("### The record", md)
        self.assertIn("Saved this week: 1", md)
        self.assertIn("### By category", md)

    def test_abandonment_rate_fact(self):
        """§3.6: 'You abandon X items at Nx the rate of Y items. Is X
        still an interest?' — a fact, fired only when both categories
        carry enough history for the ratio to mean something."""
        self.config["mirror"]["enabled"] = True
        self.seal_today()
        # productivity: 4 items, 3 abandoned; development: 4 items,
        # 1 abandoned -> 0.75 vs 0.25 -> 3x
        items = {
            "productivity": ["Motivation lecture",
                             "Discipline podcast",
                             "Habit building talk",
                             "Deep work summary"],
            "development": ["System design course",
                            "DP full course",
                            "Concurrency talk",
                            "Kubernetes intro"],
        }
        for category, titles in items.items():
            for i, title in enumerate(titles):
                row = self.store.upsert_item(
                    self.source["id"], f"{category}-{i}", title)
                self.db.execute(
                    "UPDATE content_item SET category=? WHERE id=?",
                    (category, row["id"]))
        for i in range(3):
            self.store.record_choice(
                self.db.query_one(
                    "SELECT id FROM content_item WHERE external_id=?",
                    (f"productivity-{i}",))["id"],
                "abandon", reason="the third re-save of the same talk")
        self.store.record_choice(
            self.db.query_one(
                "SELECT id FROM content_item WHERE external_id=?",
                ("development-0",))["id"],
            "abandon", reason="finished the alternatives instead")
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("You abandon 'productivity' items at 3x the "
                      "rate of 'development' items", md)
        self.assertIn("(a fact, not a verdict)", md)

    def test_abandonment_rate_silent_without_history(self):
        self.config["mirror"]["enabled"] = True
        self.seal_today()
        self.store.upsert_item(self.source["id"], "v1",
                               "One lonely item")
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertNotIn("still an interest", md)

    def test_drop_reasons_of_the_week_in_the_aftermath(self):
        """§3.6: dropping requires a reason; the week's parking block
        shows the reasons, cold."""
        self.seal_today()
        self.parking.park("the old curiosity", kind="question")
        pending = self.parking.pending()
        self.parking.dispose(pending[0]["id"], "dropped",
                             note="the question answered itself")
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("Dropped this week, with the reasons:", md)
        self.assertIn("the question answered itself", md)

    def test_curation_question_gated_on_surfacing(self):
        self.assertFalse(self.review.curation_applicable(
            "2026-11-02"))
        self._closed_day()
        self.store.upsert_item(self.source["id"], "v1", "DP Course")
        surface = SurfaceService(self.db, self.config, self.clock,
                                 self.ledger, store=self.store)
        surfaced = surface.surface(self.days.get(self.today))
        self.assertIsNotNone(surfaced)
        self.assertTrue(self.review.curation_applicable(
            "2026-11-02"))


class TestExplain(MirrorTestCase):
    def test_explain_traces_item_events(self):
        from dhriti.mirror.adapter import ViduraMirrorAdapter
        item = self.store.upsert_item(self.source["id"], "v1",
                                      "DP Course")
        self.store.record_choice(item["id"], "dismiss")
        adapter = ViduraMirrorAdapter(self.config, self.home,
                                      db=self.db, clock=self.clock,
                                      ledger=self.ledger)
        result = adapter.explain(item["id"])
        self.assertEqual(result["item"]["title"], "DP Course")
        types = [h["type"] for h in result["history"]]
        self.assertIn(ev.CONTENT_ITEM_SAVED, types)
        self.assertIn(ev.CONTENT_ITEM_DISMISSED, types)


if __name__ == "__main__":
    unittest.main()
