"""Contracts, state machine, and immutability guarantees."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import unittest

from dhriti.errors import ContractError, StateError
from dhriti.models import ContractKind, ContractState, SessionState

from test_plumbing import DhritiTestCase, daily_payload


class TestContracts(DhritiTestCase):
    def test_draft_requires_fields(self):
        payload = daily_payload()
        payload.pop("contract_line")
        with self.assertRaises(ContractError):
            self.contracts.create_draft(
                ContractKind.DAILY, self.today.isoformat(), payload)

    def test_seal_and_immutability(self):
        contract = self.seal_today()
        self.assertEqual(contract["state"], ContractState.SEALED.value)
        # sealing twice for the same day refuses (commitment is not
        # double-written)
        with self.assertRaises(ContractError):
            self.contracts.seal(self.days.today(), daily_payload())

    def test_sealed_contract_survives_direct_sql_update(self):
        contract = self.seal_today()
        with self.assertRaises(Exception):  # trigger aborts the UPDATE
            self.db.execute(
                "UPDATE contract SET payload_json='{\"pwned\":1}' "
                "WHERE id=?", (contract["id"],))
        row = self.db.query_one(
            "SELECT payload_json FROM contract WHERE id=?",
            (contract["id"],))
        self.assertNotIn("pwned", row["payload_json"])

    def test_draft_supersession(self):
        payload = daily_payload()
        first = self.contracts.create_draft(
            ContractKind.DAILY, self.today.isoformat(), payload)
        payload["contract_line"] = "write the failing test first"
        second = self.contracts.create_draft(
            ContractKind.DAILY, self.today.isoformat(), payload)
        self.assertEqual(
            self.contracts.get(first)["state"],
            ContractState.SUPERSEDED.value)
        self.assertEqual(
            self.contracts.get(second)["supersedes"], first)

    def test_require_sealed_daily(self):
        with self.assertRaises(ContractError):
            self.contracts.require_sealed_daily(self.today)
        self.seal_today()
        row = self.contracts.require_sealed_daily(self.today)
        self.assertIn("payload", row)


class TestStateMachine(unittest.TestCase):
    def test_session_happy_path(self):
        from dhriti.state_machine import assert_transition
        assert_transition("session", SessionState.DRAFT, SessionState.SEALED)
        assert_transition("session", SessionState.SEALED, SessionState.ARMING)
        assert_transition("session", SessionState.ARMING, SessionState.ACTIVE)
        assert_transition("session", SessionState.ACTIVE, SessionState.SUCCESS)
        assert_transition("session", SessionState.ACTIVE,
                          SessionState.BREAK_GLASS)
        assert_transition("session", SessionState.ACTIVE,
                          SessionState.INTERRUPTED)
        assert_transition("session", SessionState.INTERRUPTED,
                          SessionState.INCOMPLETE)

    def test_illegal_transitions_raise(self):
        from dhriti.state_machine import assert_transition
        with self.assertRaises(StateError):
            assert_transition("session", SessionState.DRAFT,
                              SessionState.ACTIVE)  # must seal + arm
        with self.assertRaises(StateError):
            assert_transition("session", SessionState.SUCCESS,
                              SessionState.ACTIVE)   # terminal
        with self.assertRaises(StateError):
            assert_transition("session", SessionState.SEALED,
                              SessionState.SUCCESS)  # no skipping ARMING


if __name__ == "__main__":
    unittest.main()


class TestMainBeliefGroup(DhritiTestCase):
    """D-030 restoration (v0.6.0 Part 1 §5): the five-field group is
    required as a unit."""

    def test_all_five_fields_required(self):
        base = daily_payload()
        self.contracts.validate(base)  # all five present: passes
        for field in ("main_belief_metric",
                      "main_belief_current_state",
                      "substitute_activities",
                      "substitute_budget"):
            broken = dict(base)
            del broken[field]
            with self.assertRaises(ContractError) as ctx:
                self.contracts.validate(broken)
            self.assertIn("D-030", str(ctx.exception))
            self.assertIn(field, str(ctx.exception))

    def test_exchange_block_in_aftermath(self):
        payload = daily_payload()
        self.contracts.seal(self.today.isoformat(), payload)
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("## The exchange", md)
        self.assertIn("parse_decl passes its test", md)
        self.assertIn("behind on the C book chapters", md)
        self.assertIn("reading about parsers, watched talks", md)
        self.assertIn("2 hours per week", md)


class TestNightWriteCLI(DhritiTestCase):
    """Bug C (v0.6.0 Part 1 §3): the file's date is authoritative."""

    def _write_contract(self, name):
        import json as _json
        path = self.home / name
        path.write_text(_json.dumps(daily_payload()),
                        encoding="utf-8")
        return path

    def test_seal_date_mismatch_is_refused(self):
        """Bug C: sealing with --date != the file's date was silently
        accepted, storing a payload written for one day as another's
        contract."""
        from dhriti.timeutil import parse_iso
        self.clock.set(parse_iso("2026-11-02T16:00:00Z"))  # 21:30 IST
        path = self._write_contract("contract-2026-11-02.json")
        with self.assertRaises(SystemExit) as ctx:
            self._run("cmd_contract_seal",
                      {"file": str(path), "date": "2026-11-03"})
        self.assertIn("date mismatch", str(ctx.exception))

    def test_seal_date_matches_file_date(self):
        from dhriti.timeutil import parse_iso
        self.clock.set(parse_iso("2026-11-02T16:00:00Z"))
        self.days.ensure_day("2026-11-03")
        path = self._write_contract("contract-2026-11-03.json")
        self._run("cmd_contract_seal",
                  {"file": str(path), "date": "2026-11-03"})
        self.assertIsNotNone(self.contracts.for_day("2026-11-03"))

    def test_seal_date_when_file_has_no_date(self):
        """The explicit --date still works when the file name carries
        no date (a hand-authored payload)."""
        from dhriti.timeutil import parse_iso
        self.clock.set(parse_iso("2026-11-02T16:00:00Z"))
        path = self._write_contract("my-contract.json")
        self._run("cmd_contract_seal",
                  {"file": str(path), "date": "2026-11-03"})
        self.assertIsNotNone(self.contracts.for_day("2026-11-03"))


class TestMechanismsV060(DhritiTestCase):
    def test_contract_revised_event(self):
        """Mechanism 2: a draft written, edited, and sealed emits a
        contract_revised event."""
        import json, hashlib
        from dhriti.timeutil import parse_iso
        self.clock.set(parse_iso("2026-11-02T02:00:00Z"))
        payload = daily_payload()
        path = self.home / "contract-2026-11-02.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        # a draft_written event with the file's hash
        self.ledger.record(
            "contract_draft_written",
            observed={"date": "2026-11-02", "path": str(path),
                      "sha256": hashlib.sha256(
                          path.read_bytes()).hexdigest()},
            action_taken="draft written")
        # edit the file (a valid change)
        payload["contract_line"] = "revised line, still valid"
        path.write_text(json.dumps(payload), encoding="utf-8")
        # seal
        self._run("cmd_contract_seal",
                  {"file": str(path), "date": None})
        events = self.ledger.events(event_type="contract_revised")
        self.assertEqual(len(events), 1)

    def test_declared_unknowns_recorded(self):
        """Mechanism 4: uncertainty declared explicitly, shown in the
        day report's exchange block."""
        payload = daily_payload()
        payload["declared_unknowns"] = [
            {"topic": "how type inference works",
             "current_state": "unknown"},
            {"topic": "parser combinator performance",
             "current_state": "partial"},
        ]
        self.contracts.seal(self.today.isoformat(), payload)
        md = self.aftermath.day_report(self.today.isoformat())["md"]
        self.assertIn("Declared unknowns", md)
        self.assertIn("how type inference works", md)

    def test_revise_draft_records_event(self):
        """Mechanism 2 (service path): revising a DRAFT re-validates
        and records; sealed contracts refuse revision."""
        from dhriti.models import ContractKind
        cid = self.contracts.create_draft(
            ContractKind.DAILY, "2026-11-05", daily_payload())
        row = self.contracts.revise(
            cid, {"contract_line": "a better line"},
            reason="the target was wrong, cold-state fix")
        self.assertEqual(row["payload"]["contract_line"],
                         "a better line")
        events = self.ledger.events(event_type="contract_revised")
        self.assertEqual(len(events), 1)
        # sealed contracts are immutable
        self.contracts.seal_id(cid)
        with self.assertRaises(ContractError):
            self.contracts.revise(cid, {"contract_line": "nope"},
                                  reason="too late")
