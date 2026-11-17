"""Normalized event ledger with a SHA-256 hash chain (dossier 7.2).

The schema is exactly the dossier's normalized event schema — observed and
inferred data stay in separate columns, missing telemetry is recorded as
MISSING (never interpreted as inactivity), and every row chains to the
previous row's hash.
"""

import csv
import hashlib
import json
import uuid
from pathlib import Path
from typing import Optional

from .db import Database
from .errors import LedgerError
from .models import TelemetryQuality
from .timeutil import Clock, RealClock, to_iso

GENESIS = "0" * 64

# Payload fields covered by the row hash. Canonical JSON (sorted keys)
# makes the hash stable across platforms.
_PAYLOAD_FIELDS = [
    "occurred_at_utc", "monotonic_offset_ms", "session_id", "case_id",
    "source_adapter", "source_version", "event_type", "parent_event_id",
    "process_instance_id", "observed_payload", "raw_payload_reference",
    "inference_payload", "model_id_or_rule_version", "policy_version",
    "action_taken", "telemetry_quality",
]


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


class Ledger:
    """Append-only event writer + chain verifier."""

    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 anchor_interval: int = 100):
        self.db = db
        self.clock = clock or RealClock()
        self.anchor_interval = anchor_interval
        self._events_since_anchor = 0

    # -- writes ------------------------------------------------------------
    def record(
        self,
        event_type: str,
        source_adapter: str = "core",
        source_version: str = "",
        session_id: Optional[str] = None,
        case_id: Optional[str] = None,
        parent_event_id: Optional[str] = None,
        process_instance_id: Optional[str] = None,
        observed: Optional[dict] = None,
        raw_payload_reference: Optional[str] = None,
        inference_payload: Optional[dict] = None,
        model_id_or_rule_version: Optional[str] = None,
        policy_version: Optional[str] = None,
        action_taken: Optional[str] = None,
        telemetry_quality: str = TelemetryQuality.OK.value,
        occurred_at_utc: Optional[str] = None,
    ) -> str:
        """Append one normalized event; returns its event_id.

        `observed` is the observed payload (v0.5.0 name; the column is
        still observed_payload — the dossier 7.2 schema is frozen).
        """
        event_id = str(uuid.uuid4())
        occurred = occurred_at_utc or self.clock.iso()
        mono = self.clock.monotonic_ms()
        row = {
            "event_id": event_id,
            "occurred_at_utc": occurred,
            "monotonic_offset_ms": mono,
            "session_id": session_id,
            "case_id": case_id or session_id,
            "source_adapter": source_adapter,
            "source_version": source_version,
            "event_type": event_type,
            "parent_event_id": parent_event_id,
            "process_instance_id": process_instance_id,
            "observed_payload": json.dumps(
                observed or {}, default=str, separators=(",", ":")),
            "raw_payload_reference": raw_payload_reference,
            "inference_payload": json.dumps(inference_payload or {}, default=str),
            "model_id_or_rule_version": model_id_or_rule_version,
            "policy_version": policy_version,
            "action_taken": action_taken,
            "telemetry_quality": telemetry_quality,
        }
        with self.db._lock:
            head = self.db.query_one(
                "SELECT seq, row_hash FROM event ORDER BY seq DESC LIMIT 1")
            prev_hash = head["row_hash"] if head else GENESIS
            chain_payload = {k: row.get(k) for k in _PAYLOAD_FIELDS}
            row_hash = hashlib.sha256(
                (prev_hash + payload_hash(chain_payload)).encode("utf-8")
            ).hexdigest()
            self.db.insert("event", {**row, "prev_hash": prev_hash,
                                     "row_hash": row_hash})
        self._events_since_anchor += 1
        if self._events_since_anchor >= self.anchor_interval:
            self.write_anchor(note="interval")
        return event_id

    def write_anchor(self, note: str = "manual") -> dict:
        """Checkpoint the chain head so it can be copied off-machine."""
        with self.db._lock:
            head = self.db.query_one(
                "SELECT seq, row_hash FROM event ORDER BY seq DESC LIMIT 1")
            prev = self.db.query_one(
                "SELECT id FROM anchor ORDER BY at_utc DESC, id DESC LIMIT 1")
            anchor = {
                "id": str(uuid.uuid4()),
                "at_utc": self.clock.iso(),
                "head_seq": head["seq"] if head else 0,
                "head_hash": head["row_hash"] if head else GENESIS,
                "prev_anchor": prev["id"] if prev else None,
            }
            self.db.insert("anchor", anchor)
        self._events_since_anchor = 0
        return anchor

    # -- reads -------------------------------------------------------------
    def events(self, event_type: Optional[str] = None,
               session_id: Optional[str] = None,
               case_id: Optional[str] = None,
               since_utc: Optional[str] = None,
               limit: Optional[int] = None) -> list:
        sql = "SELECT * FROM event WHERE 1=1"
        params: list = []
        if event_type:
            sql += " AND event_type=?"
            params.append(event_type)
        if session_id:
            sql += " AND session_id=?"
            params.append(session_id)
        if case_id:
            sql += " AND case_id=?"
            params.append(case_id)
        if since_utc:
            sql += " AND occurred_at_utc>=?"
            params.append(since_utc)
        sql += " ORDER BY seq"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return self.db.query(sql, params)

    def head(self) -> dict:
        row = self.db.query_one(
            "SELECT seq, row_hash FROM event ORDER BY seq DESC LIMIT 1")
        return row or {"seq": 0, "row_hash": GENESIS}

    # -- verification ------------------------------------------------------
    def verify_chain(self) -> dict:
        """Recompute the chain. Returns {ok, checked, first_bad_seq, reason}."""
        with self.db._lock:
            rows = self.db.query(
                "SELECT * FROM event ORDER BY seq")
        prev = GENESIS
        for row in rows:
            if row["prev_hash"] != prev:
                return {"ok": False, "checked": row["seq"],
                        "first_bad_seq": row["seq"],
                        "reason": "prev_hash mismatch (row deleted/inserted)"}
            chain_payload = {k: row.get(k) for k in _PAYLOAD_FIELDS}
            expected = hashlib.sha256(
                (prev + payload_hash(chain_payload)).encode("utf-8")
            ).hexdigest()
            if row["row_hash"] != expected:
                return {"ok": False, "checked": row["seq"],
                        "first_bad_seq": row["seq"],
                        "reason": "row_hash mismatch (row edited after insert)"}
            prev = row["row_hash"]
        return {"ok": True, "checked": len(rows), "first_bad_seq": None,
                "reason": "chain intact"}

    # -- export ------------------------------------------------------------
    def export(self, path: str, fmt: str = "json") -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = self.events()
        if fmt == "csv":
            with out.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys())
                                        if rows else ["seq"])
                writer.writeheader()
                writer.writerows(rows)
        else:
            out.write_text(json.dumps(rows, indent=2, default=str),
                           encoding="utf-8")
        return out
