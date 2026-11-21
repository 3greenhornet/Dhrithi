"""Dhriti Vidura Surfacing Engine & Recall-Before-Reveal Protocol (D-098).

Implements the core Vidura memory protocol:
  * One item per day: Surfaced only during the earned evening / decompression window (L-6 / L-7).
  * Aging / Stability Ranking: Oldest unopened items surface first, countering recency bias.
  * Recall-Before-Reveal: Prompts the operator to recall why they saved the item before
    unlocking the URL, preventing mindless backlog accumulation.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .constants import DB_VIDURA_PATH
from .timeutil import Clock, RealClock, parse_iso, to_iso


class ViduraSurfaceService:
    def __init__(self, corpus, clock: Optional[Clock] = None):
        self.corpus = corpus
        self.clock = clock or RealClock()
        self._ensure_surfacing_schema()

    def _ensure_surfacing_schema(self):
        """Ensure columns for surfacing tracking exist in vidura.sqlite3."""
        with self.corpus._get_conn() as conn:
            cur = conn.execute("PRAGMA table_info(content_item)")
            cols = {row["name"] for row in cur.fetchall()}
            if "last_surfaced_at" not in cols:
                conn.execute("ALTER TABLE content_item ADD COLUMN last_surfaced_at TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_content_last_surfaced ON content_item(last_surfaced_at)")
            if "recall_history" not in cols:
                conn.execute("ALTER TABLE content_item ADD COLUMN recall_history TEXT DEFAULT '[]'")

            # Table for surfacing audit ledger within Vidura
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vidura_surfacing_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    surfaced_at TEXT NOT NULL,
                    recalled INTEGER DEFAULT 0,
                    penalized INTEGER DEFAULT 0,
                    recall_text TEXT,
                    FOREIGN KEY(item_id) REFERENCES content_item(id)
                )
            """)

    def has_surfaced_today(self) -> bool:
        """Check if an item has already been surfaced today."""
        today_prefix = self.clock.now_utc().strftime("%Y-%m-%d")
        with self.corpus._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM vidura_surfacing_event WHERE surfaced_at LIKE ? LIMIT 1",
                (f"{today_prefix}%",)
            ).fetchone()
            return row is not None

    def suggest_daily_item(
        self,
        domain: Optional[str] = None,
        effort: Optional[str] = None,
        max_duration_s: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Rank and return the top decay candidate for evening recall."""
        with self.corpus._get_conn() as conn:
            query = """
                SELECT * FROM content_item
                WHERE (facet_intent IN ('stage', 'audience') OR facet_intent IS NULL)
                  AND (status = 'unopened' OR status IS NULL)
                  AND (last_surfaced_at IS NULL OR date(last_surfaced_at) < date('now', 'localtime'))
            """
            params: List[Any] = []

            if domain:
                query += " AND facet_domain = ?"
                params.append(domain)
            if effort:
                query += " AND facet_effort = ?"
                params.append(effort)
            if max_duration_s is not None:
                query += " AND duration_s <= ?"
                params.append(max_duration_s)

            # Oldest saved first (anti-recency ranking)
            query += " ORDER BY saved_at ASC LIMIT 1"

            row = conn.execute(query, params).fetchone()
            if not row:
                # Fallback: any item not surfaced today
                row = conn.execute(
                    "SELECT * FROM content_item ORDER BY saved_at ASC LIMIT 1"
                ).fetchone()

            if not row:
                return None

            return dict(row)

    def prepare_recall_card(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the masked recall-before-reveal card."""
        saved_iso = item.get("saved_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            saved_dt = parse_iso(saved_iso)
            days_ago = max(0, (self.clock.now_utc() - saved_dt).days)
        except Exception:
            days_ago = 1

        return {
            "item_id": item["id"],
            "title": item["title"],
            "domain": item.get("facet_domain") or "general",
            "effort": item.get("facet_effort") or "30min",
            "form": item.get("facet_form") or "video",
            "duration_s": item.get("duration_s") or 0,
            "days_ago": days_ago,
            "prompt": f"You saved this {days_ago} days ago. Before revealing the link, what was your intention or context?",
            "revealed": False
        }

    def submit_recall_response(self, item_id: str, answer_text: str) -> Dict[str, Any]:
        """Process operator's recall response and unlock the revealed URL."""
        cleaned = (answer_text or "").strip()
        is_skip = cleaned.lower() in ("skip", "")
        is_forgot = cleaned.lower() in ("i don't remember", "i dont remember", "forgot", "no idea")

        recalled = not is_skip and not is_forgot
        penalized = is_forgot

        now_iso = to_iso(self.clock.now_utc())

        with self.corpus._get_conn() as conn:
            # Fetch item
            cur = conn.execute("SELECT * FROM content_item WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Item not found: {item_id}")
            item = dict(row)

            # Record event
            conn.execute(
                """INSERT INTO vidura_surfacing_event
                   (item_id, surfaced_at, recalled, penalized, recall_text)
                   VALUES (?, ?, ?, ?, ?)""",
                (item_id, now_iso, 1 if recalled else 0, 1 if penalized else 0, cleaned[:500])
            )

            # Update item status
            conn.execute(
                """UPDATE content_item SET
                   last_surfaced_at = ?,
                   event_count = event_count + 1
                   WHERE id = ?""",
                (now_iso, item_id)
            )

            return {
                "revealed": True,
                "recalled": recalled,
                "penalized": penalized,
                "item_id": item_id,
                "title": item["title"],
                "url": item["url"],
                "description": item.get("description") or "",
                "duration_s": item.get("duration_s") or 0,
                "source": item.get("source") or "",
                "facet_domain": item.get("facet_domain") or "general"
            }
