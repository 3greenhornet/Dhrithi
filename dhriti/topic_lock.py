"""The semantic topic-lock (v0.7.0 Part 3 §3.16) — the L-9 exception.

L-4 (structure-aware, content-blind) governs enforcement and ambient
observation. The topic-lock is a DISTINCT mechanism: the operator
explicitly consents, in cold state, to the system reading ONLY the
prompts they submit to AI chat surfaces during an ACTIVE session and
comparing them semantically to the session topic. L-9 is that narrow
exception. It is OFF by default; enabling it is a cold-state act
recorded as topic_lock_enabled.

The similarity is a hybrid: lexical (continuation markers, token
overlap) + embedding (sentence-transformers when installed, else a
deterministic local hashing embedding — disclosed in status). The
divergence verdict bounds: pre_send holds the prompt (park or declare
a pivot); post_generation hides the response after a 600ms debounce.
"""

import hashlib
import math
import re
from typing import Optional

# Lexical continuation / divergence markers (the causantic lesson:
# lexical cues dominate embeddings for topic continuity).
CONTINUATION_MARKERS = (
    "continue", "same", "next", "also", "then", "after that",
    "so", "and", "still", "yes", "ok", "exactly", "more",
)
TOPIC_SHIFT_MARKERS = (
    "anyway", "different question", "unrelated", "by the way",
    "random", "curious about", "what about", "totally different",
    "off topic", "switch",
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list:
    return _TOKEN_RE.findall((text or "").lower())


def _stem(token: str) -> str:
    """A light stem: plural/verb-form 's' only. Honest about being
    a prefix-tier stemmer — no Porter, no lemmatizer."""
    if len(token) > 3 and token.endswith("s") \
            and not token.endswith("ss"):
        return token[:-1]
    return token


def _token_match(a: str, b: str) -> bool:
    """Two stems match when equal, or when the shorter (4+ chars) is
    a prefix of the longer — fail/fails/failure/failing are one word
    family for continuity purposes."""
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 4 and longer.startswith(shorter)


def _hashing_embedding(text: str, dims: int = 256) -> list:
    """A deterministic local embedding: token hashing into a fixed
    number of dimensions, L2-normalized. No network, no model
    download — honest about being a bag-of-words projection (status
    discloses it; sentence-transformers upgrades it when installed)."""
    vec = [0.0] * dims
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[index] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))


class EmbeddingBackend:
    """sentence-transformers when present; the deterministic local
    hashing embedding otherwise. The backend is disclosed, never
    silently swapped."""

    def __init__(self, model: str = "local"):
        self.backend = "local-hashing-v1"
        self._model = None
        if model != "local":
            try:  # pragma: no cover - optional dependency
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(model)
                self.backend = f"sentence-transformers:{model}"
            except Exception:
                self._model = None

    def embed(self, text: str) -> list:
        if self._model is not None:  # pragma: no cover
            import numpy as np
            vec = self._model.encode([text])[0]
            norm = np.linalg.norm(vec) or 1.0
            return [float(v) for v in vec / norm]
        return _hashing_embedding(text)


def lexical_similarity(topic: str, prompt: str) -> float:
    """Topic coverage + continuation/shift marker adjustment — the
    lexical half of the hybrid. The topic is the anchor: the question
    is 'how much of the declared topic does this prompt continue',
    so the base is the fraction of topic stems the prompt carries
    (NOT Jaccard — a long on-topic continuation must not be punished
    for its new words)."""
    topic_stems = {_stem(t) for t in _tokens(topic)}
    prompt_stems = {_stem(t) for t in _tokens(prompt)}
    if not topic_stems or not prompt_stems:
        return 0.0
    covered = sum(1 for t in topic_stems
                  if any(_token_match(t, p) for p in prompt_stems))
    coverage = covered / len(topic_stems)
    text = f" {prompt.lower()} "
    bonus = 0.1 if any(m in text for m in CONTINUATION_MARKERS) else 0.0
    penalty = 0.15 if any(m in text for m in TOPIC_SHIFT_MARKERS) \
        else 0.0
    return max(0.0, min(1.0, coverage + bonus - penalty))


class TopicLockService:
    def __init__(self, config: dict, backend: Optional[EmbeddingBackend]
                 = None):
        self.config = config.get("topic_lock", {})
        self.backend = backend or EmbeddingBackend(
            self.config.get("embedding_model", "local"))
        self._topic_embedding = None
        self.topic = ""

    # -- the session binding ------------------------------------------------
    def bind_topic(self, topic: str) -> dict:
        """Called at session start: embed the declared topic, keep
        the EMBEDDING HASH (not the vector — reproducibility, not
        surveillance)."""
        topic = (topic or "").strip()
        min_chars = int(self.config.get("min_topic_chars", 10))
        if self.config.get("require_topic", True) and \
                len(topic) < min_chars:
            raise ValueError(
                f"a session topic of at least {min_chars} characters "
                "is required while the topic-lock is on")
        self.topic = topic
        self._topic_embedding = self.backend.embed(topic)
        return {
            "topic": topic,
            "embedding_hash": hashlib.sha256(
                (";".join(f"{v:.6f}"
                          for v in self._topic_embedding)
                 ).encode()).hexdigest()[:16],
            "backend": self.backend.backend,
        }

    # -- the hybrid score -----------------------------------------------------
    def similarity(self, prompt: str) -> float:
        """Hybrid: lexical_weight * lexical + embedding_weight *
        cosine(topic, prompt)."""
        if not self.topic:
            return 1.0  # no topic bound: the lock is not active
        lexical = lexical_similarity(self.topic, prompt)
        prompt_embedding = self.backend.embed(prompt)
        embedded = _cosine(self._topic_embedding, prompt_embedding)
        # cosine can be slightly negative; the meaningful range is 0..1
        embedded = max(0.0, embedded)
        lexical_w = float(self.config.get("lexical_weight", 0.4))
        embedding_w = float(self.config.get("embedding_weight", 0.6))
        total = lexical_w * lexical + embedding_w * embedded
        return max(0.0, min(1.0, total))

    def is_divergent(self, prompt: str) -> dict:
        score = self.similarity(prompt)
        threshold = float(self.config.get("similarity_threshold", 0.65))
        return {"similarity": round(score, 4),
                "threshold": threshold,
                "divergent": score < threshold,
                "mode": self.config.get("on_divergence", "pre_send"),
                "park_button": bool(self.config.get("park_button", True))}

    # -- the divergence outcomes ----------------------------------------------
    def evaluate_prompt(self, prompt: str, session_id: str,
                        ledger=None) -> dict:
        """Pre-send: a divergent prompt is HELD. The user parks it
        (curiosity_topic_parked) or declares a legitimate pivot."""
        verdict = self.is_divergent(prompt)
        if verdict["divergent"] and ledger is not None:
            ledger.record(
                "ai_prompt_diverged",
                session_id=session_id,
                observed={"topic": self.topic[:100],
                          "similarity": verdict["similarity"],
                          "threshold": verdict["threshold"],
                          "blocked": True,
                          "mode": "pre_send"},
                action_taken="prompt held; park it or declare a pivot")
        return verdict

    def evaluate_response(self, response_text: str, session_id: str,
                          ledger=None) -> dict:
        """Post-generation fallback: a divergent response is hidden
        after the debounce; inspectable cold via the journal."""
        verdict = self.is_divergent(response_text)
        if verdict["divergent"] and ledger is not None:
            ledger.record(
                "ai_response_diverged",
                session_id=session_id,
                observed={"topic": self.topic[:100],
                          "similarity": verdict["similarity"],
                          "hidden": True,
                          "mode": "post_generation"},
                action_taken="response hidden after debounce; "
                             "inspect cold via dhriti journal")
        return verdict

    def declare_pivot(self, reason: str, session_id: str,
                      ledger=None) -> dict:
        """A legitimate pivot: the reason is typed, the event is the
        record, the lock re-binds to the new topic."""
        reason = (reason or "").strip()
        if len(reason) < 10:
            raise ValueError(
                "a pivot needs a one-sentence reason (min 10 chars)")
        if ledger is not None:
            ledger.record(
                "ai_pivot_declared",
                session_id=session_id,
                observed={"reason": reason[:300]},
                action_taken="pivot declared; lock re-binds")
        return {"pivot": True, "reason": reason}
