"""Break-glass: the toll. Delay, typed reason, cooldown, honesty."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from dhriti.errors import BreakGlassError

from test_plumbing import DhritiTestCase


class TestBreakGlass(DhritiTestCase):
    def test_delay_honored(self):
        handle = self.break_glass.initiate()
        self.assertEqual(handle["delay_seconds"], 60)
        self.clock.advance(seconds=60)
        result = self.break_glass.confirm(
            handle["handle"], "the test suite demands it, sadly enough")
        self.assertTrue(result["honored_delay"])
        self.assertTrue(result["cooldown_until"])

    def test_delay_bypass_is_recorded_not_faked(self):
        handle = self.break_glass.initiate()
        self.clock.advance(seconds=10)  # too early — a bypass
        result = self.break_glass.confirm(
            handle["handle"], "impatient fingers typed this reason out")
        self.assertFalse(result["honored_delay"])
        bypass_events = self.ledger.events("break_glass_delay_bypassed")
        self.assertEqual(len(bypass_events), 1)

    def test_short_reason_rejected(self):
        handle = self.break_glass.initiate()
        self.clock.advance(seconds=60)
        with self.assertRaises(BreakGlassError):
            self.break_glass.confirm(handle["handle"], "too short")

    def test_cooldown_blocks_new_break_and_sessions(self):
        handle = self.break_glass.initiate()
        self.clock.advance(seconds=60)
        self.break_glass.confirm(handle["handle"],
                                 "cooldown enforcement test reason here")
        with self.assertRaises(BreakGlassError):
            self.break_glass.initiate()
        with self.assertRaises(BreakGlassError):
            self.break_glass.check_session_start_allowed()

    def test_cooldown_expires(self):
        handle = self.break_glass.initiate()
        self.clock.advance(seconds=60)
        self.break_glass.confirm(handle["handle"],
                                 "cooldown expiry test reason goes here")
        self.clock.advance(hours=3)  # cooldown is 2h
        self.break_glass.check_session_start_allowed()  # no raise
        handle2 = self.break_glass.initiate()
        self.clock.advance(seconds=60)
        self.break_glass.confirm(handle2["handle"],
                                 "a second toll, paid in full this time")


if __name__ == "__main__":
    unittest.main()
