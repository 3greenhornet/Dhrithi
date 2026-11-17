"""Tests for the sidecar content store + retention (D-075)."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dhriti.content_store import ContentStore  # noqa: E402


class TestContentStore(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.store = ContentStore(self.path)

    def tearDown(self):
        self.store.close()
        os.unlink(self.path)

    def test_put_get(self):
        cid = self.store.put_text("held prompt body", kind="held_prompt",
                                  thread_id="/t1", site="chatgpt")
        row = self.store.get(cid)
        self.assertEqual(row["body"], "held prompt body")
        self.assertEqual(row["kind"], "held_prompt")
        self.assertEqual(row["meta"], {})

    def test_purge_expired_only(self):
        old = datetime.now(timezone.utc) - timedelta(days=30)
        cid_old = self.store.put_text("old", kind="held_prompt", ttl_days=14)
        cid_new = self.store.put_text("new", kind="hidden_response", ttl_days=14)
        # force the old row to look expired
        self.store.conn.execute("UPDATE content SET expires_at=? WHERE id=?",
                                (old.isoformat(), cid_old))
        self.store.conn.commit()
        purged = self.store.purge_expired()
        self.assertEqual(purged, 1)
        self.assertIsNone(self.store.get(cid_old))
        self.assertIsNotNone(self.store.get(cid_new))

    def test_kv_roundtrip(self):
        self.store.kv_set("guard_state", {"mode": "checkpoint", "n": 3})
        self.assertEqual(self.store.kv_get("guard_state")["n"], 3)

    def test_stats_shape(self):
        self.store.put_text("x", kind="held_prompt")
        stats = self.store.stats()
        self.assertIn("by_kind", stats)
        self.assertEqual(stats["by_kind"].get("held_prompt"), 1)

    def test_no_hash_chain_columns(self):
        """D-075: content is architecturally outside the chain -- assert the
        schema carries no prev/hash fields at all."""
        cols = [r[1] for r in self.store.conn.execute(
            "PRAGMA table_info(content)").fetchall()]
        for forbidden in ("hash", "prev_hash", "chain"):
            self.assertNotIn(forbidden, [c.lower() for c in cols])


class TestRetentionGlue(unittest.TestCase):
    def test_cmd_retention_dry_and_execute(self):
        from dhriti.retention import cmd_retention
        import contextlib, io
        cfg = {"raw_text_days": 14}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cmd_retention(type("A", (), {"purge_raw_after": None,
                                              "execute": False})(), cfg,
                               self.store)
        self.assertEqual(rc, 0)
        self.assertIn("dry run", buf.getvalue())
        with contextlib.redirect_stdout(buf):
            cmd_retention(type("A", (), {"purge_raw_after": None,
                                         "execute": True})(), cfg, self.store)
        self.assertIn("purged", buf.getvalue())

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.store = ContentStore(self.path)

    def tearDown(self):
        self.store.close()
        os.unlink(self.path)


if __name__ == "__main__":
    unittest.main()
