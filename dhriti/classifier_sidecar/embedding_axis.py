"""Embedding axis: local semantic relatedness, on-device only.

BACKEND SLOT, lazy imports only (this package must never hard-require a
dependency -- the core stays stdlib):

1. sentence-transformers (production): all-MiniLM-L6-v2 baseline; BGE /
   Qwen3-Embedding / EmbeddingGemma 2 as benchmark candidates per
   VERSION_PINS notes. Pick via `dhriti embed-eval` on YOUR coded
   specimens, not MTEB leaderboards (see INTEGRATION.md).
2. hashing fallback (dev/test only, deterministic): char 3-gram hashing
   to 256 dims, L2-normalized. Honest label: DEV FALLBACK -- fine for
   plumbing tests, NOT for production verdicts.

Text enters here (sidecar process, loopback) and never leaves the machine.
"""

from __future__ import annotations

import math
import re
from typing import Optional

_backend = None
_backend_name = "none"


def _load_backend() -> bool:
    global _backend, _backend_name
    # 1. FastEmbed (production ONNX CPU, sub-15ms, quantized)
    try:
        from fastembed import TextEmbedding
        _backend = TextEmbedding()
        _backend_name = "fastembed:bge-small-en-v1.5"
        return True
    except Exception:
        pass

    # 2. sentence-transformers fallback
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _backend = SentenceTransformer("all-MiniLM-L6-v2")
        _backend_name = "sentence-transformers:all-MiniLM-L6-v2"
        return True
    except Exception:
        pass

    _backend = None
    _backend_name = "hashing-dev-fallback"
    return False


def backend_info() -> dict:
    if _backend is None:
        _load_backend()
    return {"backend": _backend_name, "production": _backend is not None}


def _hashing_embed(text: str, dim: int = 384) -> list[float]:
    """DEV FALLBACK ONLY. Deterministic char-3gram hashing embedding."""
    vec = [0.0] * dim
    t = re.sub(r"\s+", " ", text.lower())
    for i in range(max(0, len(t) - 2)):
        g = t[i:i + 3]
        h = 0
        for ch in g:
            h = (h * 131 + ord(ch)) % (dim * 1009)
        vec[h % dim] += 1.0
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def embed(text: str) -> Optional[list[float]]:
    if _backend is None:
        _load_backend()
    if _backend is not None:
        try:
            if "fastembed" in _backend_name:
                v = list(_backend.embed([text]))[0]
                return [float(x) for x in v]
            return [float(x) for x in
                    _backend.encode([text], normalize_embeddings=True)[0]]
        except Exception:
            pass
    return _hashing_embed(text)


def cosine(a: Optional[list[float]], b: Optional[list[float]]) -> Optional[float]:
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


def score_against_anchors(prompt: str, anchors: list[str]) -> Optional[float]:
    """Best cosine between the prompt and any anchor (contract scope line,
    thread topic, running centroid). None if the backend produced nothing
    (caller treats None as 'no signal', never as off-topic)."""
    if not anchors:
        return None
    p = embed(prompt)
    best = None
    for a in anchors:
        c = cosine(p, embed(a))
        if c is not None and (best is None or c > best):
            best = c
    return best


def running_centroid(previous_prompts: list[str]) -> Optional[str]:
    """Self-referential drift anchor (Alignment-Drift borrowing): return a
    pseudo-anchor from earlier prompts of the same pass."""
    if len(previous_prompts) < 4:
        return None
    return " ".join(previous_prompts[: len(previous_prompts) // 2])[:2000]


def running_centroid_vector(previous_prompts: list[str]) -> Optional[list[float]]:
    """Mathematical vector centroid of past prompts in the session."""
    if not previous_prompts:
        return None
    from dhriti.classifier_sidecar.springboard_math import vector_centroid
    vecs = [v for p in previous_prompts if (v := embed(p)) is not None]
    return vector_centroid(vecs)
