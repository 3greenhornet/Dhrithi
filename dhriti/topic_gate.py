"""Dhriti Semantic Input Gate (L-4r / L-9r).

On-device relational query and prompt inspection. Replaces blind, crude keyword
blocks with intelligent semantic relevance adjudication against today's declared targets.
Zero external transmission. Raw queries kept in ephemeral TTL store.
"""

import datetime as dt
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("dhriti.topic_gate")

# Known sovereign study keywords that always pass without gating friction
SOVEREIGN_STUDY_TOKENS = {
    "java", "python", "c++", "cpp", "javascript", "typescript", "golang", "rust",
    "dsa", "leetcode", "neetcode", "algorithm", "data", "structure", "binary", "tree",
    "graph", "dp", "dynamic", "programming", "recursion", "array", "string", "hashmap",
    "sql", "database", "query", "oops", "polymorphism", "inheritance", "interface",
    "exception", "multithreading", "concurrency", "spring", "springboot", "maven",
    "gradle", "aptitude", "quantitative", "reasoning", "verbal", "placement", "interview",
    "resume", "gitam", "tcs", "infosys", "wipro", "amazon", "google", "microsoft",
    "problem", "solution", "debug", "error", "nullpointer", "stack", "overflow"
}


class TopicGate:
    """Evaluates input queries and prompts against active contract targets."""

    def __init__(self, db, clock=None):
        self.db = db
        self.clock = clock
        self._ensure_schema()

    def _ensure_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS vec_safe_anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anchor_text TEXT UNIQUE COLLATE NOCASE,
                source TEXT,
                created_at TEXT
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS query_eval_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT,
                allowed INTEGER,
                score REAL,
                reason TEXT,
                created_at TEXT
            )
        """)

    def add_safe_anchor(self, text: str, source: str = "operator_pivot") -> bool:
        """Add an anchor to permanently learn that this topic is allowed."""
        norm = text.strip()
        if not norm:
            return False
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            self.db.execute("""
                INSERT OR IGNORE INTO vec_safe_anchors (anchor_text, source, created_at)
                VALUES (?, ?, ?)
            """, (norm, source, now_iso))
            return True
        except Exception as e:
            logger.warning("Failed to save safe anchor %r: %s", norm, e)
            return False

    def list_safe_anchors(self) -> List[str]:
        rows = self.db.query("SELECT anchor_text FROM vec_safe_anchors ORDER BY id DESC")
        return [r["anchor_text"] for r in rows]

    def check_query(self, query: str, active_targets: List[Dict], is_session_active: bool = True) -> Dict:
        """Adjudicates whether a query or prompt aligns with today's targets."""
        query_clean = query.strip()
        if not query_clean or not is_session_active:
            return {"allowed": True, "score": 1.0, "reason": "pass_inactive_or_empty", "targets": []}

        q_lower = query_clean.lower()
        q_tokens = set(re.findall(r"[a-z0-9+#]+", q_lower))

        # 1. Sovereign Study Token Match
        common_study = q_tokens.intersection(SOVEREIGN_STUDY_TOKENS)
        if len(common_study) >= 1:
            self._log_eval(query_clean, True, 0.95, "sovereign_study_token")
            return {
                "allowed": True,
                "score": 0.95,
                "reason": "sovereign_study_token",
                "matched_tokens": list(common_study),
                "targets": [t.get("target", "") for t in active_targets]
            }

        # 2. Check Saved Safe Anchors
        safe_anchors = self.list_safe_anchors()
        for anchor in safe_anchors:
            if anchor.lower() in q_lower or q_lower in anchor.lower():
                self._log_eval(query_clean, True, 0.99, "learned_safe_anchor")
                return {
                    "allowed": True,
                    "score": 0.99,
                    "reason": "learned_safe_anchor",
                    "matched_anchor": anchor,
                    "targets": [t.get("target", "") for t in active_targets]
                }

        # 3. If no active targets defined, allow by default
        if not active_targets:
            return {"allowed": True, "score": 0.8, "reason": "no_targets_declared", "targets": []}

        # 4. Target Semantic Overlap / TF-IDF Similarity
        target_texts = [t.get("target", "") for t in active_targets if t.get("target")]
        target_tokens = set()
        for t in target_texts:
            target_tokens.update(re.findall(r"[a-z0-9+#]+", t.lower()))

        # Direct token intersection with targets
        overlap = q_tokens.intersection(target_tokens)
        if overlap:
            self._log_eval(query_clean, True, 0.90, "target_token_overlap")
            return {
                "allowed": True,
                "score": 0.90,
                "reason": "target_token_overlap",
                "matched_tokens": list(overlap),
                "targets": target_texts
            }

        # Compute TF-IDF Cosine Similarity
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            corpus = [query_clean] + target_texts
            vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
            tfidf_matrix = vectorizer.fit_transform(corpus)
            sims = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
            max_sim = float(sims.max()) if len(sims) > 0 else 0.0

            if max_sim >= 0.20:
                self._log_eval(query_clean, True, max_sim, "semantic_tfidf_match")
                return {
                    "allowed": True,
                    "score": round(max_sim, 3),
                    "reason": "semantic_tfidf_match",
                    "targets": target_texts
                }
        except Exception as e:
            logger.debug("TF-IDF fallback exception: %s", e)
            max_sim = 0.0

        # Off-topic drift detected
        self._log_eval(query_clean, False, max_sim, "off_topic_drift")
        return {
            "allowed": False,
            "score": round(max_sim, 3),
            "reason": "off_topic_drift",
            "query": query_clean,
            "targets": target_texts
        }

    def _log_eval(self, query: str, allowed: bool, score: float, reason: str):
        now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            self.db.execute("""
                INSERT INTO query_eval_log (query_text, allowed, score, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (query[:200], 1 if allowed else 0, score, reason, now_iso))
        except Exception:
            pass
