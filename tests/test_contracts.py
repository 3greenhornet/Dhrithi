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
