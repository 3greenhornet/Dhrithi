"""Dhriti Vidura 4-Facet Taxonomy Engine (D-097).

Implements the four orthogonal closed vocabularies:
  1. facet_domain (cs, math, systems, music, fitness, career, spiritual, philosophy, art, language, science, general)
  2. facet_intent (stage, instrument, reference, audience, dead)
  3. facet_form (video, article, tool, course)
  4. facet_effort (5min, 30min, deep)

Provides deterministic classification, join-table indexing, and instrument routing
to Life Mirror (cadence practice, exempt from memory decay).
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

DOMAIN_VOCABULARY = (
    "cs", "math", "systems", "music", "fitness", "career",
    "spiritual", "philosophy", "art", "language", "science", "general"
)

INTENT_VOCABULARY = (
    "stage", "instrument", "reference", "audience", "dead"
)

FORM_VOCABULARY = (
    "video", "article", "tool", "course"
)

EFFORT_VOCABULARY = (
    "5min", "30min", "deep"
)

# Deterministic domain keyword mappings
DOMAIN_KEYWORDS = {
    "cs": [
        "python", "javascript", "typescript", "rust", "golang", "c++", "coding", "code", "programming",
        "react", "vue", "angular", "node", "django", "fastapi", "git", "github", "sql", "database",
        "frontend", "backend", "fullstack", "docker", "kubernetes", "css", "html", "web dev", "codegrid"
    ],
    "math": [
        "math", "mathematics", "calculus", "algebra", "geometry", "linear algebra", "statistics",
        "probability", "theorem", "proof", "riemann", "equation", "prime", "topology"
    ],
    "systems": [
        "kernel", "operating system", "compiler", "cpu", "memory", "cache", "distributed systems",
        "low level", "assembly", "concurrency", "networking", "protocol", "ntfs", "posix"
    ],
    "music": [
        "music", "song", "audio", "lofi", "soundtrack", "ost", "piano", "guitar", "synth",
        "composer", "goransson", "orchestra", "relaxing rhythm", "chords", "beats"
    ],
    "fitness": [
        "fitness", "workout", "gym", "exercise", "strength", "hypertrophy", "calisthenics",
        "running", "cardio", "mobility", "stretching", "posture", "diet", "nutrition"
    ],
    "spiritual": [
        "meditation", "mindfulness", "zen", "breathwork", "vipassana", "inner peace",
        "spiritual", "consciousness", "awareness", "stillness"
    ],
    "philosophy": [
        "philosophy", "stoic", "stoicism", "aurelius", "seneca", "epictetus", "nietzsche",
        "plato", "aristotle", "ethics", "reasoning", "logic", "masculine", "wisdom", "existential"
    ],
    "art": [
        "art", "painting", "drawing", "illustration", "sketch", "museum", "sculpture",
        "calligraphy", "graphic design", "typography", "canvas", "oil painting"
    ],
    "language": [
        "japanese", "spanish", "german", "french", "kanji", "grammar", "vocabulary",
        "linguistics", "language learning", "pronunciation", "speech practice"
    ],
    "science": [
        "physics", "quantum", "biology", "chemistry", "neuroscience", "astronomy", "space",
        "cosmos", "aquarium", "marine", "mbari", "evolution", "scientific"
    ],
    "career": [
        "career", "interview", "resume", "startup", "founder", "product management",
        "venture", "salary", "management", "leadership", "business"
    ]
}


class FacetEngine:
    """Manages 4-facet schema migration, classification, and queries."""

    def __init__(self, corpus):
        self.corpus = corpus
        self.ensure_facet_schema()

    def ensure_facet_schema(self):
        """Idempotently add facet tables and indexed columns to vidura.sqlite3."""
        with self.corpus._get_conn() as conn:
            # Join table for item facets
            conn.execute("""
                CREATE TABLE IF NOT EXISTS item_facet (
                    item_id TEXT NOT NULL,
                    facet_type TEXT NOT NULL,   -- 'domain', 'intent', 'form', 'effort'
                    facet_value TEXT NOT NULL,
                    assigned_by TEXT DEFAULT 'rule',
                    confidence REAL DEFAULT 1.0,
                    PRIMARY KEY(item_id, facet_type),
                    FOREIGN KEY(item_id) REFERENCES content_item(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_item_facet_type_val ON item_facet(facet_type, facet_value)")

            # Add columns directly to content_item for fast single-row scans if not present
            cur = conn.execute("PRAGMA table_info(content_item)")
            existing_cols = {row["name"] for row in cur.fetchall()}
            for col in ("facet_domain", "facet_intent", "facet_form", "facet_effort"):
                if col not in existing_cols:
                    conn.execute(f"ALTER TABLE content_item ADD COLUMN {col} TEXT")
                    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_content_{col} ON content_item({col})")

    def classify_item(self, item: Dict[str, Any]) -> Dict[str, str]:
        """Classify a single item deterministically across domain, intent, form, effort."""
        title = (item.get("title") or "").lower()
        desc = (item.get("description") or "").lower()
        url = (item.get("url") or "").lower()
        kind = (item.get("kind") or "article").lower()
        duration_s = int(item.get("duration_s") or 0)
        source = (item.get("source") or "").lower()

        full_text = f"{title} {desc} {url}"

        # 1. FORM
        if kind == "tool" or any(w in full_text for w in ("practice site", "calculator", "speedtest", "trainer", "timer")):
            form = "tool"
        elif "course" in title or "playlist" in url or "lecture" in title:
            form = "course"
        elif kind == "video" or "youtube.com" in url or "youtu.be" in url or duration_s > 0:
            form = "video"
        else:
            form = "article"

        # 2. EFFORT
        if form == "video":
            if duration_s < 360:
                effort = "5min"
            elif duration_s <= 1800:
                effort = "30min"
            else:
                effort = "deep"
        elif form == "course":
            effort = "deep"
        elif form == "tool":
            effort = "5min"
        else:
            if any(w in full_text for w in ("cheatsheet", "summary", "quick", "tips", "notes")):
                effort = "5min"
            elif any(w in full_text for w in ("paper", "book", "specification", "complete guide", "deep dive")):
                effort = "deep"
            else:
                effort = "30min"

        # 3. DOMAIN
        domain = "general"
        max_matches = 0
        for dom, keywords in DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', full_text))
            if matches > max_matches:
                max_matches = matches
                domain = dom

        # 4. INTENT (stage vs audience vs instrument vs reference)
        if form == "tool" or any(w in full_text for w in ("speech practice", "typing test", "mental math", "flashcards")):
            intent = "instrument"
        elif any(w in full_text for w in ("docs", "documentation", "api reference", "manual", "cheatsheet", "rfc", "specification")):
            intent = "reference"
        elif any(w in full_text for w in (
            "comedy", "scene", "drama", "trailer", "movie", "standup", "bloopers", "funny",
            "reaction", "skit", "highlights", "roast", "prank", "music video"
        )):
            intent = "audience"
        elif domain in ("cs", "math", "systems") and any(w in full_text for w in (
            "tutorial", "build", "project", "implement", "how to", "architecture", "solve", "guide"
        )):
            intent = "stage"
        elif domain in ("philosophy", "spiritual", "fitness") and not any(w in full_text for w in ("comedy", "drama")):
            intent = "stage"
        else:
            intent = "audience"

        return {
            "facet_domain": domain,
            "facet_intent": intent,
            "facet_form": form,
            "facet_effort": effort
        }

    def classify_all_unclassified(self, limit: int = 5000) -> Dict[str, int]:
        """Classify and index all items currently lacking facets."""
        with self.corpus._get_conn() as conn:
            cur = conn.execute(
                "SELECT * FROM content_item WHERE facet_intent IS NULL LIMIT ?",
                (limit,)
            )
            items = [dict(r) for r in cur.fetchall()]

            count = 0
            for it in items:
                facets = self.classify_item(it)
                conn.execute(
                    """UPDATE content_item SET
                       facet_domain = ?, facet_intent = ?, facet_form = ?, facet_effort = ?
                       WHERE id = ?""",
                    (facets["facet_domain"], facets["facet_intent"], facets["facet_form"], facets["facet_effort"], it["id"])
                )
                for f_type, f_val in (
                    ("domain", facets["facet_domain"]),
                    ("intent", facets["facet_intent"]),
                    ("form", facets["facet_form"]),
                    ("effort", facets["facet_effort"]),
                ):
                    conn.execute(
                        """INSERT OR REPLACE INTO item_facet
                           (item_id, facet_type, facet_value, assigned_by)
                           VALUES (?, ?, ?, 'rule')""",
                        (it["id"], f_type, f_val)
                    )
                count += 1

            return {"classified_count": count}

    def get_facet_breakdown(self) -> Dict[str, Dict[str, int]]:
        """Return counts by each facet vocabulary."""
        with self.corpus._get_conn() as conn:
            res = {}
            for col in ("facet_domain", "facet_intent", "facet_form", "facet_effort"):
                rows = conn.execute(
                    f"SELECT {col}, COUNT(*) FROM content_item WHERE {col} IS NOT NULL GROUP BY {col}"
                ).fetchall()
                res[col.replace("facet_", "")] = {r[0]: r[1] for r in rows}
            return res

    def get_instruments(self) -> List[Dict[str, Any]]:
        """Return all interactive practice tools that belong in Life Mirror (cadence practice, no decay)."""
        with self.corpus._get_conn() as conn:
            cur = conn.execute(
                """SELECT * FROM content_item
                   WHERE facet_intent = 'instrument' OR kind = 'tool'
                   ORDER BY title ASC"""
            )
            return [dict(r) for r in cur.fetchall()]
