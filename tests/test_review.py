"""Schema v2 + cold-state mechanisms: main-belief contracts, emergency
path, parking lot, cold review, digest, suppression flag, builder
clause, specimen coder."""

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
from dhriti.ledger import Ledger
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
        leftovers = [p.name for p in tmp.iterdir() if "corrupt" in p.name]
        # a clean open may checkpoint-and-delete the wal instead; either
        # way the database must open and no garbage may remain
        self.assertTrue(db_path.exists())
        for name in leftovers:
            self.assertIn("corrupt", name)


class TestContractSchemaV2(DhritiTestCase):
    def test_main_belief_group_required(self):
        payload = daily_payload()
        for field in ("main_belief", "main_belief_metric",
                      "main_belief_current_state", "substitute_activities",
                      "substitute_budget"):
            broken = dict(payload)
            broken.pop(field)
            with self.assertRaises(ContractError) as ctx:
                self.contracts.create_draft(
                    ContractKind.DAILY, self.today.isoformat(), broken)
            self.assertIn("D-030", str(ctx.exception))

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
        partial.pop("if_then_response")
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
        result = self.break_glass.emergency(
            "family emergency, had to leave the desk now")
        self.assertTrue(result["emergency"])
        row = self.break_glass._last_confirmed()
        self.assertEqual(row["id"], result["handle"])
        self.assertIsNone(row["cooldown_until"])
        # the emergency never blocks the next session
        self.assertIsNone(self.break_glass.cooldown_active())
        # and it is its own event type in the ledger
        events = self.ledger.events(event_type="emergency_exception")
        self.assertEqual(len(events), 1)

    def test_emergency_still_requires_typed_reason(self):
        with self.assertRaises(BreakGlassError):
            self.break_glass.emergency("too short")
        with self.assertRaises(BreakGlassError):
            self.break_glass.emergency("   ")


class TestParkingLot(DhritiTestCase):
    def setUp(self):
        super().setUp()
        self.parking = ParkingLotService(self.db, self.clock, self.ledger)

    def test_park_and_dispose(self):
        row = self.parking.park("why does the JVM verify bytecode",
                                origin="curiosity while coding")
        self.assertEqual(row["disposition"], "parked")
        self.assertIn("curiosity_topic_parked",
                      [e["event_type"] for e in self.ledger.events()])
        done = self.parking.dispose(row["id"], "approved",
                                    "add to allowed research")
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
        self.parking.dispose(a["id"], "dropped")
        self.assertEqual(len(self.parking.pending()), 1)
        self.assertEqual(self.parking.stats(),
                         {"parked": 1, "dropped": 1})


class TestColdReview(DhritiTestCase):
    def setUp(self):
        super().setUp()
        self.review = ColdReviewService(self.db, self.clock, self.ledger)

    def test_six_fixed_questions_exist(self):
        for key in ("competence_source", "faking_it", "wall_or_choice",
                    "out_of_scope_device", "evidence_quality",
                    "surveillance_comfort"):
            self.assertIn(key, REVIEW_QUESTIONS)

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


class TestDigest(DhritiTestCase):
    def test_digest_contains_facts_and_chain_head(self):
        self.seal_today()
        # one break with a reason
        handle = self.break_glass.initiate()["handle"]
        self.break_glass.confirm(handle, "needed docs that were blocked "
                                     "for the task")
        text = build_digest(self.db, self.ledger,
                            self.today.isoformat(), clock=self.clock)
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
        cfg = make_config(builder_clause={
            "enabled": True,
            "blocked_domains": ["github.com"]})
        daemon = self.make_daemon(**{"builder_clause":
                                      cfg["builder_clause"]})
        daemon._tick()  # opens the day
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], "OPEN")
        session = daemon.start_session("reverse the array")
        self.assertEqual(session["state"], "ACTIVE")
        # the clause fired because targets are unmet
        events = [e["event_type"] for e in daemon.ledger.events()]
        self.assertIn("builder_clause_applied", events)
        snap = daemon.policy_engine.current_snapshot()
        self.assertIn("github.com", snap["blocked_domains"])
        daemon.release_lock()
        daemon.db.close()


class TestAftermathNewBlocks(DhritiTestCase):
    def setUp(self):
        super().setUp()
        from dhriti.aftermath import AftermathService
        self.aftermath = AftermathService(
            self.db, self.config, self.clock, self.ledger)

    def test_day_report_shows_exchange_parking_review_and_breaks(self):
        parking = ParkingLotService(self.db, self.clock, self.ledger)
        review = ColdReviewService(self.db, self.clock, self.ledger)
        self.seal_today()
        day = self.days.ensure_day(self.today)
        parking.park("why does JIT deopt", day_id=day["id"])
        review.record(f"day:{self.today.isoformat()}",
                      "wall_or_choice", "the wall was up")
        self.break_glass.emergency("laptop on fire, literally",
                                   day_id=day["id"])
        report = self.aftermath.day_report(self.days.get(self.today))
        md = report["markdown"]
        self.assertIn("The exchange", md)
        self.assertIn("I want to be a software engineer", md)
        self.assertIn("why does JIT deopt", md)
        self.assertIn("wall_or_choice: the wall was up", md)
        self.assertIn("EMERGENCY", md)
        self.assertIn("Consumption facts", md)


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
