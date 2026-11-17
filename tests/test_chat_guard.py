"""Tests for the deterministic guard core (chat_guard.py).

Law checks embedded per test name. The L-2 lint mirrors the house
FORBIDDEN_PHRASES idea: card lines are facts, never praise/shame.
"""
import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dhriti import chat_guard as cg  # noqa: E402


def fresh(mode=cg.GuardMode.CHECKPOINT, budget=15, topic="work"):
    return cg.GuardState(mode=mode, topic_label=topic, prompt_budget_limit=budget)


FORBIDDEN = ("great", "good job", "well done", "shame", "disappointed",
             "lazy", "finally", "congrats", "proud", "you failed")


class TestCardLint(unittest.TestCase):
    """L-2: the hold card never praises, never shames."""

    def test_cards_are_factual(self):
        st = fresh(topic="thesis ch2")
        d = cg.decide(st, time.time(), in_scope=False)
        for line in d.card_lines:
            for w in FORBIDDEN:
                self.assertNotIn(w, line.lower())

    def test_no_card_when_in_scope(self):
        st = fresh()
        d = cg.decide(st, time.time(), in_scope=True)
        self.assertEqual(d.action, cg.GuardAction.SEND)
        self.assertNotIn("Off-scope", " ".join(d.card_lines))


class TestModeFloor(unittest.TestCase):
    """D-076: mode mapping."""

    def test_full_lock_parks_offscope(self):
        st = fresh(mode=cg.GuardMode.FULL_LOCK)
        d = cg.decide(st, time.time(), in_scope=False)
        self.assertEqual(d.action, cg.GuardAction.PARK_ONLY)

    def test_reduced_lock_holds_with_toll(self):
        st = fresh(mode=cg.GuardMode.REDUCED_LOCK)
        d = cg.decide(st, time.time(), in_scope=False)
        self.assertEqual(d.action, cg.GuardAction.HOLD_TOLL)
        self.assertEqual(d.toll_seconds, 10)

    def test_checkpoint_collapses_offscope(self):
        st = fresh(mode=cg.GuardMode.CHECKPOINT)
        d = cg.decide(st, time.time(), in_scope=False)
        self.assertTrue(d.collapse_response)
        self.assertEqual(d.action, cg.GuardAction.SEND)

    def test_advisory_never_blocks(self):
        st = fresh(mode=cg.GuardMode.ADVISORY)
        d = cg.decide(st, time.time(), in_scope=False)
        self.assertEqual(d.action, cg.GuardAction.SEND)


class TestSidecarEscalationOnly(unittest.TestCase):
    """D-014 spirit: sidecar escalates, never silently denies."""

    def test_sidecar_park_capped_by_mode(self):
        st = fresh(mode=cg.GuardMode.ADVISORY)
        v = {"escalate": "park", "function_code": "P-15", "confidence": 0.9}
        d = cg.decide(st, time.time(), in_scope=None, sidecar_verdict=v)
        self.assertEqual(d.action, cg.GuardAction.SEND)
        self.assertTrue(d.collapse_response)   # advisory floor = collapse only

    def test_sidecar_park_in_reduced(self):
        st = fresh(mode=cg.GuardMode.REDUCED_LOCK)
        v = {"escalate": "park", "function_code": "P-15", "confidence": 0.9}
        d = cg.decide(st, time.time(), in_scope=None, sidecar_verdict=v)
        self.assertEqual(d.action, cg.GuardAction.HOLD_TOLL)

    def test_sidecar_cannot_send_in_full_lock(self):
        st = fresh(mode=cg.GuardMode.FULL_LOCK)
        v = {"escalate": None, "function_code": "advance", "confidence": 0.9}
        d = cg.decide(st, time.time(), in_scope=False, sidecar_verdict=v)
        self.assertEqual(d.action, cg.GuardAction.PARK_ONLY)


class TestBurstGovernor(unittest.TestCase):
    """D-072: rate governor, timestamps only."""

    def test_three_sends_in_window_toll(self):
        st = fresh()
        t = time.time()
        cg.decide(st, t, in_scope=True, prompt_hash="1")
        cg.decide(st, t + 1, in_scope=True, prompt_hash="2")
        self.assertFalse(cg.burst_toll_active(st, t + 2)[0])
        cg.decide(st, t + 2, in_scope=True, prompt_hash="3")
        active, toll = cg.burst_toll_active(st, t + 3)
        self.assertTrue(active)
        self.assertEqual(toll, 10)

    def test_window_expiry_clears(self):
        st = fresh()
        t = time.time()
        for i in range(3):
            cg.decide(st, t - 700 + i, in_scope=True, prompt_hash=str(i))
        active, _ = cg.burst_toll_active(st, t)
        self.assertFalse(active)


class TestDebtAntiWindup(unittest.TestCase):
    """D-079: bounded debt; freeze under FULL_LOCK; daily decay."""

    def test_ceiling_is_respected(self):
        st = fresh()
        for _ in range(50):
            cg.accrue_debt(st)
        self.assertLessEqual(st.debt.value, st.debt_cfg.ceiling)

    def test_freeze_under_full_lock(self):
        st = fresh(mode=cg.GuardMode.FULL_LOCK)
        st.debt.value = 3.0
        cg.accrue_debt(st)
        self.assertEqual(st.debt.value, 3.0)

    def test_daily_decay(self):
        from datetime import date
        st = fresh()
        st.debt.value = 5.0
        cg.decay_debt(st, date(2026, 11, 15))
        self.assertAlmostEqual(st.debt.value, 4.5)
        cg.decay_debt(st, date(2026, 11, 15))   # idempotent per day
        self.assertAlmostEqual(st.debt.value, 4.5)


class TestSchmitt(unittest.TestCase):
    """D-078: asymmetric taper transitions; no chattering."""

    def test_breach_tightens_immediately(self):
        st = fresh()
        st.taper_index = 1
        cg.schmitt_step(st, breach=True)
        self.assertEqual(st.mode, cg.GuardMode.REDUCED_LOCK)
        self.assertEqual(st.clean_streak, 0)

    def test_relax_needs_streak(self):
        st = fresh()
        st.taper_index = 2
        cg.schmitt_step(st, breach=False)
        cg.schmitt_step(st, breach=False)
        self.assertEqual(st.taper_index, 2)    # 2 < down_days=3
        cg.schmitt_step(st, breach=False)
        self.assertEqual(st.taper_index, 1)

    def test_cannot_exceed_ladder(self):
        st = fresh()
        st.taper_index = len(cg.TAPER_LADDER) - 1
        for _ in range(5):
            cg.schmitt_step(st, breach=True)
        self.assertEqual(st.mode, cg.GuardMode.FULL_LOCK)


class TestThreadInterlock(unittest.TestCase):
    """D-082: the key to thread N+1 is the disposal of thread N."""

    def test_second_open_refused_while_first_open(self):
        st = fresh()
        ok1, _, _ = cg.open_thread(st, "t1", "chatgpt", 1.0)
        ok2, reason, _ = cg.open_thread(st, "t2", "chatgpt", 2.0)
        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertEqual(reason, cg.R_THREAD_INTERLOCK)

    def test_disposal_frees_the_key(self):
        st = fresh()
        cg.open_thread(st, "t1", "chatgpt", 1.0)
        cg.dispose_thread(st, "t1", "parked", 2.0)
        ok, reason, _ = cg.open_thread(st, "t2", "chatgpt", 3.0)
        self.assertTrue(ok)

    def test_full_lock_zero_pivots(self):
        st = fresh(mode=cg.GuardMode.FULL_LOCK)
        ok, reason, _ = cg.open_thread(st, "t1", "chatgpt", 1.0)
        self.assertFalse(ok)
        self.assertEqual(reason, cg.R_PIVOT_BUDGET)

    def test_invalid_disposition_refused(self):
        st = fresh()
        cg.open_thread(st, "t1", "chatgpt", 1.0)
        with self.assertRaises(ValueError):
            cg.dispose_thread(st, "t1", "whatever", 2.0)


class TestBudget(unittest.TestCase):
    """L-5: the pass budget is a ceiling."""

    def test_budget_exhausted_parks(self):
        st = fresh(budget=2)
        t = time.time()
        cg.decide(st, t, in_scope=True, prompt_hash="1")
        cg.decide(st, t + 1, in_scope=True, prompt_hash="2")
        d = cg.decide(st, t + 2, in_scope=True, prompt_hash="3")
        self.assertEqual(d.reason, cg.R_BUDGET_EXHAUSTED)

    def test_snapshot_shapes(self):
        st = fresh()
        snap = cg.snapshot_for_digest(st, time.time())
        for key in ("mode", "debt_value", "open_threads", "bursting",
                    "prompt_budget_used", "sidecar_armed"):
            self.assertIn(key, snap)

    def test_roundtrip_snapshot(self):
        st = fresh()
        cg.open_thread(st, "t9", "claude", 1.0)
        st2 = cg.GuardState.from_snapshot(st.to_snapshot())
        self.assertIn("t9", st2.threads)
        self.assertEqual(st2.topic_label, st.topic_label)


if __name__ == "__main__":
    unittest.main()
