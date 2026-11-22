"""Day-window model: the resolution of the PDF/dossier contradiction.

Invariants under test (docs/RESOLUTIONS.md R1):
  * a day cannot OPEN without a sealed daily contract;
  * early release requires targets met AND now >= day_close;
  * window_end is an unconditional ceiling — nothing extends it;
  * finishing targets early does NOT release before day_close;
  * a day that never got a contract closes INCOMPLETE at window_end;
  * an open day left behind by a dead daemon is RECOVERED honestly.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from dhriti.models import DayState

from test_plumbing import CLOCK_START, DhritiTestCase


class TestDayWindow(DhritiTestCase):
    def test_window_resolution(self):
        from dhriti.day_window import resolve_window
        win = resolve_window(self.today, self.config)
        # local 10:00 (IST) == 04:30 UTC on 2026-11-02
        self.assertEqual(win.window_start, CLOCK_START)
        # local 20:00 day_close == 14:30 UTC; 21:00 window_end == 15:30 UTC
        from datetime import timezone
        self.assertEqual(win.day_close.astimezone(timezone.utc).hour, 14)
        self.assertEqual(win.window_end.astimezone(timezone.utc).hour, 15)
        self.assertLess(win.window_start, win.day_close)
        self.assertLess(win.day_close, win.window_end)

    def test_no_contract_no_open(self):
        day = self.days.ensure_day(self.today)
        self.assertEqual(day["state"], DayState.NO_CONTRACT.value)
        day = self.days.try_open(day)
        self.assertEqual(day["state"], DayState.NO_CONTRACT.value)

    def test_contract_then_open_at_window_start(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        self.assertEqual(day["state"], DayState.PLANNED.value)
        day = self.days.try_open(day)
        self.assertEqual(day["state"], DayState.OPEN.value)

    def test_early_finish_does_not_release_before_day_close(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        # simulate: session already succeeded (targets met) at 10:05
        self.clock.advance(minutes=5)
        day = self.days.evaluate(day, targets_met_now=True)
        self.assertEqual(day["state"], DayState.OPEN.value,
                         "easy-contract loophole: no release before "
                         "day_close (PDF 3.7)")

    def test_early_release_at_day_close_with_targets(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        self.clock.advance(hours=10, minutes=1)  # 20:01 local
        day = self.days.evaluate(day, targets_met_now=True)
        self.assertEqual(day["state"], DayState.RELEASED_EARLY.value)

    def test_no_early_release_without_targets(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        self.clock.advance(hours=10, minutes=1)
        day = self.days.evaluate(day, targets_met_now=False)
        self.assertEqual(day["state"], DayState.OPEN.value)

    def test_window_end_is_unconditional_ceiling(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        self.clock.advance(hours=11, minutes=1)  # past 21:00 local
        day = self.days.evaluate(day, targets_met_now=False)
        self.assertEqual(day["state"], DayState.CLOSED_INCOMPLETE.value)
        self.assertIsNotNone(day["released_at"])

    def test_targets_met_by_window_end_closes_complete(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        self.clock.advance(hours=11, minutes=1)
        day = self.days.evaluate(day, targets_met_now=True)
        self.assertEqual(day["state"], DayState.CLOSED_COMPLETE.value)

    def test_dead_daemon_day_is_recovered(self):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        # daemon never runs again; a week later, recovery sees it
        self.clock.advance(days=7)
        recovered = self.days.recover_open_days()
        self.assertIn(day["id"], recovered)
        self.assertEqual(
            self.days.get(self.today)["state"], DayState.RECOVERED.value)

    def test_no_contract_day_closes_incomplete_at_end(self):
        day = self.days.ensure_day(self.today)
        self.clock.advance(hours=11, minutes=1)
        day = self.days.evaluate(day, targets_met_now=False)
        self.assertEqual(day["state"], DayState.CLOSED_INCOMPLETE.value)


    def test_learning_evidence_satisfies_targets_met(self):
        from test_plumbing import payload_for
        from dhriti.learning_proof import LearningProofService
        payload = payload_for(self.home)
        payload["targets"] = [
            {"id": "t-learn-1", "label": "Dynamic Programming Study", "evidence": {"class": "learning"}}
        ]
        self.seal_today(payload)
        day = self.days.ensure_day(self.today)

        # Before proof: targets are not met
        self.assertFalse(self.days.targets_met(day))

        # Claim proof via LearningProofService
        svc = LearningProofService(self.db, ledger=self.ledger)
        synthesis = (
            "Dynamic programming solves subproblems once and memoizes results for future lookups. "
            "In this study session, we traced optimal substructure and overlapping subproblems in "
            "the classic longest common subsequence problem, calculating state transitions O(N*M) "
            "space and time complexity while comparing bottom-up tabulation against top-down memoization "
            "with full recursive call tree proofs and space optimization."
        )
        res = svc.claim_with_proof("t-learn-1", synthesis, scope_date=self.today.isoformat())
        self.assertTrue(res["ok"])

        # Now targets_met must be True (The Day Can Be Won)
        self.assertTrue(self.days.targets_met(day))


if __name__ == "__main__":
    unittest.main()
