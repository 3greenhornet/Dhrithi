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
                           observed={"a": 1})
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
                observed={"at": row["at_utc"]})
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
        ns = argparse.Namespace(sub="validate", home=str(self.home))
        ctx = self.make_cli_context()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                cli.cmd_config(ns, ctx)
        finally:
            ctx.close()
        self.assertIn("[ok  ] config valid", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class TestHealthV060(DhritiTestCase):
    """Bug A + §9.2: the bridge is probed over HTTP; config drift is
    compared against the daemon's recorded fingerprint."""

    def test_health_with_daemon_running_reports_bridge_ok(self):
        """Bug A: the old health check reported DEGRADED whenever the
        daemon lock existed but the probe was made from a CLI process.
        The new probe is an HTTP call, not an adapter method call."""
        from dhriti.daemon import Daemon
        import argparse, contextlib, io
        from dhriti.cli import cmd_health

        # start a real daemon+bridge on an ephemeral port
        self.config["bridge"]["port"] = 0
        daemon = Daemon(self.home, self.config, clock=self.clock)
        daemon.bridge.start()
        daemon._publish()  # a running daemon publishes its status
        real_port = daemon.bridge.port_bound

        # write the daemon lock so health sees daemon_running=True
        (self.home / "daemon.lock").write_text(
            str(__import__("os").getpid()))

        # health runs from a separate Context (as the CLI would)
        ctx = self.make_cli_context()
        # point the health probe at the real port
        ctx.config["bridge"]["port"] = real_port
        out = io.StringIO()
        exit_code = None
        try:
            with contextlib.redirect_stdout(out):
                try:
                    cmd_health(argparse.Namespace(), ctx)
                except SystemExit as exc:
                    exit_code = exc.code
        finally:
            ctx.close()
            daemon.bridge.stop()
            (self.home / "daemon.lock").unlink(missing_ok=True)
            daemon.db.close()

        text = out.getvalue()
        self.assertNotIn("[warn] adapter.extension_bridge", text)
        self.assertNotIn("[FAIL] adapter.extension_bridge", text)
        self.assertIn("[ok  ] adapter.extension_bridge", text)
        self.assertEqual(exit_code, 0)

    def test_health_bridge_down_with_lock_reports_warn(self):
        from dhriti.daemon import Daemon
        import argparse, contextlib, io
        from dhriti.cli import cmd_health

        self.config["bridge"]["port"] = 0
        daemon = Daemon(self.home, self.config, clock=self.clock)
        # bridge NOT started; lock present
        (self.home / "daemon.lock").write_text(
            str(__import__("os").getpid()))
        ctx = self.make_cli_context()
        ctx.config["bridge"]["port"] = daemon.bridge.port or 0
        out = io.StringIO()
        exit_code = None
        try:
            with contextlib.redirect_stdout(out):
                try:
                    cmd_health(argparse.Namespace(), ctx)
                except SystemExit as exc:
                    exit_code = exc.code
        finally:
            ctx.close()
            (self.home / "daemon.lock").unlink(missing_ok=True)
            daemon.db.close()
        self.assertIn("[warn] adapter.extension_bridge", out.getvalue())
        self.assertEqual(exit_code, 1)

    def test_config_drift_detected_from_disk(self):
        from dhriti.daemon import Daemon
        daemon = Daemon(self.home, self.config, clock=self.clock)
        daemon._tick()  # writes daemon_config_fingerprint to meta
        daemon.db.close()

        # user edits config while the daemon is "running"
        (self.home / "dhriti.config.json").write_text(
            '{"day_window": {"start": "09:00"}}', encoding="utf-8")

        # health catches the drift
        import argparse, contextlib, io
        from dhriti.cli import cmd_health
        ctx = self.make_cli_context()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                try:
                    cmd_health(argparse.Namespace(), ctx)
                except SystemExit:
                    pass
        finally:
            ctx.close()
        self.assertIn("[warn] config.drift", out.getvalue())

    def test_no_drift_when_disk_matches_daemon(self):
        import json as _json
        from dhriti.daemon import Daemon
        # the same config the daemon loads must be on disk, or the
        # comparison is meaningless
        (self.home / "dhriti.config.json").write_text(
            _json.dumps(self.config), encoding="utf-8")
        daemon = Daemon(self.home, self.config, clock=self.clock)
        daemon._tick()
        daemon.db.close()
        import argparse, contextlib, io
        from dhriti.cli import cmd_health
        ctx = self.make_cli_context()
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                try:
                    cmd_health(argparse.Namespace(), ctx)
                except SystemExit:
                    pass
        finally:
            ctx.close()
        self.assertIn("[ok  ] config.drift", out.getvalue())
