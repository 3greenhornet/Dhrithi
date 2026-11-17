"""Function axis: turn-type / dialogue-act classifier emitting P-codes.

D-074: springboarding is a DO-ing pattern. Embeddings measure about-ness;
this axis measures what the prompt DOES to the conversation.

Two backends behind a MODEL SLOT:
1. rules (default, deterministic, stdlib): marker phrases + structure
   heuristics -> P-13/P-14/P-15/P-03/advance. Honest heuristic: labeled as
   such everywhere; used as fallback and as the ambiguous-band prefilter.
2. model (production path per their research pile): MIDAS/TalkMoves-style
   dialogue-act model (e.g., DeBERTa fine-tune). Wire it into
   `load_model()` -- lazy import, never at module import time.

Text enters HERE (sidecar, L-9-gated) and never leaves to the network.
"""

from __future__ import annotations

import re
from typing import Optional

# --- MODEL SLOT -----------------------------------------------------------
_model = None


def load_model(model_path: str = "") -> bool:
    """Optional: plug a fine-tuned dialogue-act model here. Return True if
    a model loaded; the rules backend remains the fallback."""
    global _model
    try:  # production path, lazy import; absent install -> rules backend
        from transformers import pipeline  # type: ignore
        _model = pipeline("text-classification",
                          model=model_path or "cltl/DialogAct",
                          truncation=True)
        return True
    except Exception:
        _model = None
        return False


# --- rules backend (deterministic, documented as heuristic) ---------------

LEAP_MARKERS = (
    "what if", "by the way", "btw", "another thing", "one more thing",
    "random question", "completely unrelated", "switching topics",
    "new question", "separate question", "while we're at it",
    "also tell me", "out of curiosity",
)
META_MARKERS = (
    "this conversation", "our chat", "you just said", "earlier you said",
    "why do you think we", "let's step back", "meta question",
    "what are we even doing",
)
SCOPE_MARKERS = (
    "should we also", "want me to", "do you want me to",
    "we could also", "shall we also", "extend this to", "expand this to",
)
BRANCH_MARKERS = (
    "which reminds me", "that makes me think", "wait, isn't that",
    "hold on, what about", "does this relate to", "isn't this similar to",
)


def classify(prompt: str, thread_topic: str = "") -> dict:
    """Return {function_code, confidence, matched}. thread_topic unused by
    the rules backend; the model backend may use it as context."""
    p = prompt.lower().strip()
    if _model is not None:
        try:
            out = _model(prompt[:512])[0]
            label = str(out.get("label", "")).upper()
            score = float(out.get("score", 0.0))
            return {"function_code": map_model_label(label),
                    "confidence": score, "matched": [label],
                    "backend": "model"}
        except Exception:
            pass  # fall through to rules; sidecar must never 500 on model hiccups
    if any(m in p for m in META_MARKERS):
        return {"function_code": "P-13", "confidence": 0.7,
                "matched": [m for m in META_MARKERS if m in p],
                "backend": "rules"}
    if any(m in p for m in SCOPE_MARKERS):
        return {"function_code": "P-14", "confidence": 0.65,
                "matched": [m for m in SCOPE_MARKERS if m in p],
                "backend": "rules"}
    if any(m in p for m in LEAP_MARKERS):
        return {"function_code": "P-15", "confidence": 0.75,
                "matched": [m for m in LEAP_MARKERS if m in p],
                "backend": "rules"}
    if any(m in p for m in BRANCH_MARKERS):
        return {"function_code": "P-03", "confidence": 0.6,
                "matched": [m for m in BRANCH_MARKERS if m in p],
                "backend": "rules"}
    return {"function_code": "advance", "confidence": 0.5,
            "matched": [], "backend": "rules"}


def map_model_label(label: str) -> str:
    """Map a MIDAS/TalkMoves-ish label to our P-code vocabulary (D-074:
    hot verdicts and cold mining share one language)."""
    table = {
        "OFFER": "P-14", "INFORMATION_REQUEST": "advance",
        "WH_QUESTION": "advance", "YESNO_QUESTION": "advance",
        "METACOMMENT": "P-13", "METASTATEMENT": "P-13",
        "OPINION": "advance", "ACKNOWLEDGEMENT": "advance",
    }
    return table.get(label, "unknown")
