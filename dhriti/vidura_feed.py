"""Dhriti Vidura Categorized Placement Feed & Target Integration (Package I & J).

Surfaces curated learning streams from the 2,925 sovereign items stored in vidura.sqlite3:
1. Core Java & Spring Ecosystem
2. Algorithms & Data Structures (DSA)
3. System Design & Backend Architecture
4. Quantitative Aptitude & Placement Drills

Allows 1-click addition into today's contract targets, establishing them as active Stage tasks.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from .constants import DB_VIDURA_PATH


FEED_CATEGORIES = [
    {
        "id": "java",
        "title": "Core Java & Spring Ecosystem",
        "keywords": ["java", "spring", "jvm", "concurrency", "multithreading", "collections", "hibernate", "oop", "maven", "stream"]
    },
    {
        "id": "dsa",
        "title": "Data Structures & Algorithms (DSA)",
        "keywords": ["leetcode", "neetcode", "algorithm", "binary search", "tree", "graph", "dynamic programming", "dp", "recursion", "array", "stack", "queue"]
    },
    {
        "id": "system_design",
        "title": "System Design & Distributed Backend",
        "keywords": ["system design", "distributed", "microservices", "redis", "kafka", "database", "sql", "nosql", "sharding", "load balancer", "api"]
    },
    {
        "id": "aptitude",
        "title": "Quantitative Aptitude & Placement Drills",
        "keywords": ["aptitude", "interview", "reasoning", "puzzle", "placement", "probability", "time and work", "speed", "quant", "oa"]
    }
]


class ViduraFeedService:
    def __init__(self, vidura_db_path: Optional[Path] = None):
        self.db_path = vidura_db_path or DB_VIDURA_PATH

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=DELETE;")
        return conn

    def get_categorized_feed(self, limit_per_category: int = 8) -> Dict[str, Any]:
        """Returns structured carousels from the Vidura corpus."""
        if not self.db_path.exists():
            return {"ok": True, "feed": [], "total_items": 0}

        with self._get_conn() as conn:
            # Check if content_item exists
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_item'")
            if not cur.fetchone():
                return {"ok": True, "feed": [], "total_items": 0}

            feed_result = []
            for cat in FEED_CATEGORIES:
                like_clauses = " OR ".join(["lower(title) LIKE ?" for _ in cat["keywords"]])
                params = [f"%{k}%" for k in cat["keywords"]]
                sql = f"""
                    SELECT id, title, url, kind, source, duration_s, saved_at
                    FROM content_item
                    WHERE {like_clauses}
                    ORDER BY rowid DESC
                    LIMIT ?
                """
                params.append(limit_per_category)
                rows = conn.execute(sql, params).fetchall()

                items = []
                for r in rows:
                    items.append({
                        "id": r["id"],
                        "title": r["title"],
                        "url": r["url"],
                        "kind": r["kind"],
                        "source": r["source"],
                        "duration_min": int(round((r["duration_s"] or 0) / 60))
                    })

                feed_result.append({
                    "id": cat["id"],
                    "title": cat["title"],
                    "item_count": len(items),
                    "items": items
                })

            cur = conn.execute("SELECT count(*) as total FROM content_item")
            total = cur.fetchone()["total"]

        return {
            "ok": True,
            "feed": feed_result,
            "total_items": total
        }

    def add_feed_item_as_target(self, db, item_id: str, scope_date: Optional[str] = None) -> Dict[str, Any]:
        """Adds a Vidura video/article into today's active contract targets and safe anchors."""
        today = scope_date or dt.date.today().isoformat()
        
        # 1. Fetch item details
        with self._get_conn() as conn:
            cur = conn.execute("SELECT id, title, url FROM content_item WHERE id=?", (item_id,))
            item = cur.fetchone()
            if not item:
                raise ValueError(f"Content item '{item_id}' not found in Vidura corpus.")
            item_title = item["title"]
            item_url = item["url"]

        # 2. Add to sealed contract targets
        row = db.query_one(
            "SELECT id, payload_json FROM contract WHERE kind='daily' AND scope_date=? AND state='SEALED'",
            (today,)
        )
        if not row:
            raise ValueError(f"No sealed contract for {today}. Seal contract before adding targets.")

        contract_id = row["id"]
        payload = json.loads(row["payload_json"])
        targets = payload.get("targets", [])

        # Check if already present
        for t in targets:
            if t.get("label") == item_title:
                return {"ok": True, "already_present": True, "title": item_title}

        new_target = {
            "id": f"vidura-{item_id[:8]}",
            "label": item_title,
            "kind": "learning",
            "url": item_url,
            "claimed": False,
            "evidence": {"class": "learning"}
        }
        targets.append(new_target)
        payload["targets"] = targets

        db.execute(
            "UPDATE contract SET payload_json=? WHERE id=?",
            (json.dumps(payload), contract_id)
        )

        # 3. Register safe anchor so searches for this topic are allowed
        try:
            from .topic_gate import TopicGate
            gate = TopicGate(db)
            gate.add_safe_anchor(item_title, source="vidura_target")
        except Exception:
            pass

        return {
            "ok": True,
            "added": True,
            "target": new_target
        }
