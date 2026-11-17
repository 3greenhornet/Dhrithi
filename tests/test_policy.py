"""Deterministic policy engine: allowlists, categories, modes, research
bounds, taper scaling. No model, no network — rules only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

import json

from dhriti.models import Action, TaperStage, WorkMode
from dhriti.profiles import DEFAULT_PROFILES

from test_plumbing import DhritiTestCase, daily_payload


class TestPolicyEngine(DhritiTestCase):
    def _policy(self, profile_name="coding", mode=WorkMode.CLOSED_WORLD,
                taper_stage=1, research=None):
        contract = {"mandatory_task": "x", "core_belief": "b",
                    "identity_statement": "i"}
        return self.policy.build_snapshot(
            DEFAULT_PROFILES[profile_name], contract, mode,
            research["sources"] if research else None,
            research["expires_at"] if research else None,
            taper_stage=taper_stage)

    def test_allowlisted_domain_allowed(self):
        pol = self._policy()
        decision = self.policy.evaluate_url(pol, "https://docs.oracle.com/"
                                                "en/java/")
        self.assertEqual(decision.action, Action.ALLOW)

    def test_subdomain_matches(self):
        pol = self._policy()
        decision = self.policy.evaluate_url(pol, "https://m.youtube.com/"
                                                "watch?v=x")
        self.assertEqual(decision.action, Action.BLOCK)
        self.assertIn("video", decision.category)

    def test_ai_chat_blocked_in_closed_world(self):
        pol = self._policy()
        for url in ("https://chatgpt.com/c/abc",
                    "https://claude.ai/chat/xyz"):
            decision = self.policy.evaluate_url(pol, url)
            self.assertEqual(decision.action, Action.BLOCK, url)

    def test_unlisted_domain_blocked_in_closed_world(self):
        pol = self._policy()
        decision = self.policy.evaluate_url(pol, "https://example.org/")
        self.assertEqual(decision.action, Action.BLOCK)
        self.assertEqual(decision.rule_id, "rule:closed-world")

    def test_unlisted_domain_allowed_in_default_mode(self):
        pol = self._policy(mode=WorkMode.BOUNDED_RESEARCH)
        decision = self.policy.evaluate_url(pol, "https://example.org/")
        self.assertEqual(decision.action, Action.ALLOW)

    def test_research_pass_sources_allowed_until_expiry(self):
        pol = self._policy(research={
            "sources": ["owasp.org"],
            "expires_at": "2026-11-02T06:00:00Z"})
        decision = self.policy.evaluate_url(
            pol, "https://owasp.org/www-community/")
        self.assertEqual(decision.action, Action.ALLOW)
        self.assertEqual(decision.rule_id, "rule:research-pass")
        # after expiry the allowance is gone
        self.clock.advance(hours=2)
        decision = self.policy.evaluate_url(
            pol, "https://owasp.org/www-community/")
        self.assertEqual(decision.action, Action.BLOCK)
        self.assertEqual(decision.rule_id, "rule:closed-world")

    def test_open_exploration_allows_everything(self):
        pol = self._policy(mode=WorkMode.OPEN_EXPLORATION)
        decision = self.policy.evaluate_url(pol, "https://youtube.com/")
        self.assertEqual(decision.action, Action.ALLOW)

    def test_taper_stage_3_downgrades_block_to_warn(self):
        pol = self._policy(taper_stage=TaperStage.CHECKPOINT)
        decision = self.policy.evaluate_url(pol, "https://youtube.com/")
        self.assertEqual(decision.action, Action.WARN)

    def test_app_allowlist(self):
        pol = self._policy()
        self.assertEqual(
            self.policy.evaluate_app(pol, "Code.exe").action, Action.ALLOW)
        self.assertEqual(
            self.policy.evaluate_app(pol, "steam.exe").action,
            Action.BLOCK)

    def test_snapshot_versions_increase_and_persist(self):
        p1 = self._policy()
        p2 = self._policy()
        self.assertEqual(p2["version"], p1["version"] + 1)
        current = self.policy.current_snapshot()
        self.assertEqual(current["version"], p2["version"])

    def test_extension_rules_hide_reasons(self):
        pol = self._policy()
        rules = self.policy.extension_rules(pol)
        self.assertIn("blocked_domains", rules)
        self.assertIn("contract_line", rules)
        self.assertNotIn("reason", json.dumps(rules),
                         "no reason strings cross the wall (Wall Principle)")


if __name__ == "__main__":
    unittest.main()
