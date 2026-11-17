"""Tests for guard metrics, crosscheck, canary, verdict fusion, anchors."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dhriti.guard_metrics import (kill_chain_attribution,  # noqa: E402
                                  novelty_domains, park_break_ratio,
                                  render_guard_block, sensor_conflict)
from dhriti.classifier_sidecar.verdict import fuse  # noqa: E402
from dhriti.canary import check_e2_canary           # noqa: E402
from dhriti.anchor_proof import (canonical, event_hash,  # noqa: E402
                                 verify_segment, export_segment,
                                 verify_bundle)


class TestParkBreakRatio(unittest.TestCase):
    """D-085: near-miss pyramid as a leading indicator."""

    def test_healthy_ratio(self):
        r = park_break_ratio([{"label": "w1", "parks": 9, "breaks": 2}])
        self.assertTrue(r["healthy"])
        self.assertEqual(r["ratio"], 4.5)

    def test_routed_around_flag(self):
        r = park_break_ratio([
            {"label": "w1", "parks": 9, "breaks": 2},
            {"label": "w2", "parks": 1, "breaks": 2},
        ])
        self.assertTrue(r["routed_around"])

    def test_empty_series_honest(self):
        r = park_break_ratio([])
        self.assertIsNone(r["healthy"])
        self.assertEqual(r["note"], "no data")


class TestKillChain(unittest.TestCase):
    def test_counts_and_dominant(self):
        evs = [{"type": "guard_send_held", "stage": "send_held"},
               {"type": "guard_send_held", "stage": "send_held"},
               {"type": "guard_response_hidden", "stage": "response_hidden"}]
        c = kill_chain_attribution(evs)
        self.assertEqual(c["counts"]["send_held"], 2)
        self.assertEqual(c["dominant_stage"], "send_held")


class TestNovelty(unittest.TestCase):
    def test_novel_domains_detected(self):
        out = novelty_domains({"a.com", "b.com"},
                              {"c.com": 4, "a.com": 9, "d.com": 2}, 3)
        self.assertEqual([d["domain"] for d in out], ["c.com"])
        self.assertEqual(out[0]["count"], 4)


class TestSensorConflict(unittest.TestCase):
    """D-080: disagreement as bypass detector."""

    def test_conflict_detected(self):
        c = sensor_conflict(aw_browser_minutes=12.0, ext_nav_events=0)
        self.assertIsNotNone(c)
        self.assertEqual(c["hypothesis"], "other_browser_or_blind_adapter")

    def test_agreement_no_conflict(self):
        self.assertIsNone(sensor_conflict(12.0, 30))
        self.assertIsNone(sensor_conflict(0.0, 0))

    def test_dead_sensor_proves_nothing(self):
        self.assertIsNone(sensor_conflict(12.0, 0, aw_quality="MISSING"))


class TestVerdictFusion(unittest.TestCase):
    """Two-axis fusion: leap overrides adjacency; ambiguous band collapses."""

    def test_on_topic_no_escalation(self):
        v = fuse(0.85, "advance", 0.9)
        self.assertIsNone(v.escalate)

    def test_leap_overrides_adjacency(self):
        v = fuse(0.85, "P-15", 0.8)
        self.assertEqual(v.escalate, "park")

    def test_low_score_parks(self):
        v = fuse(0.2, "advance", 0.5)
        self.assertEqual(v.escalate, "park")

    def test_ambiguous_band_collapses(self):
        v = fuse(0.55, "advance", 0.5)
        self.assertEqual(v.escalate, "collapse")

    def test_malicious_payload_failsafe(self):
        v = fuse(0.9, "P-99", 0.9).validate()
        self.assertEqual(v.function_code, "unknown")
        v2 = fuse(0.9, "advance", 0.9)
        v2.escalate = "nuke"
        v2.validate()
        self.assertIsNone(v2.escalate)


class TestCanary(unittest.TestCase):
    """D-081: E2 tamper canary."""

    def test_alive_when_blackholed(self):
        def fake_resolver(host, _):
            return [(2, 1, 6, "", ("0.0.0.0", 0))]
        r = check_e2_canary("dhriti-canary.invalid", resolver=fake_resolver)
        self.assertTrue(r["ok"])
        self.assertEqual(r["status"], "alive")

    def test_tampered_when_public(self):
        def fake_resolver(host, _):
            return [(2, 1, 6, "", ("93.184.216.34", 0))]
        r = check_e2_canary("dhriti-canary.invalid", resolver=fake_resolver)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "tampered")

    def test_missing_entry_when_nxdomain(self):
        def fake_resolver(host, _):
            raise socket_gaierror()
        r = check_e2_canary("dhriti-canary.invalid", resolver=fake_resolver)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "missing_entry")


def socket_gaierror():
    import socket
    return socket.gaierror(8, "nodename nor servname")


class TestAnchorProof(unittest.TestCase):
    """D-084: witness verifies without content trust."""

    def _chain(self):
        evs = []
        prev = "genesis"
        for i in range(5):
            ev = {"seq": i, "type": "guard_send_held", "n": i}
            ev["hash"] = event_hash(prev, ev)
            evs.append(ev)
            prev = ev["hash"]
        return evs

    def test_valid_segment_verifies(self):
        evs = self._chain()
        bundle = export_segment(evs, anchor_seq=1)
        ok, detail = verify_bundle(bundle)
        self.assertTrue(ok, detail)

    def test_tampered_event_fails(self):
        evs = self._chain()
        evs[3]["n"] = 999                     # silently edited?
        bundle = export_segment(evs, anchor_seq=1)
        ok, _ = verify_bundle(bundle)
        self.assertFalse(ok)

    def test_canonical_stable(self):
        self.assertEqual(canonical({"b": 1, "a": 2}), canonical({"a": 2, "b": 1}))


class TestDigestBlock(unittest.TestCase):
    def test_render_includes_flags(self):
        from dhriti.guard_metrics import render_guard_block as rgb
        md = rgb({"mode": "checkpoint", "prompt_budget_used": 3,
                  "prompt_budget_limit": 15, "debt_value": 1.5,
                  "debt_ceiling": 10, "debt_frozen": False,
                  "open_threads": ["/t1"], "bursting": False,
                  "clean_streak": 1, "taper_stage": "checkpoint",
                  "sidecar_armed": False},
                 {"ratio": 3.2, "healthy": True, "routed_around": False,
                  "note": ""},
                 {"dominant_stage": "send_held", "total": 5},
                 [{"domain": "c.com", "count": 4}])
        self.assertIn("Guard", md)
        self.assertIn("c.com", md)
        self.assertIn("checkpoint", md)


if __name__ == "__main__":
    unittest.main()
