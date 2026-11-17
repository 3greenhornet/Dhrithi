"""Springboard Math: Inverted Recommendation Engine Mechanics (D-074).

Inverts the algorithmic funnels of YouTube, Pinterest, and Instagram to mathematically
detect, quantify, and halt curiosity rabbit holes and springboarding.

1. Pinterest Pixie Inversion (Graph Walk Distance):
   - Rather than walking L steps to discover serendipitous ideas, we measure graph /
     vector drift distance away from the session anchor centroid.
   - Walk distance D_walk = 1.0 - CosSim(prompt, Centroid(Anchors)).

2. YouTube UCB Uncertainty Scoring Inversion:
   - YouTube uses Upper Confidence Bound: Score = mu + c * sqrt(ln(N) / n_i) to force
     exploration of cold, obscure items (e.g. 17-year-old videos with 42 views).
   - Inverted for focus enforcement: when an off-anchor prompt has high vocabulary
     novelty / obscurity (n_i -> 0), the uncertainty term inflates the EVASION RISK
     rather than exploration bonus.
   - EvasionRisk = (1.0 - CosSim) * (1.0 + c * sqrt(ln(N + 2) / (n_bar + 1))).

3. MMR (Maximal Marginal Relevance) Diversity Inversion:
   - Recommendation systems use (1 - lambda) to reward diversity.
   - Dhriti inverts this: diversity away from the task anchor is heavily penalized.
     Marginal Divergence = 1.0 - max_{r in Recent} CosSim(prompt, r).
   - If a prompt has low anchor similarity AND high marginal divergence, it is
     statistically a runaway rabbit-hole leap.

4. Instagram Concept Taxonomy Tree:
   - Measures hierarchical tree distance between task domain and prompt domain.
   - Sibling / cousin hops (e.g., Java Arrays -> Dark Energy) produce hop distances >= 2.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Optional


# --- 1. Vector Operations & Centroids -----------------------------------------

def vector_centroid(vectors: list[list[float]]) -> Optional[list[float]]:
    """Calculates the normalized arithmetic mean centroid of a list of vectors."""
    if not vectors:
        return None
    dim = len(vectors[0])
    c = [0.0] * dim
    valid = 0
    for v in vectors:
        if len(v) == dim:
            valid += 1
            for i in range(dim):
                c[i] += v[i]
    if valid == 0:
        return None
    for i in range(dim):
        c[i] /= valid
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in c)) or 1.0
    return [x / norm for x in c]


def cosine_similarity(a: Optional[list[float]], b: Optional[list[float]]) -> float:
    """Computes cosine similarity in range [-1.0, 1.0], clamped to [0.0, 1.0]."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(0.0, min(1.0, dot / (na * nb)))


# --- 2. Inverted Pixie Walk & Marginal Divergence (MMR) -----------------------

def calculate_drift_metrics(prompt_vec: list[float],
                            anchor_vecs: list[list[float]],
                            recent_vecs: list[list[float]]) -> dict:
    """Computes walk distance (Pixie inversion) and marginal divergence (MMR inversion)."""
    anchor_centroid = vector_centroid(anchor_vecs)
    anchor_sim = cosine_similarity(prompt_vec, anchor_centroid) if anchor_centroid else 0.5
    pixie_walk_distance = 1.0 - anchor_sim

    # Marginal divergence against recent prompts in this thread/pass
    if recent_vecs:
        max_recent_sim = max((cosine_similarity(prompt_vec, rv) for rv in recent_vecs), default=0.0)
    else:
        max_recent_sim = anchor_sim
    mmr_marginal_divergence = 1.0 - max_recent_sim

    return {
        "anchor_similarity": round(anchor_sim, 4),
        "pixie_walk_distance": round(pixie_walk_distance, 4),
        "max_recent_similarity": round(max_recent_sim, 4),
        "mmr_marginal_divergence": round(mmr_marginal_divergence, 4),
    }


# --- 3. Inverted YouTube UCB (Curiosity / Novelty Evasion Scoring) -----------

def tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if len(w) >= 2]


def ucb_evasion_score(prompt_text: str,
                      session_tokens: Counter,
                      anchor_sim: float,
                      c: float = 1.414) -> dict:
    """Inverts YouTube UCB exploration to calculate Novelty Evasion Risk.

    YouTube UCB: Score = mu + c * sqrt(ln(N) / n_i)
    Dhriti Inversion: EvasionRisk = (1 - Sim) * (1 + c * sqrt(ln(N + 2) / (n_bar + 1)))
    """
    p_tokens = tokenize(prompt_text)
    if not p_tokens:
        return {"novelty_uncertainty": 0.0, "evasion_risk": 0.0, "rare_token_ratio": 0.0}

    total_session_tokens = sum(session_tokens.values())
    seen_counts = [session_tokens.get(t, 0) for t in p_tokens]
    avg_count = sum(seen_counts) / len(seen_counts)
    rare_tokens = sum(1 for c in seen_counts if c <= 1)
    rare_ratio = rare_tokens / len(p_tokens)

    # Uncertainty formula
    uncertainty = c * math.sqrt(math.log(max(2.0, total_session_tokens + 2)) / (avg_count + 1.0))
    uncertainty = min(3.0, max(0.0, uncertainty))

    # Evasion risk combines off-anchor distance with vocabulary novelty
    off_anchor = max(0.0, 1.0 - anchor_sim)
    evasion_risk = off_anchor * (0.5 + 0.5 * uncertainty)

    return {
        "novelty_uncertainty": round(uncertainty, 4),
        "evasion_risk": round(min(1.0, evasion_risk), 4),
        "rare_token_ratio": round(rare_ratio, 4),
    }


# --- 4. Instagram Concept Taxonomy Tree ---------------------------------------

TAXONOMY = {
    "career_prep": {
        "coding": ["java", "python", "array", "arrays", "algorithm", "algorithms",
                   "leetcode", "data structure", "tree", "graph", "hashmap", "sort",
                   "binary search", "recursion", "dynamic programming"],
        "aptitude": ["quant", "quantguide", "probability", "permutation", "algebra",
                     "puzzle", "speed", "distance", "percentage", "arithmetic", "ratio"],
        "placement": ["gitam", "placement", "interview", "resume", "cv", "linkedin",
                      "portal", "login", "application", "hiring", "mock interview"]
    },
    "scientific_curiosity": {
        "astrophysics": ["dark energy", "dark matter", "exotic matter", "antimatter",
                         "galaxy", "andromeda", "space travel", "relativity", "black hole",
                         "speed of light", "interstellar", "propulsion", "warp drive"],
        "deep_science": ["quantum mechanics", "string theory", "multiverse", "higgs",
                         "entropy", "cosmology", "neutron star", "fermi paradox"]
    },
    "entertainment": {
        "manga_anime": ["manga", "anime", "manhwa", "chapter", "scanlation", "webtoon"],
        "social": ["reddit", "pinterest", "youtube video", "stream", "meme", "twitter"],
        "media": ["movie", "tv show", "netflix", "trailer", "game", "gaming"]
    }
}


def classify_taxonomy_node(text: str) -> tuple[Optional[str], Optional[str]]:
    """Returns (category, leaf) for the text, or (None, None) if not matched."""
    t = text.lower()
    for cat, leaves in TAXONOMY.items():
        for leaf, keywords in leaves.items():
            for kw in keywords:
                if kw in t:
                    return cat, leaf
    return None, None


def taxonomy_hop_distance(prompt_text: str, anchor_cat: str = "career_prep") -> dict:
    """Calculates tree hop distance from the task category to the prompt category.

    Distance scale:
    0 = Same leaf (e.g. coding -> coding)
    1 = Sibling within category (e.g. coding -> aptitude)
    2 = Cousin across category boundaries (e.g. career_prep -> scientific_curiosity)
    3 = Distant consumer distraction (e.g. career_prep -> entertainment)
    """
    cat, leaf = classify_taxonomy_node(prompt_text)
    if not cat:
        return {"category": "unknown", "leaf": "unknown", "hops": 0, "is_cross_domain": False}

    if cat == anchor_cat:
        hops = 1 if leaf != "coding" else 0
        cross = False
    elif cat == "scientific_curiosity":
        hops = 2  # Rabbit hole hop
        cross = True
    else:  # entertainment
        hops = 3
        cross = True

    return {
        "category": cat,
        "leaf": leaf,
        "hops": hops,
        "is_cross_domain": cross
    }


# --- 5. Unified Springboard Evaluator (The 4-Stage Funnel) --------------------

def evaluate_springboard_breach(prompt_text: str,
                                prompt_vec: Optional[list[float]],
                                anchor_vecs: list[list[float]],
                                recent_vecs: list[list[float]],
                                session_tokens: Counter) -> dict:
    """Synthesizes all 4 recommendation engine inversions into a single verdict."""
    # 1. Drift & Marginal Divergence
    if prompt_vec:
        drift = calculate_drift_metrics(prompt_vec, anchor_vecs, recent_vecs)
    else:
        drift = {
            "anchor_similarity": 0.5,
            "pixie_walk_distance": 0.5,
            "max_recent_similarity": 0.5,
            "mmr_marginal_divergence": 0.5
        }

    # 2. Inverted UCB Novelty / Curiosity Score
    ucb = ucb_evasion_score(prompt_text, session_tokens, drift["anchor_similarity"])

    # 3. Instagram Taxonomy Hop Distance
    tax = taxonomy_hop_distance(prompt_text)

    # 4. Unified Springboard Index S in [0.0, 1.0]
    # S = 0.35 * WalkDist + 0.25 * MarginalDivergence + 0.20 * EvasionRisk + 0.20 * (Hops / 3.0)
    s_index = (
        0.35 * drift["pixie_walk_distance"] +
        0.25 * drift["mmr_marginal_divergence"] +
        0.20 * ucb["evasion_risk"] +
        0.20 * min(1.0, tax["hops"] / 2.0)
    )

    # 5. Dual-Anchor Margin Adjustment (Hard-Negative Defense)
    # If the text is closer to safe placement/engineering than to distraction, discount S
    margin_res = None
    if prompt_vec:
        from dhriti.classifier_sidecar import embedding_axis
        safe_v = [v for a in DEFAULT_SAFE_ANCHORS if (v := embedding_axis.embed(a)) is not None]
        block_v = [v for b in DEFAULT_BLOCK_ANCHORS if (v := embedding_axis.embed(b)) is not None]
        if safe_v and block_v:
            margin_res = calculate_dual_anchor_margin(prompt_vec, safe_v, block_v)
            if margin_res["is_safe_dominant"]:
                s_index = max(0.0, s_index - 0.30)
            elif margin_res["is_block_dominant"]:
                s_index = min(1.0, s_index + 0.20)

    s_index = round(min(1.0, max(0.0, s_index)), 4)

    # Escalation thresholds
    is_leap = False
    suggested_code = "advance"
    reason = "on-topic"

    if tax["hops"] >= 2 or s_index >= 0.65:
        is_leap = True
        suggested_code = "P-15"  # Topic Leap
        reason = f"Springboard leap detected (Index: {s_index}, Hops: {tax['hops']}, Category: {tax['category']})"
    elif s_index >= 0.45 or tax["hops"] == 1:
        if drift["mmr_marginal_divergence"] >= 0.50:
            suggested_code = "P-03"  # Curiosity-chain branching
            reason = f"Curiosity branching (Index: {s_index}, Divergence: {drift['mmr_marginal_divergence']})"

    return {
        "springboard_index": s_index,
        "is_leap": is_leap,
        "suggested_p_code": suggested_code,
        "reason": reason,
        "metrics": {
            "drift": drift,
            "ucb": ucb,
            "taxonomy": tax,
            "margin": margin_res
        }
    }


# --- 6. Dual-Anchor Margin Engine (Hard-Negative Defense) ---------------------

DEFAULT_SAFE_ANCHORS = [
    "java programming data structures algorithms array leetcode binary search",
    "quantitative aptitude math probability quantguide placement interview questions",
    "college placement portal interview resume hiring linkedin gitam portal",
    "academic research computer science software engineering technical documentation",
]

DEFAULT_BLOCK_ANCHORS = [
    "astrophysics dark energy antimatter exotic matter space travel andromeda galaxy",
    "manga anime manhwa webtoon chapter scanlation entertainment",
    "reddit pinterest youtube rabbit hole celebrity meme gaming stream",
]


def calculate_dual_anchor_margin(prompt_vec: list[float],
                                 safe_vecs: list[list[float]],
                                 block_vecs: list[list[float]]) -> dict:
    """Computes Margin = Sim(prompt, BlockCentroid) - Sim(prompt, SafeCentroid).

    - Margin > 0.15: Firmly pulling toward rabbit hole / distraction.
    - Margin <= 0.0: Firmly anchored in safe technical / placement work.
    - Resolves the false-positive dilemma for technical research papers.
    """
    safe_c = vector_centroid(safe_vecs)
    block_c = vector_centroid(block_vecs)
    sim_safe = cosine_similarity(prompt_vec, safe_c) if safe_c else 0.5
    sim_block = cosine_similarity(prompt_vec, block_c) if block_c else 0.5
    margin = sim_block - sim_safe
    return {
        "sim_safe": round(sim_safe, 4),
        "sim_block": round(sim_block, 4),
        "margin": round(margin, 4),
        "is_safe_dominant": margin <= 0.0,
        "is_block_dominant": margin > 0.15,
    }


# --- 7. Networking Token Bucket Rate Limiter ----------------------------------

class TokenBucket:
    """Deterministic Leaky/Token Bucket rate shaper (networking borrowing).
    Permits burst capacity up to `capacity` tokens, replenishing at `refill_per_s`.
    """
    def __init__(self, capacity: float = 5.0, refill_per_s: float = 0.0167):
        self.capacity = capacity
        self.refill_per_s = refill_per_s  # 1 token every 60s
        self.tokens = capacity
        self.last_ts = 0.0

    def consume(self, now: float, cost: float = 1.0) -> bool:
        if self.last_ts > 0.0:
            elapsed = max(0.0, now - self.last_ts)
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_s)
        self.last_ts = now
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    def remaining(self, now: float) -> float:
        if self.last_ts > 0.0:
            elapsed = max(0.0, now - self.last_ts)
            tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_s)
        else:
            tokens = self.tokens
        return round(tokens, 2)


