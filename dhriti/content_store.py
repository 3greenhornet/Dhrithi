"""Dhriti Guard Kit -- TTL content sidecar store (D-075).

The ledger is append-only and hash-chained: raw text can NEVER live there,
because "delete raw from time to time" would break chain verification.
This store is a SEPARATE SQLite file, outside the chain, with no triggers.
The ledger records only {prompt_hash, verdict, action, latency} events;
the sidecar holds the purgeable scaffolding (hidden response bodies, parked
prompt text, guard state snapshots).

Journal mode follows the house rule R-007: DELETE on Windows, WAL elsewhere.

Integration point: instantiate in the daemon with the data dir path; the
bridge guard handlers read/write through it; `retention.py` purges.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS content (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    thread_id  TEXT,
    site       TEXT,
    kind       TEXT NOT NULL,          -- 'held_prompt' | 'hidden_response'
    body       TEXT NOT NULL,
    meta       TEXT                    -- JSON: verdict codes, latency, etc.
);
CREATE INDEX IF NOT EXISTS idx_content_expires ON content(expires_at);
CREATE INDEX IF NOT EXISTS idx_content_thread ON content(thread_id);
CREATE TABLE IF NOT EXISTS path_reputation (
    path_prefix TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    triggers    INTEGER NOT NULL DEFAULT 1,
    last_hit    TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
"""


class ContentStore:
    def __init__(self, path: str):
        self.path = path
        is_new = not os.path.exists(path)
        self.conn = sqlite3.connect(path)
        if os.name == "nt":
            self.conn.execute("PRAGMA journal_mode=DELETE;")   # R-007
        else:
            self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

        # Optional 2026 vector acceleration (sqlite-vec extension)
        self._vec_enabled = False
        try:
            import sqlite_vec
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_safe_anchors USING vec0(
                    anchor_id INTEGER PRIMARY KEY,
                    embedding float[384]
                );
            """)
            self.conn.commit()
            self._vec_enabled = True
        except Exception:
            self._vec_enabled = False

    # -- kv (guard state snapshots; rebuildable from ledger events) ------

    def kv_set(self, key: str, value) -> None:
        now = _utcnow()
        self.conn.execute(
            "INSERT INTO kv(key, value, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at",
            (key, json.dumps(value, sort_keys=True), now))
        self.conn.commit()

    def kv_get(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM kv WHERE key=?",
                                (key,)).fetchone()
        return json.loads(row[0]) if row else default

    # -- content rows (TTL) ----------------------------------------------

    def put_text(self, body: str, kind: str, thread_id: str = "",
                 site: str = "", ttl_days: float = 14.0,
                 meta: Optional[dict] = None) -> int:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=ttl_days)
        cur = self.conn.execute(
            "INSERT INTO content(created_at, expires_at, thread_id, site, "
            "kind, body, meta) VALUES(?,?,?,?,?,?,?)",
            (now.isoformat(), expires.isoformat(), thread_id, site, kind,
             body, json.dumps(meta or {}, sort_keys=True)))
        self.conn.commit()
        return int(cur.lastrowid)

    def get(self, content_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT id, created_at, expires_at, thread_id, site, kind, body,"
            " meta FROM content WHERE id=?", (content_id,)).fetchone()
        if not row:
            return None
        return {"id": row[0], "created_at": row[1], "expires_at": row[2],
                "thread_id": row[3], "site": row[4], "kind": row[5],
                "body": row[6], "meta": json.loads(row[7] or "{}")}

    def purge_expired(self, now: Optional[datetime] = None) -> int:
        """Delete expired rows. Returns count; caller emits the ledger event
        (guard_content_purged) with this count -- the FACT is chained, the
        text is not."""
        now = now or datetime.now(timezone.utc)
        cur = self.conn.execute("DELETE FROM content WHERE expires_at < ?",
                                (now.isoformat(),))
        self.conn.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    def stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT kind, COUNT(*) FROM content GROUP BY kind").fetchall()
        kv = self.conn.execute("SELECT COUNT(*) FROM kv").fetchone()
        return {"by_kind": {k: n for k, n in rows}, "kv_keys": kv[0]}

    def add_safe_anchor_vec(self, embedding: list[float]) -> bool:
        if not self._vec_enabled or len(embedding) != 384:
            return False
        try:
            import sqlite_vec
            self.conn.execute(
                "INSERT INTO vec_safe_anchors(embedding) VALUES(?)",
                (sqlite_vec.serialize_float32(embedding),)
            )
            self.conn.commit()
            return True
        except Exception:
            return False

    def nearest_safe_anchors(self, query_vec: list[float], limit: int = 3) -> list[dict]:
        if not self._vec_enabled or len(query_vec) != 384:
            return []
        try:
            import sqlite_vec
            cur = self.conn.execute("""
                SELECT anchor_id, distance
                FROM vec_safe_anchors
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
            """, (sqlite_vec.serialize_float32(query_vec), limit))
            return [{"anchor_id": r[0], "distance": float(r[1])} for r in cur.fetchall()]
        except Exception:
            return []

    def record_path_trigger(self, path_prefix: str, category: str, ttl_days: float = 7.0) -> None:
        """Section 6.2: Domain + path reputation memory."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=ttl_days)
        self.conn.execute("""
            INSERT INTO path_reputation(path_prefix, category, triggers, last_hit, expires_at)
            VALUES(?, ?, 1, ?, ?)
            ON CONFLICT(path_prefix) DO UPDATE SET
                triggers = triggers + 1,
                last_hit = excluded.last_hit,
                expires_at = excluded.expires_at
        """, (path_prefix, category, now.isoformat(), expires.isoformat()))
        self.conn.commit()

    def check_path_reputation(self, url: str) -> Optional[dict]:
        """Section 6.2: Check if a URL or path prefix has a known reputation."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute("""
            SELECT path_prefix, category, triggers
            FROM path_reputation
            WHERE expires_at > ?
            ORDER BY LENGTH(path_prefix) DESC
        """, (now,))
        for prefix, cat, trig in cur.fetchall():
            if prefix in url:
                return {"path_prefix": prefix, "category": cat, "triggers": trig}
        return None

    def close(self) -> None:
        self.conn.close()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
