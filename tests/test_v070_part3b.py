"""v0.7.0 Part 3 tests, batch 2: stack integration (§3.12), Kael
mechanisms (§3.13), operator toolkit completion (§3.14), the
confrontation file (§3.10), the semantic topic-lock (§3.16), FSRS
(§3.17)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import unittest

from dhriti.stack import StackProbe, NextDnsPoller
from dhriti.reflection_bank import (ReflectionBank, EmergencyContacts,
                                    REFLECTION_BANK)
from dhriti.topic_lock import (TopicLockService, EmbeddingBackend,
                               lexical_similarity)
from dhriti.fsrs import (FsrsShadow, retrievability,
                         initial_difficulty, update_difficulty,
                         stability_after_recall, DEFAULT_PARAMS)
from dhriti.review import build_confrontation_file
from dhriti.mirror.store import MirrorStore

from test_plumbing import DhritiTestCase, daily_payload


class TestStack(DhritiTestCase):
    def test_probe_reports_not_configured_honestly(self):
        probe = StackProbe(self.config, self.home, self.clock,
                           self.ledger, db=self.db)
        results = {row["tool"]: row for row in probe.probe_all()}
        self.assertEqual(results["Cold Turkey"]["status"],
                         "NOT_CONFIGURED")
        self.assertEqual(results["NextDNS"]["status"],
                         "NOT_CONFIGURED")
        self.assertEqual(results["Brave filters"]["status"],
                         "NOT_CONFIGURED")

    def test_probe_reports_installed(self):
        self.config["stack"]["nextdns"] = {
            "enabled": True, "profile_id": "ab12",
            "api_key_env": "DHRITI_NEXTDNS_API_KEY",
            "log_poll_minutes": 15}
        probe = StackProbe(self.config, self.home, self.clock,
                           self.ledger, db=self.db)
        results = {row["tool"]: row for row in probe.probe_all()}
        self.assertEqual(results["NextDNS"]["status"], "INSTALLED")
        self.assertIn("ab12", results["NextDNS"]["detail"])

    def test_integration_declaration_recorded(self):
        probe = StackProbe(self.config, self.home, self.clock,
                           self.ledger, db=self.db)
        probe.declare_integration("unhook",
                                  ["youtube_suppression"])
        events = self.ledger.events(
            event_type="stack_integration_declared")
        self.assertEqual(len(events), 1)

    def test_unhook_delegation_splits_the_rules(self):
        self.config["stack"]["unhook"] = {
            "enabled": True, "delegate_youtube_suppression": True}
        probe = StackProbe(self.config, self.home, self.clock,
                           self.ledger, db=self.db)
        self.assertTrue(probe.suppress_js_owns_youtube())

    def test_cold_turkey_narrows_to_residual(self):
        self.config["stack"]["cold_turkey"] = {
            "enabled": True, "executable": "coldturkey",
            "arm_cmd": [], "disarm_cmd": [], "status_cmd": [],
            "delegate_domains": ["youtube.com", "reddit.com"]}
        probe = StackProbe(self.config, self.home, self.clock,
                           self.ledger, db=self.db)
        residual = probe.cold_turkey_residual(
            ["youtube.com", "chatgpt.com", "reddit.com"])
        self.assertEqual(residual, ["chatgpt.com"])

    def test_brave_import_reports_unsupported_honestly(self):
        rules = self.home / "brave.txt"
        rules.write_text(
            "! a comment\n"
            "youtube.com##ytd-rich-item-renderer\n"
            "example.com##/regex/selector/\n"
            "||ads.example.com^\n", encoding="utf-8")
        self.config["stack"]["brave_filters"] = {
            "enabled": True, "import_path": str(rules)}
        probe = StackProbe(self.config, self.home, self.clock,
                           self.ledger, db=self.db)
        report = probe.import_brave(rules)
        self.assertEqual(len(report["supported"]), 1)
        self.assertEqual(report["unsupported"], 2)
        events = self.ledger.events(
            event_type="suppress_imported_rules")
        self.assertEqual(len(events), 1)

    def test_nextdns_poll_records_dns_blocked(self):
        self.config["stack"]["nextdns"] = {
            "enabled": True, "profile_id": "ab12",
            "api_key_env": "DHRITI_NEXTDNS_API_KEY",
            "log_poll_minutes": 15}
        import os
        os.environ["DHRITI_NEXTDNS_API_KEY"] = "test-key"

        class FakeResp:
            def read(self):
                return json.dumps(
                    {"dnsQueries": [{"domain": "youtube.com"},
                                    {"domain": "reddit.com"}]}
                ).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        poller = NextDnsPoller(self.db, self.config, self.clock,
                               self.ledger, http=lambda req,
                               timeout: FakeResp())
        blocked = poller.poll()
        self.assertEqual(blocked, 2)
        events = self.ledger.events(event_type="dns_blocked")
        self.assertEqual(len(events), 2)
        os.environ.pop("DHRITI_NEXTDNS_API_KEY", None)


class TestKael(DhritiTestCase):
    def test_bank_has_30_questions(self):
        self.assertEqual(len(REFLECTION_BANK), 30)
        bank = ReflectionBank(self.db, self.config, self.clock,
                              self.ledger)
        self.assertEqual(len(bank.questions()), 30)

    def test_draw_off_by_default(self):
        bank = ReflectionBank(self.db, self.config, self.clock,
                              self.ledger)
        self.assertIsNone(bank.draw("2026-11-02"))

    def test_draw_one_per_week_deterministic(self):
        self.config["reflection_bank"]["enabled"] = True
        bank = ReflectionBank(self.db, self.config, self.clock,
                              self.ledger)
        first = bank.draw("2026-11-02")
        self.assertIsNotNone(first)
        again = bank.draw("2026-11-02")
        self.assertEqual(first, again)
        self.assertEqual(len(self.ledger.events(
            event_type="reflection_question_drawn")), 1)

    def test_emergency_contacts_max_three(self):
        contacts = EmergencyContacts(self.db, self.clock,
                                     self.ledger)
        contacts.add("mom", "+91-...")
        contacts.add("dad", "+91-...")
        contacts.add("friend", "+91-...")
        with self.assertRaises(ValueError):
            contacts.add("fourth", "+91-...")
        self.assertEqual(len(contacts.list()), 3)

    def test_ritual_quick_uses_yesterday(self):
        # yesterday's contract exists
        yesterday = "2026-11-01"
        payload = daily_payload()
        payload["workspace_dir"] = str(self.home)
        self.contracts.seal(yesterday, payload)
        out, code = self._run("cmd_ritual", {"quick": True,
                                             "set": None})
        self.assertIn("yesterday's contract", out)
        self.assertTrue((self.home / "contract-2026-11-02.json")
                        .exists())


class TestOperatorToolkitCompletion(DhritiTestCase):
    def test_anchor_offsite_refuses_inside_home(self):
        with self.assertRaises(SystemExit):
            self._run("cmd_anchor_offsite",
                      {"path": str(self.home / "anchor.json")})

    def test_anchor_offsite_writes_outside(self):
        outside = self.home.parent / "offsite-anchor.json"
        out, code = self._run("cmd_anchor_offsite",
                              {"path": str(outside)})
        self.assertTrue(outside.exists())
        payload = json.loads(outside.read_text())
        self.assertIn("head", payload)

    def test_selector_staleness_reported_in_health(self):
        self.ledger.record(
            "surface_rule_stale",
            observed={"rule": "yt-home-shorts"},
            action_taken="selector no longer matches")
        from dhriti.health import build_health
        report = build_health(self.home, self.config, self.clock,
                              db=self.db, ledger=self.ledger)
        self.assertTrue(any(
            "[warn] suppression.yt-home-shorts" in line
            for line in report.lines))

    def test_health_reports_mirror_quota_when_enabled(self):
        import os
        self.config["mirror"]["enabled"] = True
        os.environ["DHRITI_YOUTUBE_CLIENT_ID"] = "x"
        try:
            from dhriti.health import build_health
            report = build_health(self.home, self.config,
                                  self.clock, db=self.db,
                                  ledger=self.ledger)
            self.assertTrue(any("mirror.quota" in line
                                for line in report.lines))
            self.assertTrue(any("mirror.oauth" in line
                                for line in report.lines))
        finally:
            os.environ.pop("DHRITI_YOUTUBE_CLIENT_ID", None)

    def test_health_honesty_boundaries_stated(self):
        from dhriti.health import build_health
        report = build_health(self.home, self.config, self.clock,
                              db=self.db, ledger=self.ledger)
        self.assertTrue(any("honesty.boundaries" in line
                            for line in report.lines))

    def test_reclassify_is_additive(self):
        store = MirrorStore(self.db, {"mirror": {}}, self.clock,
                            self.ledger)
        source = store.add_source("youtube_liked", "LL", "Liked")
        item = store.upsert_item(source["id"], "v1",
                                 "System design course")
        out, code = self._run("cmd_reclassify",
                              {"classifier": "rules-v1",
                               "since": "2026-11-01"})
        self.assertIn("appended", out)
        # the categorized events doubled (original + reclassify)
        events = self.ledger.events(
            event_type="content_item_categorized")
        self.assertEqual(len(events), 2)

    def test_policy_replay_is_a_dry_run(self):
        hypothetical = self.home / "hypothetical.json"
        hypothetical.write_text(json.dumps(
            {"blocked_domains": ["example.com"]}), encoding="utf-8")
        out, code = self._run("cmd_policy_replay",
                              {"config": str(hypothetical),
                               "weeks": 1})
        self.assertIn("reported, not applied", out)


class TestConfrontation(DhritiTestCase):
    def test_file_generated(self):
        self.seal_today()
        session = self.start_session()
        self.passes.open(session["id"], "how do auth tokens expire",
                         minutes=5)
        # the pass expires unanswered
        self.clock.advance(minutes=10)
        self.passes.expire_overdue(grace_seconds=0)
        text = build_confrontation_file(self.db, self.ledger,
                                        self.today.isoformat(),
                                        self.config, self.clock)
        self.assertIn("CONFRONTATION FILE", text)
        self.assertIn("passes that expired unanswered", text)
        self.assertIn("how do auth tokens expire", text)

    def test_faces_breaks_and_parking(self):
        self.parking.park("the old curiosity", kind="question")
        record = self.breaks.initiate(None)
        self.clock.advance(seconds=70)
        self.breaks.confirm(record["id"],
                            "the honest reason for the break here")
        text = build_confrontation_file(self.db, self.ledger,
                                        self.today.isoformat(),
                                        self.config, self.clock)
        self.assertIn("the honest reason for the break", text)
        self.assertIn("the old curiosity", text)

    def test_not_sent(self):
        """The confrontation file is a fact on disk and one event;
        nothing in it goes anywhere."""
        from dhriti.cli import cmd_confrontation
        import argparse
        ctx = self.make_cli_context()
        try:
            cmd_confrontation(argparse.Namespace(), ctx)
        finally:
            ctx.close()
        events = self.ledger.events(
            event_type="confrontation_generated")
        self.assertEqual(len(events), 1)
        observed = json.loads(events[0]["observed_payload"])
        self.assertIn("NOT sent", self.ledger.events(
            event_type="confrontation_generated"
        )[0]["action_taken"])


class TestSemanticTopicLock(unittest.TestCase):
    def test_backend_disclosed(self):
        backend = EmbeddingBackend("local")
        self.assertEqual(backend.backend, "local-hashing-v1")

    def test_lexical_similarity_continuation_beats_shift(self):
        topic = "debugging the JWT refresh flow"
        cont = lexical_similarity(
            topic, "continue debugging the JWT refresh, same error")
        shift = lexical_similarity(
            topic, "anyway, a totally different question now")
        self.assertGreater(cont, shift)

    def test_bind_topic_requires_min_chars(self):
        service = TopicLockService({"topic_lock": {
            "require_topic": True, "min_topic_chars": 10}})
        with self.assertRaises(ValueError):
            service.bind_topic("short")

    def test_bind_keeps_the_hash_not_the_vector(self):
        service = TopicLockService({})
        result = service.bind_topic("debugging the JWT test failure")
        self.assertIn("embedding_hash", result)
        self.assertNotIn("embedding", result)

    def test_hybrid_similarity_bounds(self):
        service = TopicLockService({})
        service.bind_topic("reverse the array in java")
        on_topic = service.similarity("reverse the array in java "
                                      "again")
        off_topic = service.similarity("why do cats meow at each "
                                       "other")
        self.assertGreater(on_topic, off_topic)

    def test_divergence_verdict_pre_send(self):
        service = TopicLockService({"topic_lock": {
            "similarity_threshold": 0.65,
            "on_divergence": "pre_send", "park_button": True}})
        service.bind_topic("debugging the JWT test failure")
        verdict = service.evaluate_prompt(
            "is Ex Machina realistic about AI self-preservation",
            session_id="s1", ledger=None)
        self.assertTrue(verdict["divergent"])
        self.assertEqual(verdict["mode"], "pre_send")
        self.assertTrue(verdict["park_button"])

    def test_pre_send_records_divergence_event(self):
        service = TopicLockService({"topic_lock": {
            "similarity_threshold": 0.65}})
        service.bind_topic("debugging the JWT test failure")
        service.evaluate_prompt("tell me about nuclear missiles",
                                session_id="s1", ledger=self.ledger
                                ) if hasattr(self, "ledger") else None
        # (ledger path tested in the DhritiTestCase subclass below)

    def test_response_divergence_hidden_post_generation(self):
        service = TopicLockService({"topic_lock": {
            "similarity_threshold": 0.65,
            "on_divergence": "post_generation"}})
        service.bind_topic("debugging the JWT test failure")
        verdict = service.evaluate_response(
            "Anyway, here is the history of the Roman Empire...",
            session_id="s1", ledger=None)
        self.assertTrue(verdict["divergent"])

    def test_pivot_requires_reason_and_rebinds(self):
        service = TopicLockService({})
        with self.assertRaises(ValueError):
            service.declare_pivot("short", "s1")
        result = service.declare_pivot(
            "the JWT failure revealed an async gap I must close", "s1")
        self.assertTrue(result["pivot"])


class TestTopicLockLedger(DhritiTestCase):
    def test_divergent_prompt_records_event(self):
        service = TopicLockService(self.config)
        service.bind_topic("debugging the JWT test failure")
        service.evaluate_prompt("let me tell you about my setup",
                                session_id="s1",
                                ledger=self.ledger)
        events = self.ledger.events(
            event_type="ai_prompt_diverged")
        self.assertEqual(len(events), 1)
        observed = json.loads(events[0]["observed_payload"])
        self.assertIn("similarity", observed)

    def test_on_topic_prompt_passes_silently(self):
        service = TopicLockService(self.config)
        service.bind_topic("debugging the JWT test failure")
        service.evaluate_prompt("the JWT test still fails on "
                                "refresh", session_id="s1",
                                ledger=self.ledger)
        self.assertEqual(len(self.ledger.events(
            event_type="ai_prompt_diverged")), 0)

    def test_pivot_declared_event(self):
        service = TopicLockService(self.config)
        service.bind_topic("debugging the JWT test failure")
        service.declare_pivot(
            "the failure is actually an async misunderstanding",
            "s1", ledger=self.ledger)
        self.assertEqual(len(self.ledger.events(
            event_type="ai_pivot_declared")), 1)

    def test_enabling_is_a_cold_state_act(self):
        self.assertFalse(self.config["topic_lock"]
                         ["semantic_mode_enabled"])
        self.ledger.record(
            "topic_lock_enabled",
            observed={"semantic_mode": True},
            action_taken="L-9 exception enabled cold")
        self.assertEqual(len(self.ledger.events(
            event_type="topic_lock_enabled")), 1)


class TestFsrs(unittest.TestCase):
    def test_retrievability_decay(self):
        # R(0) = 1; R grows with t; R decreases with S
        self.assertAlmostEqual(retrievability(0, 10.0), 1.0)
        self.assertLess(retrievability(10, 10.0),
                        retrievability(5, 10.0))
        self.assertGreater(retrievability(10, 30.0),
                           retrievability(10, 5.0))

    def test_difficulty_bounds_and_updates(self):
        d0 = initial_difficulty(1, DEFAULT_PARAMS)
        self.assertGreaterEqual(d0, 1.0)
        self.assertLessEqual(d0, 10.0)
        easier = update_difficulty(8.0, 4, DEFAULT_PARAMS)
        self.assertLess(easier, 8.0)

    def test_stability_grows_on_recall(self):
        s = 10.0
        s2 = stability_after_recall(s, 5.0, 0.9, DEFAULT_PARAMS)
        self.assertGreater(s2, s)

    def test_monotonicity(self):
        s = 5.0
        for _ in range(5):
            s = stability_after_recall(s, 5.0, 0.8, DEFAULT_PARAMS)
            self.assertGreater(s, 0.1)
        self.assertGreater(s, 5.0)


class TestFsrsShadow(DhritiTestCase):
    def _seed_pile(self, n=5):
        store = MirrorStore(self.db, {"mirror": {}}, self.clock,
                            self.ledger)
        source = store.add_source("youtube_liked", "LL", "Liked")
        import datetime as dt
        for i in range(n):
            row = store.upsert_item(source["id"], f"v{i}",
                                    f"Course part {i}")
            saved = (self.clock.now_utc() - dt.timedelta(
                days=10 + i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.db.execute(
                "UPDATE content_item SET saved_at_utc=? WHERE id=?",
                (saved, row["id"]))
        return store

    def test_shadow_computed_weekly(self):
        self._seed_pile()
        shadow = FsrsShadow(self.db, self.config, self.clock,
                            self.ledger)
        result = shadow.compute_shadow("2026-11-02")
        self.assertEqual(result["items_compared"], 5)
        self.assertIsInstance(result["rank_correlation"], float)
        rows = self.db.query("SELECT * FROM fsrs_shadow")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(self.ledger.events(
            event_type="fsrs_shadow_computed")), 1)

    def test_shadow_gate_opens_at_day_30(self):
        self._seed_pile(n=2)
        shadow = FsrsShadow(self.db, self.config, self.clock,
                            self.ledger)
        self.assertFalse(shadow.shadow_gate_open())
        self.clock.advance(days=31)
        self.assertTrue(shadow.shadow_gate_open())

    def test_production_gate_refused_early(self):
        self._seed_pile()
        shadow = FsrsShadow(self.db, self.config, self.clock,
                            self.ledger)
        with self.assertRaises(ValueError) as ctx:
            shadow.open_production_gate()
        self.assertIn("the FSRS gate is closed", str(ctx.exception))
        self.assertIn("more months", str(ctx.exception))

    def test_production_gate_status_honest(self):
        self._seed_pile()
        shadow = FsrsShadow(self.db, self.config, self.clock,
                            self.ledger)
        status = shadow.production_gate_status()
        self.assertLess(status["months_of_use"], 6)
        self.assertFalse(status["open"])


if __name__ == "__main__":
    unittest.main()
