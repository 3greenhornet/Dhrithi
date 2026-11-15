"""v0.7.0 Part 3 §3.15 + §4.20: conversation mining, --patterns mode
(turn-type distribution, transition network, top variants, user-probe
named patterns) over the P-coded Specimen 002."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))

import json
import unittest

import conversation_mining as cm

SPECIMEN = (Path(__file__).resolve().parents[1]
            / "analysis" / "specimens"
            / "specimen_002_turns.json")


class TestPatternsMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = cm.load_specimen(SPECIMEN)

    def test_eleven_turns_each_side(self):
        self.assertEqual(len(self.data["turns"]), 11)
        for turn in self.data["turns"]:
            self.assertTrue(turn["p_codes"])
            self.assertTrue(turn["ai_p_codes"])

    def test_distribution_counts_by_side(self):
        dist = cm.distribution(self.data)
        # user side: P-20 x5, P-19 x3, P-21 x3, P-22 x1
        self.assertEqual(dist["user_side"]["P-20"], 5)
        self.assertEqual(dist["user_side"]["P-19"], 3)
        self.assertEqual(dist["user_side"]["P-21"], 3)
        self.assertEqual(dist["user_side"]["P-22"], 1)
        # AI side: P-11 x10, P-12 x4 (the 'what field' asks)
        self.assertEqual(dist["ai_side"]["P-11"], 10)
        self.assertEqual(dist["ai_side"]["P-12"], 4)

    def test_transition_network_dominant_edges(self):
        net = cm.transition_network(self.data)
        # the loop: AI affordance/deflection -> user elaboration is
        # the strongest edge; every user turn hands off to the AI
        self.assertEqual(net["edges"]["P-11 -> P-20"], 5)
        self.assertEqual(net["user_to_ai_transitions"], 11)
        self.assertGreaterEqual(net["ai_to_user_transitions"], 10)

    def test_top_variant_is_the_loop(self):
        var = cm.top_variants(self.data)
        # deflection-question -> affordance -> user elaboration is a
        # top-3 modal variant (the documented completion->offer->
        # elaboration loop)
        self.assertIn("P-12 -> P-11 -> P-20",
                      var["top_variants"])
        self.assertGreaterEqual(
            var["top_variants"]["P-12 -> P-11 -> P-20"], 3)

    def test_user_probe_named_patterns(self):
        probe = cm.user_probe_named(self.data)
        counts = probe["counts"]
        self.assertEqual(counts["elaborations_past_completion"], 5)
        self.assertEqual(counts["corrections_of_framing"], 1)
        self.assertEqual(counts["show_and_tell"], 3)
        self.assertEqual(counts["conversation_for_its_own_sake"], 3)
        self.assertEqual(counts["task_anchor_drift"], 1)
        # §4.20's closing line, verbatim
        self.assertIn("You named none of these as probes in the "
                      "review.", probe["text"])

    def test_documented_counts_recompute_exactly(self):
        """The audit's summary numbers (completion signals 2, AI
        deflections 4, user elaborations 5, task-anchor drift 1)
        recompute from the coding."""
        counts = cm.documented_counts(self.data)
        self.assertEqual(counts["completion_signals"], 2)
        self.assertEqual(counts["ai_deflections"], 4)
        self.assertEqual(counts["user_elaborations"], 5)
        self.assertEqual(counts["task_anchor_drift"], 1)

    def test_build_patterns_names_both_sides(self):
        text = cm.build_patterns(self.data)
        for marker in ("Turn-type distribution",
                       "Transition network",
                       "Top variants",
                       "User-probe patterns",
                       "documented counts"):
            self.assertIn(marker, text)


class TestStageOneRules(unittest.TestCase):
    """The rule lists are structural (L-4): punctuation, phrase
    lists, token shape — never content semantics."""

    def test_completion_signal_survives_punctuation(self):
        self.assertTrue(cm._has_completion_signal(
            "good. one more - the mobile youtube feed is gone too"))

    def test_no_false_completion(self):
        self.assertFalse(cm._has_completion_signal(
            "also i typed in the custom reddit filter"))

    def test_ai_question_flagged(self):
        labels = cm.rule_labels(
            "Understood. What field are you targeting?", "AI")
        self.assertIn("P-11", labels)

    def test_ai_statement_not_flagged(self):
        labels = cm.rule_labels(
            "The hosts file is a strong move.", "AI")
        self.assertNotIn("P-11", labels)

    def test_user_show_and_tell(self):
        labels = cm.rule_labels(
            "i downloaded the sysmon config", "user")
        self.assertIn("P-19", labels)


class TestCoderIntegration(unittest.TestCase):
    """code_specimen.py emits the P-codes (specimen-002 form) and
    keeps specimen-001 output byte-identical."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        path = (Path(__file__).resolve().parents[1] / "analysis"
                / "specimens" / "code_specimen.py")
        spec = importlib.util.spec_from_file_location(
            "code_specimen", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.coder = mod
        cls.data = json.loads(SPECIMEN.read_text(encoding="utf-8"))

    def test_ai_turn_rows_are_p_coded(self):
        rows = self.coder.code_events(self.data, "SPECIMEN-002")
        ai_rows = [r for r in rows if r["event_type"] == "ai_turn"]
        self.assertEqual(len(ai_rows), 11)
        inference = json.loads(ai_rows[0]["inference_payload"])
        self.assertEqual(inference["p_codes"], ["P-11"])

    def test_user_rows_carry_p_codes(self):
        rows = self.coder.code_events(self.data, "SPECIMEN-002")
        first = rows[0]
        self.assertEqual(first["event_type"], "user_turn")
        inference = json.loads(first["inference_payload"])
        self.assertEqual(inference["p_codes"], ["P-19"])

    def test_summary_carries_the_distribution(self):
        summary = self.coder.summarize(self.data)
        self.assertEqual(summary["p_code_distribution"]["ai_side"]
                         ["P-12"], 4)
        self.assertEqual(summary["p_code_distribution"]["user_side"]
                         ["P-20"], 5)
        self.assertIn("RECONSTRUCTED", summary["provenance"])


if __name__ == "__main__":
    unittest.main()
