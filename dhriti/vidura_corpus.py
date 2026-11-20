"""Dhriti Vidura Corpus & Topic Tree Storage (D-096).

Maintains a dedicated separate SQLite database (`vidura.sqlite3`) for mutable
content, bookmarks, YouTube metadata, FTS5 lexical index, and hierarchical
topic nodes (rows with parent_id, NOT dynamic schema columns).
Keeps immutable dhriti.sqlite3 isolated and protected.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class ViduraCorpus:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # Safer journal mode for Windows NTFS (D-041)
        conn.execute("PRAGMA journal_mode=DELETE;")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS content_item (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,          -- 'video', 'article', 'tool', 'reference'
                    source TEXT NOT NULL,        -- 'youtube', 'chrome_bookmarks', 'manual'
                    external_id TEXT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    duration_s INTEGER DEFAULT 0,
                    saved_at TEXT NOT NULL,
                    event_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'unopened' -- 'unopened', 'in_progress', 'completed', 'archived'
                );

                CREATE TABLE IF NOT EXISTS topic_node (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    label TEXT NOT NULL,
                    depth INTEGER DEFAULT 0,
                    item_count INTEGER DEFAULT 0,
                    FOREIGN KEY(parent_id) REFERENCES topic_node(id)
                );

                CREATE TABLE IF NOT EXISTS item_topic (
                    item_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    assigned_by TEXT DEFAULT 'rule',
                    PRIMARY KEY(item_id, node_id),
                    FOREIGN KEY(item_id) REFERENCES content_item(id),
                    FOREIGN KEY(node_id) REFERENCES topic_node(id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
                    title, description, url, content=content_item, content_rowid=rowid
                );

                -- Triggers to sync FTS5 table
                CREATE TRIGGER IF NOT EXISTS content_ai AFTER INSERT ON content_item BEGIN
                    INSERT INTO content_fts(rowid, title, description, url)
                    VALUES (new.rowid, new.title, new.description, new.url);
                END;

                CREATE TRIGGER IF NOT EXISTS content_ad AFTER DELETE ON content_item BEGIN
                    INSERT INTO content_fts(content_fts, rowid, title, description, url)
                    VALUES('delete', old.rowid, old.title, old.description, old.url);
                END;

                CREATE TRIGGER IF NOT EXISTS content_au AFTER UPDATE ON content_item BEGIN
                    INSERT INTO content_fts(content_fts, rowid, title, description, url)
                    VALUES('delete', old.rowid, old.title, old.description, old.url);
                    INSERT INTO content_fts(rowid, title, description, url)
                    VALUES (new.rowid, new.title, new.description, new.url);
                END;
            """)

    def add_item(
        self,
        url: str,
        title: str,
        kind: str = "article",
        source: str = "manual",
        description: str = "",
        duration_s: int = 0,
        external_id: Optional[str] = None,
        topic_labels: Optional[List[str]] = None
    ) -> str:
        """Add or update an item in the corpus."""
        item_id = str(uuid.uuid4())
        saved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO content_item
                   (id, kind, source, external_id, url, title, description, duration_s, saved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, kind, source, external_id, url, title, description, duration_s, saved_at)
            )
            if topic_labels:
                for lbl in topic_labels:
                    node_id = self._ensure_topic(conn, lbl)
                    conn.execute(
                        "INSERT OR IGNORE INTO item_topic (item_id, node_id) VALUES (?, ?)",
                        (item_id, node_id)
                    )
                    conn.execute("UPDATE topic_node SET item_count = item_count + 1 WHERE id = ?", (node_id,))
        return item_id

    def ensure_topic(self, label: str, parent_label: Optional[str] = None) -> str:
        """Public helper to create or retrieve a hierarchical topic node."""
        with self._get_conn() as conn:
            return self._ensure_topic(conn, label, parent_label)

    def _ensure_topic(self, conn: sqlite3.Connection, label: str, parent_label: Optional[str] = None) -> str:
        cur = conn.execute("SELECT id FROM topic_node WHERE lower(label) = lower(?)", (label.strip(),))
        row = cur.fetchone()
        if row:
            return row["id"]
        parent_id = None
        depth = 0
        if parent_label:
            parent_id = self._ensure_topic(conn, parent_label)
            p_row = conn.execute("SELECT depth FROM topic_node WHERE id = ?", (parent_id,)).fetchone()
            depth = (p_row["depth"] + 1) if p_row else 1
        node_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO topic_node (id, parent_id, label, depth, item_count) VALUES (?, ?, ?, ?, 0)",
            (node_id, parent_id, label.strip(), depth)
        )
        return node_id

    def search(self, query_text: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Instant BM25 full-text search over titles, descriptions, and URLs."""
        with self._get_conn() as conn:
            # Escape FTS special chars
            clean_q = "".join(c for c in query_text if c.isalnum() or c.isspace()).strip()
            if not clean_q:
                cur = conn.execute("SELECT * FROM content_item ORDER BY saved_at DESC LIMIT ?", (limit,))
            else:
                cur = conn.execute(
                    """SELECT c.* FROM content_item c
                       JOIN content_fts f ON c.rowid = f.rowid
                       WHERE content_fts MATCH ?
                       ORDER BY bm25(content_fts) LIMIT ?""",
                    (f"{clean_q}*", limit)
                )
            return [dict(r) for r in cur.fetchall()]

    def get_topic_tree(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Roll-up query over topic hierarchy, returning top buckets with children."""
        with self._get_conn() as conn:
            roots = conn.execute(
                "SELECT * FROM topic_node WHERE parent_id IS NULL ORDER BY item_count DESC LIMIT ?",
                (limit,)
            ).fetchall()
            out = []
            for r in roots:
                children = conn.execute(
                    "SELECT * FROM topic_node WHERE parent_id = ? ORDER BY item_count DESC",
                    (r["id"],)
                ).fetchall()
                out.append({
                    "id": r["id"],
                    "label": r["label"],
                    "item_count": r["item_count"],
                    "children": [{"id": c["id"], "label": c["label"], "item_count": c["item_count"]} for c in children]
                })
            return out

    def ingest_bookmarks_json(self, json_data_or_path: Any) -> int:
        """Ingest Chrome/Edge Bookmarks JSON file directly (zero OAuth, zero API)."""
        data = None
        if isinstance(json_data_or_path, (str, Path)) and Path(str(json_data_or_path)).exists():
            with open(str(json_data_or_path), "r", encoding="utf-8") as f:
                data = json.load(f)
        elif isinstance(json_data_or_path, str):
            data = json.loads(json_data_or_path)
        elif isinstance(json_data_or_path, dict):
            data = json_data_or_path

        if not data or "roots" not in data:
            return 0

        count = 0
        items_to_insert = []

        def traverse(node, folder_path):
            nonlocal count
            if not isinstance(node, dict):
                return
            ntype = node.get("type")
            name = node.get("name", "Untitled")
            if ntype == "url":
                url = node.get("url", "")
                if url.startswith("http"):
                    # Detect tool vs reference vs article
                    kind = "tool" if any(w in name.lower() for w in ("calculator", "timer", "speech", "tool", "regex", "convert")) else "article"
                    items_to_insert.append((url, name, kind, "chrome_bookmarks", folder_path))
                    count += 1
            elif ntype == "folder" or "children" in node:
                next_path = f"{folder_path}/{name}" if folder_path else name
                for ch in node.get("children", []):
                    traverse(ch, next_path)

        for root_name in ("bookmark_bar", "other", "synced"):
            if root_name in data["roots"]:
                traverse(data["roots"][root_name], "")

        for url, name, kind, source, folder in items_to_insert:
            tags = [p for p in folder.split("/") if p and p.lower() not in ("bookmarks", "bookmark_bar")]
            self.add_item(url=url, title=name, kind=kind, source=source, topic_labels=tags)

        return count

    def stats(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total_items = conn.execute("SELECT count(*) FROM content_item").fetchone()[0]
            total_topics = conn.execute("SELECT count(*) FROM topic_node").fetchone()[0]
            kinds = {r[0]: r[1] for r in conn.execute("SELECT kind, count(*) FROM content_item GROUP BY kind").fetchall()}
            return {
                "total_items": total_items,
                "total_topics": total_topics,
                "by_kind": kinds
            }
