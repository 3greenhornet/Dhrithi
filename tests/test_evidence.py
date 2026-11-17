"""Evidence classes, verdicts, and proof rules (PDF section 6)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from test_plumbing import DhritiTestCase, daily_payload


class TestEvidence(DhritiTestCase):
    def test_machine_checked_command_success(self):
        sess = self.start_session("task")
        ev = self.evidence.machine_check_command(
            sess["id"], "reversal passes its test",
            "python3 -c \"print('ok')\"")
        self.assertEqual(ev["verdict"], "ACCEPTED")
        self.assertEqual(ev["class"], "MACHINE_CHECKED")

    def test_machine_checked_command_failure(self):
        sess = self.start_session("task")
        ev = self.evidence.machine_check_command(
            sess["id"], "reversal passes its test",
            "python3 -c \"import sys; sys.exit(2)\"")
        self.assertEqual(ev["verdict"], "REJECTED")

    def test_documented_failure_counts_when_declared(self):
        sess = self.start_session("task")
        ev = self.evidence.machine_check_command(
            sess["id"], "documented failure",
            "python3 -c \"import sys; sys.exit(2)\"",
            accept_nonzero_exit=True)
        self.assertEqual(ev["verdict"], "ACCEPTED")

    def test_file_evidence_hashes(self):
        target = self.home / "ReverseArray.java"
        target.write_text("class ReverseArray {}", encoding="utf-8")
        sess = self.start_session("task")
        ev = self.evidence.submit_file(
            sess["id"], "notes written", str(target))
        self.assertEqual(ev["verdict"], "ACCEPTED")
        self.assertIn("sha256", ev["detail"])

    def test_file_not_found_is_recorded_not_crashed(self):
        sess = self.start_session("task")
        ev = self.evidence.submit_file(
            sess["id"], "notes written",
            str(self.home / "missing.md"))
        self.assertEqual(ev["verdict"], "REJECTED")
        self.assertIn("file not found", ev["verdict_reason"])

    def test_manual_claim_is_not_proof(self):
        sess = self.start_session("task")
        ev = self.evidence.submit_manual(
            sess["id"], "notes written", "I swear I did it")
        self.assertEqual(ev["verdict"], "REJECTED",
                         "a claim is not proof — kept for review only")

    def test_command_not_found_is_recorded_not_crashed(self):
        sess = self.start_session("task")
        ev = self.evidence.machine_check_command(
            sess["id"], "reversal passes its test",
            "definitely-not-a-command-xyz --run")
        self.assertEqual(ev["detail"]["exit_code"], None)
        self.assertIn("not found", ev["detail"]["error"])

    def test_target_match_drives_day_targets(self):
        """A target with a named command is met only by that command;
        a file target by a submitted file of that name."""
        sess = self.start_session("task")
        (self.home / "notes.md").write_text("notes", encoding="utf-8")
        # wrong command first: does not satisfy the target
        self.evidence.machine_check_command(
            sess["id"], "reversal passes its test", "echo wrong")
        day = self.days.get(self.today)
        self.assertFalse(self.days.targets_met(day))
        # the declared command + the declared file: satisfies both
        self.evidence.machine_check_command(
            sess["id"], "reversal passes its test",
            daily_payload()["targets"][0]["evidence"]["command"])
        self.evidence.submit_file(
            sess["id"], "notes written", str(self.home / "notes.md"))
        day = self.days.get(self.today)
        self.assertTrue(self.days.targets_met(day))


if __name__ == "__main__":
    unittest.main()


class TestWorkspaceResolution(DhritiTestCase):
    """Bug D (v0.6.0 Part 1 §4): evidence paths resolve against the
    contract's workspace_dir, never the CLI's CWD."""

    def test_relative_path_resolves_against_workspace(self):
        workspace = self.home / "workspace"
        workspace.mkdir()
        (workspace / "notes.md").write_text("correct", encoding="utf-8")
        (self.home / "notes.md").write_text("WRONG", encoding="utf-8")
        session = self.start_session()
        row = self.evidence.submit_file(
            session["id"], "notes written", "notes.md",
            workspace=workspace)
        self.assertEqual(row["verdict"], "ACCEPTED")
        # the correct file was hashed
        import hashlib
        expected = hashlib.sha256(
            (workspace / "notes.md").read_bytes()).hexdigest()
        self.assertEqual(row["detail"]["sha256"], expected)

    def test_relative_path_without_workspace_resolves_to_home_not_cwd(self):
        (self.home / "notes.md").write_text("at home", encoding="utf-8")
        self.evidence.home = self.home
        session = self.start_session()
        import os
        old_cwd = os.getcwd()
        os.chdir("/tmp")  # the wrong place
        try:
            row = self.evidence.submit_file(
                session["id"], "notes written", "notes.md")
        finally:
            os.chdir(old_cwd)
        self.assertEqual(row["verdict"], "ACCEPTED")
        import hashlib
        expected = hashlib.sha256(
            (self.home / "notes.md").read_bytes()).hexdigest()
        self.assertEqual(row["detail"]["sha256"], expected)

    def test_machine_command_runs_in_workspace(self):
        import sys
        workspace = self.home / "workspace"
        workspace.mkdir()
        (workspace / "flag.txt").write_text("ok", encoding="utf-8")
        session = self.start_session()
        cmd = f'"{sys.executable}" -c "import os, sys; sys.exit(0 if os.path.exists(\'flag.txt\') else 1)"'
        row = self.evidence.machine_check_command(
            session["id"], "target", cmd, workspace=workspace)
        self.assertEqual(row["verdict"], "ACCEPTED")
