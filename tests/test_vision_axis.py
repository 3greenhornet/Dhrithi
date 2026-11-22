"""Tests for the Vision Axis & Safe Visual Gate (L-9r / Research Doc §26.1 & §10.3)."""

import base64
import hashlib
import io
import os
import pytest
from PIL import Image

from dhriti.classifier_sidecar.vision_axis import (
    VisionClassifier,
    classify_query_intent,
    ADULT_EXPLICIT_TOKENS,
    SAFE_STUDY_VISUAL_TOKENS
)
from dhriti.topic_gate import TopicGate
from dhriti.db import Database


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_vision.sqlite3"
    db = Database(str(db_file))
    yield db
    db.close()


@pytest.fixture
def sample_image_bytes():
    # Create a small valid 200x200 PNG in memory
    img = Image.new("RGB", (200, 200), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestVisionAxisIntent:
    def test_adult_queries_suppress_grid(self):
        adult_queries = [
            "porn video hd",
            "xxx adult movie",
            "hentai art gallery",
            "erotic art uncensored",
            "nude photos 18+",
            "onlyfans leaks"
        ]
        for q in adult_queries:
            res = classify_query_intent(q)
            assert res["is_adult"] is True, f"Failed for {q}"
            assert res["suppress_image_grid"] is True
            assert res["max_thumbnails"] == 0
            assert res["action"] == "suppress_grid"

    def test_safe_study_queries_always_allowed(self):
        study_queries = [
            "binary search tree diagram",
            "cpu pipeline architecture flowchart",
            "mitochondria biology diagram",
            "linear regression formula graph",
            "apj abdul kalam biography photo",
            "taj mahal architectural layout"
        ]
        for q in study_queries:
            res = classify_query_intent(q)
            assert res["is_adult"] is False, f"Failed for {q}"
            assert res["suppress_image_grid"] is False
            assert res["max_thumbnails"] == 16, "Anti-springboard boundary must be 16"
            assert res["action"] == "allow"

    def test_suggestive_queries_bounded_and_blurred(self):
        res = classify_query_intent("bikini swimsuit fashion")
        assert res["is_adult"] is False
        assert res["is_suggestive"] is True
        assert res["suppress_image_grid"] is False
        assert res["max_thumbnails"] == 8
        assert res["action"] == "blur_or_suppress"

    def test_suggestive_word_in_study_context_prefers_study(self):
        # E.g., human anatomy or biological context
        res = classify_query_intent("human reproductive anatomy diagram biology")
        assert res["is_adult"] is False
        assert res["action"] == "allow"
        assert res["max_thumbnails"] == 16


class TestVisionClassifierZeroRetention:
    def test_classify_image_hash_and_zero_retention(self, sample_image_bytes, tmp_path):
        os.environ["DHRITI_CI_ENVIRONMENT"] = "1"
        try:
            classifier = VisionClassifier()
            verdict = classifier.classify_image(
                sample_image_bytes,
                host="images.google.com",
                metadata={"alt": "cpu architecture diagram"}
            )
            expected_hash = hashlib.sha256(sample_image_bytes).hexdigest()
            assert verdict["sha256"] == expected_hash
            assert verdict["is_safe"] is True
            assert verdict["action"] == "allow"

            # Verify no file written to disk
            files = list(tmp_path.glob("*"))
            assert len(files) == 0, "Zero-retention rule: no image bytes may be written to disk"
        finally:
            os.environ.pop("DHRITI_CI_ENVIRONMENT", None)

    def test_allow_and_learn_safe_anchors(self, sample_image_bytes):
        classifier = VisionClassifier()
        img_hash = hashlib.sha256(sample_image_bytes).hexdigest()

        assert not classifier.is_safe_anchor(img_hash)
        classifier.learn_safe_image(img_hash, host_path="example.com/diagram.png")
        assert classifier.is_safe_anchor(img_hash)

        # Re-classification immediately returns safe
        verdict = classifier.classify_image(sample_image_bytes)
        assert verdict["is_safe"] is True
        assert verdict["action"] == "allow"
        assert verdict["reason"] == "learned_safe_anchor"


class TestTopicGateImageGating:
    def test_topic_gate_adult_query_blocked(self, temp_db):
        gate = TopicGate(temp_db)
        targets = [{"target": "Solve Two Sum in Python"}]

        resp = gate.check_query("hentai adult 18+ art", targets, is_session_active=True)
        assert resp["allowed"] is False
        assert resp["is_adult"] is True
        assert resp["suppress_image_grid"] is True
        assert resp["max_thumbnails"] == 0
        assert resp["reason"] == "adult_content_detected"

    def test_topic_gate_study_query_allowed_with_springboard_bound(self, temp_db):
        gate = TopicGate(temp_db)
        targets = [{"target": "Solve Two Sum in Python"}]

        resp = gate.check_query("binary search tree diagram", targets, is_session_active=True)
        assert resp["allowed"] is True
        assert resp["is_adult"] is False
        assert resp["suppress_image_grid"] is False
        assert resp["max_thumbnails"] == 16
        assert resp["reason"] == "sovereign_study_token"

    def test_topic_gate_general_normal_query_unblocked_when_no_targets(self, temp_db):
        gate = TopicGate(temp_db)
        resp = gate.check_query("solar system planet photos", [], is_session_active=True)
        assert resp["allowed"] is True
        assert resp["is_adult"] is False
        assert resp["suppress_image_grid"] is False
        assert resp["max_thumbnails"] == 16
