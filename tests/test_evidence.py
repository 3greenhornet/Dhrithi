"""Evidence classes, verdicts, and proof rules (PDF section 6)."""

import json

from test_plumbing import DhritiTestCase, daily_payload


class TestEvidence(DhritiTestCase):
    def _session(self, spec='[{"kind":"command"}]'):
        self.seal_today()
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        return self.sessions.start(day["id"], "task", spec)

    def test_machine_checked_command_success(self):
        sess = self._session()
        ev = self.evidence.machine_check_command(
            sess["id"], "python3 -c \"print('ok')\"")
        self.assertEqual(ev["verdict"], "ACCEPTED")
        self.assertEqual(ev["class"], "MACHINE_CHECKED")

    def test_machine_checked_command_failure(self):
        sess = self._session()
        ev = self.evidence.machine_check_command(
            sess["id"], "python3 -c \"import sys; sys.exit(2)\"")
        self.assertEqual(ev["verdict"], "REJECTED")

    def test_documented_failure_counts_when_declared(self):
        self.seal_today(daily_payload())
        day = self.days.ensure_day(self.today)
        day = self.days.try_open(day)
        sess = self.sessions.start(
            day["id"], "task",
            json.dumps([{"kind": "command", "accept_nonzero_exit": True}]))
        ev = self.evidence.machine_check_command(
            sess["id"], "python3 -c \"import sys; sys.exit(2)\"")
        self.assertEqual(ev["verdict"], "ACCEPTED")

    def test_file_evidence_hashes(self):
        target = self.home / "ReverseArray.java"
        target.write_text("class ReverseArray {}", encoding="utf-8")
        sess = self._session(spec='[{"kind":"file"}]')
        ev = self.evidence.submit_file(sess["id"], str(target))
        self.assertEqual(ev["verdict"], "ACCEPTED")
        self.assertIn("sha256", ev["detail"])

    def test_manual_claim_is_not_proof(self):
        sess = self._session()
        ev = self.evidence.submit_manual(sess["id"], "I swear I did it")
        self.assertEqual(ev["verdict"], "REJECTED",
                         "a claim is not proof — kept for review only")

    def test_kind_mismatch_rejected(self):
        sess = self._session()
        ev = self.evidence.submit_manual(sess["id"], "honest note anyway")
        self.assertEqual(ev["verdict"], "REJECTED")

    def test_screenshot_is_disabled_placeholder(self):
        from dhriti.errors import DisabledFeature
        sess = self._session()
        with self.assertRaises(DisabledFeature) as ctx:
            self.evidence.submit_screenshot(sess["id"], "x.png")
        self.assertIn("vision-proof", str(ctx.exception))

    def test_command_not_found_is_recorded_not_crashed(self):
        sess = self._session()
        ev = self.evidence.machine_check_command(
            sess["id"], "definitely-not-a-command-xyz --run")
        self.assertEqual(ev["detail"]["exit_code"], None)
        self.assertIn("not found", ev["detail"]["error"])


if __name__ == "__main__":
    unittest.main()
