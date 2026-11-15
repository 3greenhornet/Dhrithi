"""The rule-based classifier (Part 3 §3.1 / PDF Part 2 §8.3): keyword
matching over title + description, deterministic, no model, no
network. Confidence is the matched-keyword density — an honest number
for a rule, not a dressed-up guess.

The ML service (config mirror.ml_service) can upgrade the verdict
later; when it is unreachable or disabled, this classifier IS the
verdict and the categorized event says so.
"""

from .categories import CATEGORIES

CLASSIFIER_VERSION = "rules-v1"


def classify(title: str, description: str = "") -> dict:
    """Return {category, confidence, matched, classifier,
    classifier_version}. category='unknown' when nothing matches."""
    text = f"{title or ''} {description or ''}".lower()
    if not text.strip():
        return {"category": "unknown", "confidence": 0.0,
                "matched": [], "classifier": "rule",
                "classifier_version": CLASSIFIER_VERSION}
    best, best_hits = "unknown", []
    for category, keywords in CATEGORIES:
        if category == "unknown":
            continue
        hits = [kw for kw in keywords if kw in text]
        if len(hits) > len(best_hits):
            best, best_hits = category, hits
    if not best_hits:
        return {"category": "unknown", "confidence": 0.0,
                "matched": [], "classifier": "rule",
                "classifier_version": CLASSIFIER_VERSION}
    # confidence: matched keyword count against a soft ceiling —
    # 1 hit ≈ 0.4, 2 ≈ 0.6, 3+ ≈ 0.75..0.9. A rule never claims 1.0.
    confidence = min(0.9, 0.2 + 0.2 * len(best_hits))
    return {"category": best, "confidence": round(confidence, 2),
            "matched": best_hits[:5], "classifier": "rule",
            "classifier_version": CLASSIFIER_VERSION}
