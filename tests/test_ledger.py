"""Ledger hash chain: tamper-evidence, not tamper-proof."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

import sqlite3

from test_plumbing import DhritiTestCase


class TestLedgerChain(DhritiTestCase):
    def test_chain_verifies_clean(self):
        for i in range(10):
            self.ledger.record("test_event", observed_payload={"i": i})
        result = self.ledger.verify_chain()
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 10)

    def test_row_edit_detected(self):
        for i in range(5):
            self.ledger.record("test_event", observed_payload={"i": i})
        # bypass our wrapper and the triggers via a raw connection:
        # drop trigger, tamper, restore trigger (an owner could do this)
        raw = sqlite3.connect(str(self.home / "dhriti.sqlite3"))
        raw.execute("DROP TRIGGER trg_event_no_update")
        raw.execute("UPDATE event SET observed_payload='{\"i\":999}' "
                    "WHERE seq=3")
        raw.execute("CREATE TRIGGER trg_event_no_update BEFORE UPDATE ON "
                    "event BEGIN SELECT RAISE(ABORT, 'ledger events are "
                    "append-only'); END;")
        raw.commit()
        raw.close()
        result = self.ledger.verify_chain()
        self.assertFalse(result["ok"])
        self.assertEqual(result["first_bad_seq"], 3)

    def test_row_deletion_detected(self):
        for i in range(5):
            self.ledger.record("test_event", observed_payload={"i": i})
        raw = sqlite3.connect(str(self.home / "dhriti.sqlite3"))
        raw.execute("DROP TRIGGER trg_event_no_delete")
        raw.execute("DELETE FROM event WHERE seq=2")
        raw.execute("CREATE TRIGGER trg_event_no_delete BEFORE DELETE ON "
                    "event BEGIN SELECT RAISE(ABORT, 'ledger events are "
                    "append-only'); END;")
        raw.commit()
        raw.close()
        result = self.ledger.verify_chain()
        self.assertFalse(result["ok"])

    def test_append_only_triggers_fire_through_api(self):
        self.ledger.record("test_event")
        with self.assertRaises(Exception):
            self.db.execute("UPDATE event SET event_type='pwned'")

    def test_anchors_written(self):
        for i in range(12):  # anchor_interval is 5 in the test plumbing
            self.ledger.record("test_event", observed_payload={"i": i})
        anchors = self.db.query(
            "SELECT * FROM anchor ORDER BY rowid")
        self.assertGreaterEqual(len(anchors), 2)
        # anchors fire on events 5 and 10; events 11-12 wait for the next
        self.assertEqual(anchors[-1]["head_seq"], 10)
        self.assertEqual(self.ledger.head()["seq"], 12)

    def test_export_json_and_csv(self):
        self.ledger.record("test_event", observed_payload={"a": 1})
        json_path = self.ledger.export(str(self.home / "e.json"))
        csv_path = self.ledger.export(str(self.home / "e.csv"), fmt="csv")
        self.assertTrue(json_path.exists() and csv_path.exists())
        import json
        rows = json.loads(json_path.read_text())
        self.assertEqual(len(rows), 1)

    def test_missing_telemetry_is_unknown_not_inactivity(self):
        event_id = self.ledger.record(
            "observer_gap", telemetry_quality="MISSING")
        rows = self.ledger.events("observer_gap")
        self.assertEqual(rows[0]["telemetry_quality"], "MISSING")


if __name__ == "__main__":
    unittest.main()
