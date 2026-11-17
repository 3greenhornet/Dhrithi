"""Unit tests for recommendation engine inversion mechanics in springboard_math.py."""

import unittest
from collections import Counter
from dhriti.classifier_sidecar.springboard_math import (
    vector_centroid,
    cosine_similarity,
    calculate_drift_metrics,
    ucb_evasion_score,
    taxonomy_hop_distance,
    evaluate_springboard_breach
)


class TestSpringboardMath(unittest.TestCase):

    def test_vector_centroid_and_cosine(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        c = vector_centroid([v1, v2])
        self.assertIsNotNone(c)
        self.assertAlmostEqual(c[0], c[1], places=4)
        # Cosine similarity
        self.assertAlmostEqual(cosine_similarity(v1, v1), 1.0)
        self.assertAlmostEqual(cosine_similarity(v1, v2), 0.0)

    def test_pixie_walk_distance(self):
        anchor = [1.0, 0.0, 0.0]
        on_topic = [0.95, 0.05, 0.0]
        off_topic = [0.05, 0.95, 0.0]

        d_on = calculate_drift_metrics(on_topic, [anchor], [])
        d_off = calculate_drift_metrics(off_topic, [anchor], [])

        self.assertLess(d_on["pixie_walk_distance"], 0.1)
        self.assertGreater(d_off["pixie_walk_distance"], 0.8)

    def test_ucb_uncertainty_inversion(self):
        # A session where we've seen lots of Java tokens
        tokens = Counter({"java": 20, "array": 15, "algorithm": 10, "leetcode": 8})

        # Test prompt 1: on-topic familiar words
        score_on = ucb_evasion_score("java array algorithm leetcode", tokens, anchor_sim=0.9)
        # Test prompt 2: obscure out-of-domain words (dark matter space travel)
        score_off = ucb_evasion_score("dark energy antimatter exotic galaxy", tokens, anchor_sim=0.1)

        self.assertLess(score_on["evasion_risk"], 0.2)
        self.assertGreater(score_off["evasion_risk"], 0.6)

    def test_concept_taxonomy_hops(self):
        # Coding to coding -> 0 hops
        res1 = taxonomy_hop_distance("find the largest element in java array")
        self.assertEqual(res1["hops"], 0)

        # Coding to aptitude/placement -> 1 hop (sibling)
        res2 = taxonomy_hop_distance("quantguide probability questions for gitam placement")
        self.assertEqual(res2["hops"], 1)

        # Coding to astrophysics rabbit hole -> 2 hops (cross-category)
        res3 = taxonomy_hop_distance("is space travel possible with dark energy and antimatter")
        self.assertEqual(res3["hops"], 2)
        self.assertTrue(res3["is_cross_domain"])

        # Coding to entertainment -> 3 hops
        res4 = taxonomy_hop_distance("read latest one piece manga chapter on reddit")
        self.assertEqual(res4["hops"], 3)
        self.assertTrue(res4["is_cross_domain"])

    def test_unified_springboard_breach(self):
        tokens = Counter({"java": 10, "array": 5})
        anchor_vec = [1.0, 0.0, 0.0]

        # 1. On-topic prompt
        on_topic_vec = [0.98, 0.02, 0.0]
        res_on = evaluate_springboard_breach(
            "how to find largest subarray in java",
            on_topic_vec, [anchor_vec], [anchor_vec], tokens)
        self.assertFalse(res_on["is_leap"])
        self.assertLess(res_on["springboard_index"], 0.35)

        # 2. Rabbit hole prompt
        rabbit_vec = [0.05, 0.98, 0.0]
        res_rabbit = evaluate_springboard_breach(
            "why is antimatter costly and how is dark energy made",
            rabbit_vec, [anchor_vec], [anchor_vec], tokens)
        self.assertTrue(res_rabbit["is_leap"])
        self.assertEqual(res_rabbit["suggested_p_code"], "P-15")
        self.assertGreater(res_rabbit["springboard_index"], 0.65)


if __name__ == "__main__":
    unittest.main()

