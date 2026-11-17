"""Sidecar verdict schema -- escalate-not-decide (the D-014-compatible shape).

The sidecar NEVER says "block". It says one of:
    {"escalate": None}                      -- no concern
    {"escalate": "park"}                    -- park this prompt (no send)
    {"escalate": "collapse"}                -- send but collapse-seal response

The deterministic core caps the escalation at the mode floor. Confidence
below threshold or malformed payloads are treated as no-escalation
(fail-safe toward the structural rules, not toward blocking).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


ALLOWED_ESCALATIONS = (None, "park", "collapse")

# P-codes the function axis may emit (reference vocabulary D-043 / live D-074)
FUNCTION_CODES = ("P-13", "P-14", "P-15",   # Mirror of Meta / Scope Invitation / Topic Leap
                  "P-03",                    # Curiosity-chain branching
                  "advance", "unknown")


@dataclass
class Verdict:
    topic_score: Optional[float] = None     # cosine vs topic anchor, 0..1
    function_code: str = "unknown"
    confidence: float = 0.0
    escalate: Optional[str] = None
    reason: str = ""
    model_info: dict = field(default_factory=dict)

    def validate(self) -> "Verdict":
        if self.escalate not in ALLOWED_ESCALATIONS:
            self.escalate = None            # fail-safe: unknown -> nothing
        if self.function_code not in FUNCTION_CODES:
            self.function_code = "unknown"
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if self.topic_score is not None:
            self.topic_score = max(0.0, min(1.0, float(self.topic_score)))
        return self

    def to_dict(self) -> dict:
        return {"topic_score": self.topic_score,
                "function_code": self.function_code,
                "confidence": self.confidence,
                "escalate": self.escalate,
                "reason": self.reason,
                "model_info": self.model_info}


# Thresholds: LOW/HIGH band. Between them = ambiguous band -> only band
# that needs the slow path (the D-014-compatible cascade).
def fuse(topic_score: Optional[float], function_code: str,
         confidence: float, low: float = 0.40, high: float = 0.70,
         leap_codes: tuple = ("P-15", "P-03"),
         springboard_report: Optional[dict] = None) -> Verdict:
    """Deterministic fusion of semantic, dialogue-act, and recommendation-inversion axes.
    Implements Section 7.5 Multi-Signal Quorum:
    - 2+ independent signals agree -> Hard escalation (Park).
    - 1 signal only -> Soft Hold (Reviewable, with 'Allow & Learn' option).
    - 0 signals -> Advance on-topic.
    """
    info = {}
    signals = []

    if springboard_report:
        info["springboard"] = springboard_report
        metrics = springboard_report.get("metrics", {})
        tax = metrics.get("taxonomy", {})
        ucb = metrics.get("ucb", {})
        margin = metrics.get("margin", {})

        if tax.get("hops", 0) >= 2:
            signals.append("taxonomy_cross_category")
        if ucb.get("evasion_risk", 0.0) >= 0.55:
            signals.append("ucb_novelty_uncertainty")
        if margin and margin.get("is_block_dominant"):
            signals.append("dual_anchor_block_margin")
        if springboard_report.get("is_leap"):
            signals.append("springboard_index_breach")

    if function_code in leap_codes and confidence >= 0.6:
        signals.append(f"dialogue_act_{function_code}")
    if topic_score is not None and topic_score <= low:
        signals.append("low_topic_cosine")

    info["signal_count"] = len(signals)
    info["signals_triggered"] = signals

    # 1. Clear on-topic and zero signals
    if topic_score is not None and topic_score >= high and len(signals) == 0:
        return Verdict(topic_score, function_code, confidence, None,
                       "on-topic and advancing", model_info=info).validate()

    # 2. Hard Escalation: 2-of-3 Multi-Signal Quorum
    if len(signals) >= 2 or (springboard_report and springboard_report.get("is_leap")):
        code = springboard_report.get("suggested_p_code", "P-15") if springboard_report else function_code
        conf = max(confidence, float(springboard_report.get("springboard_index", 0.85))) if springboard_report else confidence
        return Verdict(
            topic_score=topic_score,
            function_code=code,
            confidence=conf,
            escalate="park",
            reason=f"Quorum breach ({len(signals)} signals: {', '.join(signals[:3])})",
            model_info=info
        ).validate()

    # 3. Soft Hold: Exactly 1 signal fired (Section 7.5 Soft Hold)
    if len(signals) == 1 or (topic_score is not None and topic_score < high):
        return Verdict(
            topic_score=topic_score,
            function_code=function_code if function_code != "unknown" else "P-03",
            confidence=max(confidence, 0.6),
            escalate="collapse",
            reason=f"Soft hold ({signals[0] if signals else 'ambiguous band'})",
            model_info=info
        ).validate()

    return Verdict(topic_score, function_code, confidence, None,
                   "no signal", model_info=info).validate()
