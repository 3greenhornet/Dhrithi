"""D-048 + D-049 — the evening.

D-048: enforcement ends at window_end; observation (counts only) may
run on until day_end when observation_evening is enabled — the hole
becomes measured, not closed.

D-049: the earned evening. On a closed day whose targets were NOT met,
the configured consumption categories stay blocked until day_end
(bounded, D-018). Days that met their targets release to an open
evening: consumption is earned by evidence, not by the clock. Default
OFF; enabling is a cold-state act, exactly like the builder clause."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhriti.aftermath import AftermathService

from test_plumbing import DhritiTestCase, daily_payload


class TestEarnedEvening(DhritiTestCase):
    def _closed_incomplete_day(self, **cfg):
        """Seal a contract, open the day, miss the targets, close it."""
        self.seal_today()
        daemon = self.make_daemon(**cfg)
        daemon._tick()                       # 10:00 IST — day opens
        self.clock.advance(hours=11)         # 21:00 IST — window_end
        daemon._tick()                       # day closes
        return daemon

    def test_default_off_no_earned_enforcement(self):
        daemon = self._closed_incomplete_day()
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], "CLOSED_INCOMPLETE")
        policy = daemon._current_extension_policy()
        self.assertFalse(policy["enforce"])
        self.assertNotIn("earned_evening_applied",
                         [e["event_type"] for e in daemon.ledger.events()])
        daemon.release_lock()
        daemon.db.close()

    def test_unmet_targets_block_consumption_until_day_end(self):
        daemon = self._closed_incomplete_day(earned_evening={
            "enabled": True})
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], "CLOSED_INCOMPLETE")
        policy = daemon._current_extension_policy()
        self.assertTrue(policy["enforce"])
        self.assertEqual(policy["mode"], "earned_evening")
        self.assertIn("youtube.com", policy["blocked_domains"])
        self.assertIn("chatgpt.com", policy["blocked_domains"])
        # bounded: expires at day_end (23:59 IST == 18:29 UTC), never later
        self.assertEqual(policy["expires_at"], "2026-11-02T18:29:00Z")
        # search must stay reachable — google.com is not consumption
        self.assertNotIn("google.com", policy["blocked_domains"])
        # the wall page still speaks only the user's own contract line
        self.assertEqual(policy["contract_line"],
                         "reverse the array in Java")
        # the event fires exactly once per day
        daemon._current_extension_policy()
        daemon._current_extension_policy()
        events = [e for e in daemon.ledger.events()
                  if e["event_type"] == "earned_evening_applied"]
        self.assertEqual(len(events), 1)
        daemon.release_lock()
        daemon.db.close()

    def test_bounded_release_at_day_end(self):
        daemon = self._closed_incomplete_day(earned_evening={
            "enabled": True})
        self.assertTrue(daemon._current_extension_policy()["enforce"])
        self.clock.advance(hours=3)               # 18:30 UTC — past day_end
        policy = daemon._current_extension_policy()
        self.assertFalse(policy["enforce"])       # never indefinite (D-018)
        daemon.release_lock()
        daemon.db.close()

    def test_met_targets_earn_an_open_evening(self):
        self.seal_today()
        daemon = self.make_daemon(earned_evening={"enabled": True})
        daemon._tick()
        sess = daemon.start_session("reverse the array")
        daemon.evidence.machine_check_command(
            sess["id"], "python3 -c \"print('sorted')\"")
        daemon.end_session_success(sess["id"])
        self.clock.advance(hours=10, minutes=2)   # day_close, targets met
        daemon._tick()
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], "RELEASED_EARLY")
        policy = daemon._current_extension_policy()
        self.assertFalse(policy["enforce"])       # earned: evening open
        self.assertNotIn("earned_evening_applied",
                         [e["event_type"] for e in daemon.ledger.events()])
        daemon.release_lock()
        daemon.db.close()


class TestEveningObservation(DhritiTestCase):
    def _evening(self, **cfg):
        self.seal_today()
        daemon = self.make_daemon(**cfg)
        daemon._tick()                       # day opens
        self.clock.advance(hours=11)         # past window_end
        daemon._tick()                       # day closes
        return daemon

    def test_marker_event_once_per_day_and_whole_day_facts(self):
        daemon = self._evening(observation_evening={"enabled": True})
        self.assertTrue(daemon._evening_observation_active())
        daemon._tick()
        daemon._tick()
        markers = [e for e in daemon.ledger.events()
                   if e["event_type"] == "evening_observation_active"]
        self.assertEqual(len(markers), 1)
        # an evening navigation (21:30 IST, session-less) is observed
        self.clock.advance(minutes=30)
        daemon.ledger.record(
            "browser_navigation", source_adapter="extension",
            observed_payload={"url": "https://www.youtube.com/watch?v=x",
                              "title": ""})
        aftermath = AftermathService(daemon.db, daemon.config, daemon.clock,
                                     daemon.ledger)
        md = aftermath.day_report(daemon.days.get(self.today))["markdown"]
        self.assertIn("video: 1", md)
        self.assertIn("after window_end (evening)", md)
        self.assertIn("1 after window_end", md)
        daemon.release_lock()
        daemon.db.close()

    def test_observation_ends_at_day_end(self):
        daemon = self._evening(observation_evening={"enabled": True})
        self.assertTrue(daemon._evening_observation_active())
        self.clock.advance(hours=3)               # 18:30 UTC — past 23:59 IST
        self.assertFalse(daemon._evening_observation_active())
        daemon.release_lock()
        daemon.db.close()

    def test_disabled_by_default(self):
        daemon = self._evening()
        self.assertFalse(daemon._evening_observation_active())
        self.assertNotIn(
            "evening_observation_active",
            [e["event_type"] for e in daemon.ledger.events()])
        daemon.release_lock()
        daemon.db.close()


class TestObservationEndResolution(unittest.TestCase):
    def test_day_end_never_precedes_window_end(self):
        from dhriti.day_window import resolve_observation_end, resolve_window
        import datetime as _dt
        from dhriti.timeutil import parse_iso
        config = {"timezone": "Asia/Kolkata",
                  "day_window": {"start": "10:00", "day_close": "20:00",
                                 "end": "21:00"},
                  "observation_evening": {"enabled": True,
                                          "day_end": "18:00"}}  # incoherent
        date = _dt.date(2026, 11, 2)
        obs_end = resolve_observation_end(date, config)
        win = resolve_window(date, config)
        self.assertGreaterEqual(obs_end, win.window_end)
        self.assertEqual(obs_end, win.window_end)


if __name__ == "__main__":
    unittest.main()
