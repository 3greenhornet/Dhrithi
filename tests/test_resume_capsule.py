"""Unit tests for the Resume Capsule / Return Anchor mechanism."""

import json
import tempfile
import unittest
from pathlib import Path

from dhriti.db import Database
from dhriti.session import SessionService
from dhriti.timeutil import SimulatedClock, parse_iso


class TestResumeCapsule(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.db = Database(self.home / "test.sqlite3")
        self.clock = SimulatedClock(parse_iso("2026-11-17T10:00:00Z"))
        self.sessions = SessionService(self.db, self.clock)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_session_create_with_resume_capsule(self):
        sess = self.sessions.create(
            day_id="day-1",
            contract_id="contract-1",
            task="LeetCode 238 Product of Array Except Self",
            next_action="Implement prefix product array loop",
            blocker="Edge case with multiple zeros"
        )
        self.assertIsNotNone(sess["outcome_json"])
        data = json.loads(sess["outcome_json"])
        capsule = data.get("resume_capsule")
        self.assertIsNotNone(capsule)
        self.assertEqual(capsule["next_action"], "Implement prefix product array loop")
        self.assertEqual(capsule["blocker"], "Edge case with multiple zeros")
        self.assertEqual(capsule["updated_at"], "2026-11-17T10:00:00Z")

    def test_session_checkpoint_updates_capsule(self):
        sess = self.sessions.create(
            day_id="day-1",
            contract_id="contract-1",
            task="LeetCode 238"
        )
        self.assertIsNone(sess["outcome_json"])

        self.clock.advance(minutes=15)
        updated = self.sessions.checkpoint(
            sess["id"],
            next_action="Write unit test for empty array",
            blocker="None - test passing"
        )
        data = json.loads(updated["outcome_json"])
        capsule = data.get("resume_capsule")
        self.assertIsNotNone(capsule)
        self.assertEqual(capsule["next_action"], "Write unit test for empty array")
        self.assertEqual(capsule["blocker"], "None - test passing")
        self.assertEqual(capsule["updated_at"], "2026-11-17T10:15:00Z")


if __name__ == "__main__":
    unittest.main()
