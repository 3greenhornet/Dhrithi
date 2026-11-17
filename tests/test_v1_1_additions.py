"""Dhriti Guard Kit v1.1 -- tests for the additions mined from the
raw-material audit (D-087 hosts bypass audit, D-088 external CLI probe,
ActivityWatch bug-aware quality hint, Sysmon/4688 lineage conflict).
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

try:
    from dhriti.canary import audit_hosts_entries, normalize_hostname, \
        check_e2_canary
    from dhriti.observer_crosscheck import aw_quality_hint, lineage_conflict
    from dhriti.external_cli_probe import (audit_gate, list_processes,
                                           rename_bypass_canary,
                                           run_cli, cold_turkey_status)
except ImportError:  # pragma: no cover
    from canary import audit_hosts_entries, normalize_hostname, check_e2_canary  # type: ignore
    from observer_crosscheck import aw_quality_hint, lineage_conflict  # type: ignore
    from external_cli_probe import (audit_gate, list_processes,  # type: ignore
                                    rename_bypass_canary, run_cli,
                                    cold_turkey_status)


class TestNormalizeHostname(unittest.TestCase):
    def test_case_and_trailing_dot(self):
        self.assertEqual(normalize_hostname("ChatGPT.COM."),
                         "chatgpt.com")

    def test_www_is_distinct_on_purpose(self):
        # the whole point of D-087: www is a separate entry, and
        # conflating them IS the bypass
        self.assertNotEqual(normalize_hostname("www.chatgpt.com"),
                            normalize_hostname("chatgpt.com"))


class TestHostsAudit(unittest.TestCase):
    def test_clean_block_produces_no_hard_findings(self):
        content = ("0.0.0.0 chatgpt.com\n"
                   "0.0.0.0 www.chatgpt.com\n"
                   "0.0.0.0 gemini.google.com\n"
                   "0.0.0.0 www.gemini.google.com\n")
        out = audit_hosts_entries(content)
        self.assertEqual(out["hard"], [])
        self.assertEqual(out.get("event"), None)

    def test_public_ip_is_hard_finding(self):
        out = audit_hosts_entries("0.0.0.0 chatgpt.com\n"
                                  "142.250.4.100 chatgpt.com\n")
        kinds = [f["kind"] for f in out["hard"]]
        self.assertIn("non_blackhole_ip", kinds)
        self.assertEqual(out["event"], "guard_e2_block_bypass_risk")

    def test_www_gap_is_flagged(self):
        out = audit_hosts_entries("0.0.0.0 deepseek.com\n")
        kinds = [f["kind"] for f in out["soft"]]
        self.assertIn("www_gap", kinds)

    def test_punycode_is_hard(self):
        out = audit_hosts_entries("0.0.0.0 xn--pple-43d.com\n")
        kinds = [f["kind"] for f in out["hard"]]
        self.assertIn("punycode", kinds)

    def test_canary_invalid_never_flagged(self):
        out = audit_hosts_entries("0.0.0.0 dhriti-canary.invalid\n")
        self.assertEqual(out["findings"], [])

    def test_mixed_case_soft(self):
        out = audit_hosts_entries("0.0.0.0 ChatGPT.com\n")
        kinds = [f["kind"] for f in out["soft"]]
        self.assertIn("mixed_case", kinds)

    def test_never_raises_on_garbage(self):
        out = audit_hosts_entries("# comment\n\nxxx\n0.0.0.0\n")
        self.assertIn("checked_lines", out)


class TestE2CanaryStillWorks(unittest.TestCase):
    def test_alive(self):
        def resolver(host, port):
            return [(2, 1, 6, "", ("0.0.0.0", 0))]
        out = check_e2_canary("dhriti-canary.invalid", resolver=resolver)
        self.assertTrue(out["ok"])

    def test_tampered(self):
        def resolver(host, port):
            return [(2, 1, 6, "", ("93.184.216.34", 0))]
        out = check_e2_canary("dhriti-canary.invalid", resolver=resolver)
        self.assertFalse(out["ok"])
        self.assertEqual(out["event"], "guard_e2_canary_missing")


class TestAWQualityHint(unittest.TestCase):
    def test_missing_on_poll_failure(self):
        self.assertEqual(aw_quality_hint(None, polled=True), "MISSING")
        self.assertEqual(aw_quality_hint([{"data": {"app": "chrome",
                                                    "duration": 5}}],
                                         polled=False), "MISSING")

    def test_suspect_is_pr561_signature(self):
        ev = [{"data": {"app": "chrome", "duration": 0}},
              {"data": {"app": "msedge", "duration": 0}}]
        self.assertEqual(aw_quality_hint(ev, polled=True), "SUSPECT")

    def test_degraded_empty_but_reachable(self):
        self.assertEqual(aw_quality_hint([], polled=True), "DEGRADED")

    def test_ok_with_real_durations(self):
        ev = [{"data": {"app": "chrome", "duration": 30}}]
        self.assertEqual(aw_quality_hint(ev, polled=True), "OK")


class TestLineageConflict(unittest.TestCase):
    def test_agreement_is_none(self):
        self.assertIsNone(lineage_conflict("explorer.exe", "Explorer.EXE"))

    def test_unknown_sensor_is_not_a_conflict(self):
        self.assertIsNone(lineage_conflict(None, "svc.exe"))
        self.assertIsNone(lineage_conflict("", "svc.exe"))

    def test_disagreement_recorded(self):
        out = lineage_conflict("chrome.exe", "cmd.exe")
        self.assertIsNotNone(out)
        self.assertEqual(out["event"], "guard_lineage_conflict")
        self.assertTrue(out["conflict"])


class TestExternalCliProbe(unittest.TestCase):
    def test_run_cli_missing_binary_honest(self):
        out = run_cli("definitely-not-a-real-binary-xyz", ["-status"])
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "FAILED")

    def test_rename_bypass_detected(self):
        names = ["explorer.exe", "chrome.exe"]
        out = rename_bypass_canary(names, locked_claimed=True)
        self.assertTrue(out["bypass_risk"])
        self.assertEqual(out["event"], "guard_stack_bypass_risk")
        self.assertIn("ServiceHub.Power", out["missing"])

    def test_no_risk_when_services_present(self):
        names = list(__import__("dhriti.external_cli_probe",
                                fromlist=["CT_EXPECTED_PROCESSES"])
                     .CT_EXPECTED_PROCESSES)
        out = rename_bypass_canary(names, locked_claimed=True)
        self.assertFalse(out["bypass_risk"])

    def test_no_risk_when_no_block_claimed(self):
        out = rename_bypass_canary([], locked_claimed=False)
        self.assertFalse(out["bypass_risk"])

    def test_list_processes_injectable(self):
        raw = '"ServiceHub.Power","123",Running\n"chrome.exe","456",Running\n'
        names = list_processes(lister=lambda: raw)
        self.assertIn("ServiceHub.Power", names)
        self.assertIn("chrome.exe", names)

    def test_audit_gate_not_installed_honest(self):
        out = audit_gate(cli_path="")
        self.assertFalse(out["armed"])
        self.assertEqual(out["checks"]["presence"],
                         "NOT_INSTALLED (honest placeholder)")

    def test_cold_turkey_status_machine_checked(self):
        # injected path that doesn't exist -> FAILED, honest, never raises
        out = cold_turkey_status("definitely-not-a-real-binary-xyz")
        self.assertEqual(out["status"], "FAILED")
        self.assertFalse(out["locked"])


if __name__ == "__main__":
    unittest.main()
