"""Operator QoL toolkit tests (v0.4.0): health, backup, journal,
config. Each tool has at least one test (Phase 1 acceptance)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

from dhriti.backup import BackupService
from dhriti.health import build_health
from dhriti.journal import JournalService

from test_plumbing import DhritiTestCase


class TestBackup(DhritiTestCase):
    def test_backup_creates_manifest_and_verifies(self):
        self.ledger.record("something_happened",
                           observed_payload={"a": 1})
        service = BackupService(self.home, self.db, self.ledger,
                                self.clock)
        manifest = service.create()
        self.assertTrue(manifest["chain_verified_before"])
        self.assertTrue(manifest["chain_verified_after"])
        names = [f["name"] for f in manifest["files"]]
        self.assertIn("dhriti.sqlite3", names)
        self.assertIn("ledger_export.json", names)
        # verify() against the manifest passes
        result = service.verify(Path(manifest["dest"]))
        self.assertTrue(result["ok"], result.get("problems"))

    def test_backup_detects_tampering(self):
        service = BackupService(self.home, self.db, self.ledger,
                                self.clock)
        manifest = service.create()
        # tamper with a copied file
        target = Path(manifest["dest"]) / "ledger_export.json"
        target.write_text("tampered", encoding="utf-8")
        result = service.verify(Path(manifest["dest"]))
        self.assertFalse(result["ok"])
        self.assertTrue(any("hash mismatch" in p
                            for p in result["problems"]))


class TestJournal(DhritiTestCase):
    def test_add_list_and_ledger_fact(self):
        service = JournalService(self.home, self.clock)
        try:
            row = service.add("the mirror works. I still don't.")
            self.assertTrue(row["at_utc"])
            rows = service.list()
            self.assertEqual(len(rows), 1)
            # the ledger records the FACT only
            self.ledger.record(
                "journal_entry_added",
                observed_payload={"at": row["at_utc"]})
            events = self.ledger.events(event_type="journal_entry_added")
            self.assertEqual(len(events), 1)
            self.assertNotIn("mirror works",
                             events[0]["observed_payload"])
        finally:
            service.close()


class TestHealth(DhritiTestCase):
    def test_health_green_on_fresh_home(self):
        report = build_health(self.home, self.config, self.clock,
                              db=self.db, ledger=self.ledger)
        self.assertEqual(report.overall, "OK",
                         "\n".join(report.lines))

    def test_health_flags_broken_chain(self):
        # forge a row edit: triggers make the direct UPDATE abort, so
        # simulate damage by inserting a row with a broken prev link
        self.db.execute(
            "INSERT INTO event(seq, event_id, occurred_at_utc, "
            "monotonic_offset_ms, source_adapter, event_type, "
            "telemetry_quality, prev_hash, row_hash) "
            "VALUES(99999, 'forged', '2026-11-02T00:00:00Z', 0, 'x', "
            "'x', 'OK', 'deadbeef', 'deadbeef')")
        report = build_health(self.home, self.config, self.clock,
                              db=self.db, ledger=self.ledger)
        self.assertEqual(report.overall, "BROKEN")
        self.assertTrue(any("[FAIL] chain" in line
                            for line in report.lines))


class TestConfigCli(DhritiTestCase):
    def test_config_validate_and_get(self):
        import argparse, contextlib, io
        from dhriti import cli
        (self.home / "dhriti.config.json").write_text(
            "{}", encoding="utf-8")
        ctx = argparse.Namespace(sub="validate", home=str(self.home))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.cmd_config(ctx)
        self.assertIn("[ok  ] config valid", out.getvalue())


if __name__ == "__main__":
    unittest.main()
