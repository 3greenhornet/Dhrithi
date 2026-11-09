"""Cold-state mechanisms: contracts schema, emergency path, parking
lot, cold review, digest, suppression flag, builder clause, specimen
coder."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"
                       / "specimens"))

from dhriti.db import Database, resolve_journal_mode
from dhriti.errors import BreakGlassError, ContractError
from dhriti.models import ContractKind
from dhriti.review import (ColdReviewService, ParkingLotService,
                           REVIEW_QUESTIONS, build_digest)

from test_plumbing import DhritiTestCase, daily_payload, make_config


class TestJournalMode(unittest.TestCase):
    def test_delete_is_a_valid_override(self):
        self.assertEqual(resolve_journal_mode("delete"), "delete")
        self.assertEqual(resolve_journal_mode("WAL"), "wal")
        self.assertEqual(resolve_journal_mode(None),
                         resolve_journal_mode(None))  # deterministic auto

    def test_stale_wal_quarantined_on_corrupt_open(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        db_path = tmp / "dhriti.sqlite3"
        db = Database(db_path, journal_mode="delete")
        db.close()
        # simulate a corrupt sidecar left by a crash
        (tmp / "dhriti.sqlite3-wal").write_bytes(b"garbage")
        db2 = Database(db_path, journal_mode="delete")
        db2.close()
        # Bug 8 (Phase 0): the database opens, AND either the suspect
        # sidecar was quarantined as *.corrupt-* or no -wal file remains.
        self.assertTrue(db_path.exists())
        corrupt = [p.name for p in tmp.iterdir() if "corrupt" in p.name]
        wal = [p.name for p in tmp.iterdir() if p.name.endswith("-wal")]
        self.assertTrue(
            corrupt or not wal,
            f"neither quarantined ({corrupt}) nor removed ({wal}); "
            "garbage sidecar survived an open that should not trust it")
        for name in corrupt:
            self.assertIn("corrupt", name)


class TestContractSchemaV2(DhritiTestCase):
    def test_main_belief_requires_label(self):
        payload = daily_payload()
        payload["main_belief"] = "compiler practice"   # not an object
        with self.assertRaises(ContractError) as ctx:
            self.contracts.create_draft(
                ContractKind.DAILY, self.today.isoformat(), payload)
        self.assertIn("main_belief", str(ctx.exception))

    def test_if_then_group_is_all_or_nothing(self):
        payload = daily_payload()
        payload.pop("expected_obstacle", None)
        payload.pop("if_then_response", None)
        payload.pop("return_condition", None)
        # group absent entirely -> valid
        cid = self.contracts.create_draft(
            ContractKind.DAILY, self.today.isoformat(), payload)
        self.assertTrue(cid)
        # partial group -> refused
        partial = daily_payload()
        partial["expected_obstacle"] = "the loop throws"
        with self.assertRaises(ContractError) as ctx:
            self.contracts.create_draft(
                ContractKind.DAILY, self.today.isoformat(), partial)
        self.assertIn("all-or-nothing", str(ctx.exception))

    def test_research_fallback_must_be_bounded(self):
        payload = daily_payload()
        payload["research_fallback"] = {"scope": "docs"}
        with self.assertRaises(ContractError) as ctx:
            self.contracts.create_draft(
                ContractKind.DAILY, self.today.isoformat(), payload)
        self.assertIn("return_condition", str(ctx.exception))
        payload["research_fallback"] = {
            "scope": "Spring Security JWT for the failing test",
            "return_condition": "rerun the test"}
        cid = self.contracts.create_draft(
            ContractKind.DAILY, self.today.isoformat(), payload)
        self.assertTrue(cid)


class TestEmergencyPath(DhritiTestCase):
    def test_emergency_is_immediate_logged_and_cooldown_free(self):
        result = self.breaks.emergency(
            None, "family emergency, had to leave the desk now")
        self.assertEqual(result["kind"], "emergency")
        row = self.breaks._last_confirmed()
        self.assertEqual(row["id"], result["id"])
        self.assertIsNone(row["cooldown_until"])
        # the emergency never blocks the next session
        self.assertIsNone(self.breaks.cooldown_active())
        # and it is its own event type in the ledger
        events = self.ledger.events(event_type="emergency_exception")
        self.assertEqual(len(events), 1)

    def test_emergency_still_requires_typed_reason(self):
        with self.assertRaises(BreakGlassError):
            self.breaks.emergency(None, "too short")
        with self.assertRaises(BreakGlassError):
            self.breaks.emergency(None, "   ")


class TestParkingLot(DhritiTestCase):
    def test_park_and_dispose(self):
        row = self.parking.park("why does the JVM verify bytecode",
                                source="curiosity while coding")
        self.assertIsNone(row["disposition"])
        self.assertIn("curiosity_topic_parked",
                      [e["event_type"] for e in self.ledger.events()])
        done = self.parking.dispose(row["id"], "approved",
                                    note="add to allowed research")
        self.assertEqual(done["disposition"], "approved")
        # double disposition refused
        with self.assertRaises(ValueError):
            self.parking.dispose(row["id"], "dropped")

    def test_park_requires_a_line(self):
        with self.assertRaises(ValueError):
            self.parking.park("   ")

    def test_long_questions_are_capped(self):
        row = self.parking.park("x" * 500)
        self.assertLessEqual(len(row["question"]), 200)

    def test_pending_and_stats(self):
        a = self.parking.park("topic a")
        self.parking.park("topic b")
        self.parking.dispose(a["id"], "dropped",
                             note="not worth the time, honestly")
        self.assertEqual(len(self.parking.pending()), 1)
        self.assertEqual(self.parking.stats(),
                         {"parked": 1, "dropped": 1})

    def test_dropped_requires_a_reason(self):
        """The abandonment ritual: dropping is a decision with a
        one-line reason — cold-state feedback, not a silent
        disappearance."""
        row = self.parking.park("topic a")
        with self.assertRaises(ValueError) as ctx:
            self.parking.dispose(row["id"], "dropped")
        self.assertIn("one-line reason", str(ctx.exception))


class TestColdReview(DhritiTestCase):
    def test_ten_fixed_questions_exist(self):
        keys = {k for k, _ in REVIEW_QUESTIONS}
        self.assertEqual(len(REVIEW_QUESTIONS), 10)
        for key in ("competence_source", "faking_it", "wall_or_choice",
                    "out_of_scope_device", "evidence_quality",
                    "surveillance_comfort", "targets_honest",
                    "toll_worth_it",
                    "what_would_make_tomorrow_sealable",
                    "declared_thinking"):
            self.assertIn(key, keys)

    def test_answers_stored_outside_ledger_payload(self):
        self.review.record("week:2026-11-02", "competence_source",
                           "guitar scales, honestly")
        rows = self.review.answers_for("week:2026-11-02")
        self.assertEqual(rows[0]["answer"], "guitar scales, honestly")
        event = self.ledger.events(event_type="cold_review_answer")[0]
        # the answer text must NOT travel into the chain (deletion model)
        self.assertNotIn("guitar", event["observed_payload"])
        self.assertEqual(
            json.loads(event["observed_payload"])["question_key"],
            "competence_source")

    def test_unknown_question_refused(self):
        with self.assertRaises(ValueError):
            self.review.record("week:2026-11-02", "how_great_am_i", "very")

    def test_leisure_question_conditional(self):
        qs = self.review.questions_for(leisure_declared=False)
        self.assertEqual(len(qs), 10)
        qs = self.review.questions_for(leisure_declared=True)
        self.assertEqual(len(qs), 11)
        self.assertIn("leisure_honored", {k for k, _ in qs})


class TestDigest(DhritiTestCase):
    def test_digest_contains_facts_and_chain_head(self):
        self.seal_today()
        # one break with a reason
        record = self.breaks.initiate(None)
        self.breaks.confirm(record["id"],
                            "needed docs that were blocked for the task")
        text = build_digest(self.db, self.ledger,
                            self.today.isoformat(), config=self.config,
                            clock=self.clock)
        self.assertIn("DHRITI WEEKLY DIGEST", text)
        self.assertIn("chain head:", text)
        self.assertIn("needed docs that were blocked", text)
        self.assertIn("dead-man's switch", text)


class TestPolicySuppressionAndBuilderClause(DhritiTestCase):
    def _snapshot(self, **kwargs):
        return self.policy.build_snapshot(
            {"allowed_domains": [], "allowed_apps": [],
             "blocked_categories": []},
            daily_payload(), kwargs.get("mode"),
            None, None, **{k: v for k, v in kwargs.items() if k != "mode"})

    def test_snapshot_carries_suppression_flag(self):
        from dhriti.models import WorkMode
        snap = self._snapshot(mode=WorkMode.CLOSED_WORLD,
                              suppress_surfaces=True)
        rules = self.policy.extension_rules(snap)
        self.assertTrue(rules["suppress_surfaces"])
        snap2 = self._snapshot(mode=WorkMode.CLOSED_WORLD,
                               suppress_surfaces=False)
        self.assertFalse(
            self.policy.extension_rules(snap2)["suppress_surfaces"])

    def test_builder_clause_extends_blocked_domains(self):
        from dhriti.models import WorkMode
        snap = self._snapshot(
            mode=WorkMode.CLOSED_WORLD,
            extra_blocked_domains=["github.com"])
        self.assertIn("github.com", snap["blocked_domains"])


class TestDaemonBuilderClause(DhritiTestCase):
    def test_builder_clause_blocks_until_targets_met(self):
        self.seal_today()  # seal BEFORE the daemon swaps the db handle
        # Bug 7 (Phase 0): github.com is in the coding profile's
        # allowlist, so the allowlist wins and the clause does not fire
        # for it. The clause is tested with a domain that is NOT
        # allowlisted.
        cfg = make_config(builder_clause={
            "enabled": True,
            "blocked_domains": ["github.com",
                                "builder-distraction.example"]})
        daemon = self.make_daemon(**{"builder_clause":
                                      cfg["builder_clause"]})
        daemon._tick()  # opens the day
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], "OPEN")
        session = daemon.start_session("reverse the array")
        self.assertEqual(session["state"], "ACTIVE")
        # the clause fired for the non-allowlisted domain
        events = [e["event_type"] for e in daemon.ledger.events()]
        self.assertIn("builder_clause_applied", events)
        self.assertIn("builder_clause_overridden_by_allowlist", events)
        snap = daemon.policy_engine.current_snapshot()
        self.assertIn("builder-distraction.example",
                      snap["blocked_domains"])
        self.assertNotIn("github.com", snap["blocked_domains"])
        daemon.release_lock()
        daemon.db.close()


class TestAftermathNewBlocks(DhritiTestCase):
    def test_day_report_shows_parking_review_and_breaks(self):
        self.parking.park("why does JIT deopt")
        self.review.record(f"day:{self.today.isoformat()}",
                           "targets_honest", "the wall was up")
        self.breaks.emergency(None, "laptop on fire, literally")
        report = self.aftermath.day_report(self.today.isoformat())
        md = report["markdown"]
        self.assertIn("why does JIT deopt", md)
        self.assertIn("targets_honest: the wall was up", md)
        self.assertIn("Consumption facts", md)
        self.assertIn("## Breaks", md)


class TestSpecimenCoder(unittest.TestCase):
    def test_coder_runs_on_specimen_001(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable,
             str(root / "analysis" / "specimens" / "code_specimen.py"),
             str(root / "analysis" / "specimens"
                 / "specimen_001_turns.json"),
             "--out-dir", str(root / "analysis" / "specimens"
                              / "SPECIMEN_001")],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(
            (root / "analysis" / "specimens" / "SPECIMEN_001"
             / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["user_turns"], 52)
        self.assertEqual(summary["affordance_rate"], 1.0)
        self.assertEqual(summary["evidence_events_total"], 0)
        self.assertGreater(summary["ai_suggestion_offers_total"], 25)


if __name__ == "__main__":
    unittest.main()


class TestRestoredQuestions(unittest.TestCase):
    """v0.6.0 Part 1 §6: the base's six questions are authoritative;
    the v0.5.0 additions that do not overlap are kept."""

    def test_base_six_questions_all_present(self):
        keys = {k for k, _ in REVIEW_QUESTIONS}
        for required in ("competence_source", "faking_it",
                         "wall_or_choice", "out_of_scope_device",
                         "evidence_quality", "surveillance_comfort"):
            self.assertIn(required, keys,
                          f"base question {required!r} missing")

    def test_v050_additions_present(self):
        keys = {k for k, _ in REVIEW_QUESTIONS}
        for kept in ("targets_honest", "toll_worth_it",
                     "what_would_make_tomorrow_sealable"):
            self.assertIn(kept, keys)

    def test_curation_choice_conditional(self):
        from dhriti.review import CONDITIONAL_QUESTIONS
        self.assertIn("curation_choice", CONDITIONAL_QUESTIONS)

    def test_ten_fixed_questions(self):
        self.assertEqual(len(REVIEW_QUESTIONS), 10)


class TestDigestV060(DhritiTestCase):
    def test_emergency_threshold_line(self):
        """§9.3: 3+ emergency exits in the week get the threshold
        line; below it, the line is absent."""
        from dhriti.models import SessionState
        self.seal_today()
        day = self.days.today()
        day = self.days.try_open(day, self.contracts.for_day(day["date"]))
        session = self.sessions.create(day["id"], "c1")
        self.walk_to_active(session["id"])
        for i in range(3):
            self.breaks.emergency(
                session["id"], f"production incident {i}",
                session_finish=lambda sid: None)
        text = build_digest(self.db, self.ledger, "2026-11-02",
                            self.config, self.clock)
        self.assertIn("3 in 7 days", text)
        # and absent below the threshold
        text2 = build_digest(self.db, self.ledger, "2026-11-09",
                             self.config, self.clock)
        self.assertNotIn("in 7 days. The pattern", text2)
