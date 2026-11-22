"""Tests for TopicGate semantic query and prompt inspection (L-4r / L-9r)."""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhriti.db import Database
from dhriti.topic_gate import TopicGate


class TestTopicGate(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.gate = TopicGate(self.db)
        self.targets = [
            {"target": "Binary tree preorder and inorder traversal LeetCode", "kind": "code"},
            {"target": "Kunal Kushwaha Java OOPs Tutorial Lecture 4", "kind": "learning"},
            {"target": "Permutations and Combinations Quantitative Aptitude", "kind": "aptitude"}
        ]

    def tearDown(self):
        self.db.close()

    def test_sovereign_study_tokens_allowed(self):
        res = self.gate.check_query("how to reverse linked list in java", self.targets)
        self.assertTrue(res["allowed"])
        self.assertEqual(res["reason"], "sovereign_study_token")

    def test_target_overlap_allowed(self):
        res = self.gate.check_query("preorder traversal recursive solution", self.targets)
        self.assertTrue(res["allowed"])

    def test_safe_anchors_learned(self):
        self.gate.add_safe_anchor("react native architecture")
        res = self.gate.check_query("react native architecture state management", self.targets)
        self.assertTrue(res["allowed"])
        self.assertEqual(res["reason"], "learned_safe_anchor")

    def test_off_topic_drift_flagged(self):
        res = self.gate.check_query("best action movies on netflix 2026", self.targets)
        self.assertFalse(res["allowed"])
        self.assertEqual(res["reason"], "off_topic_drift")
        self.assertIn("Binary tree preorder", res["targets"][0])

    def test_empty_or_inactive_allowed(self):
        res = self.gate.check_query("", self.targets)
        self.assertTrue(res["allowed"])
        res2 = self.gate.check_query("gaming news", self.targets, is_session_active=False)
        self.assertTrue(res2["allowed"])


if __name__ == "__main__":
    unittest.main()
