"""Migrations: lazy, additive, backed-up, idempotent (v0.5.0)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from dhriti.constants import SCHEMA_VERSION
from dhriti.db import Database
from dhriti.migrations import MIGRATIONS, current_version, run_migrations

from test_plumbing import DhritiTestCase


class TestMigrations(DhritiTestCase):
    def test_fresh_install_is_current(self):
        """A fresh database is stamped with SCHEMA_VERSION directly —
        migrations are only for databases created by older versions."""
        self.assertEqual(current_version(self.db), SCHEMA_VERSION)

    def test_noop_when_current(self):
        report = run_migrations(self.db, self.home, backup_runner=lambda: {
            "chain_verified_before": True, "dest": "unused"})
        self.assertEqual(report["applied"], [])

    def test_v1_database_migrates_to_current(self):
        """A v1 database (the v0.3.0 shape) migrates up through every
        version, idempotently, with a backup first."""
        # stamp as v1 and drop the v0.5.0 shapes so steps do real work
        self.db.set_meta("schema_version", "1")
        self.db.execute("DROP TABLE IF EXISTS vidura_item")
        self.db.execute("DROP TABLE IF EXISTS vidura_review")
        self.db.execute(
            "CREATE TABLE parking_lot_v1 AS "
            "SELECT id, created_at, session_id, day_id, question, "
            "source AS origin, disposition, disposed_at AS "
            "disposition_at, note AS disposition_note FROM parking_lot")
        self.db.execute("DROP TABLE parking_lot")
        self.db.execute("ALTER TABLE parking_lot_v1 RENAME TO parking_lot")

        backups = []

        def fake_backup():
            backups.append(True)
            return {"chain_verified_before": True,
                    "dest": str(self.home / "fake-backup")}

        report = run_migrations(self.db, self.home,
                                backup_runner=fake_backup)
        self.assertTrue(backups, "backup must run before migration")
        self.assertEqual(current_version(self.db), SCHEMA_VERSION)
        self.assertEqual(len(report["applied"]),
                         sum(len(steps)
                             for v, steps in MIGRATIONS.items()))
        # the renamed columns exist under their new names
        cols = {r["name"] for r in self.db.query(
            "PRAGMA table_info(parking_lot)")}
        self.assertIn("source", cols)
        self.assertIn("disposed_at", cols)
        # idempotent: a second run does nothing
        report2 = run_migrations(self.db, self.home,
                                 backup_runner=fake_backup)
        self.assertEqual(report2["applied"], [])

    def test_migration_refused_when_backup_fails(self):
        self.db.set_meta("schema_version", "1")
        self.db.execute("DROP TABLE IF EXISTS vidura_item")
        with self.assertRaises(RuntimeError) as ctx:
            run_migrations(self.db, self.home, backup_runner=lambda: {
                "chain_verified_before": False})
        self.assertIn("Fix the backup first", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
