"""SQLite storage: schema, migrations, write guard.

Tamper-evidence strategy (dossier 2.7 / PDF 5.7 — tamper-evident, not
tamper-proof):

  * Triggers refuse UPDATE and DELETE on sealed contracts and on ledger
    events. Legitimate history is append-only through normal operation.
  * The ledger rows form a SHA-256 hash chain (see ledger.py), so a row
    edited after the fact (e.g. via sqlite3 CLI with triggers dropped)
    breaks verification. `dhriti verify` walks the chain.
  * Periodic anchor rows checkpoint the chain head so the owner can copy
    a single hash outside the machine (the honest limit: an owner who
    replaces the whole database cannot be detected locally).

Concurrency: one connection guarded by an RLock. The Lite tier's event
volume (a few events/second at most) makes this safe and simple.
"""

import datetime as _dt
import json
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Optional

from .constants import SCHEMA_VERSION
from .errors import LedgerError


def resolve_journal_mode(requested: str = None) -> str:
    """Plan Part 1 §4.10 / risk R-007: WAL mode produces corrupted
    databases on abnormal shutdown on NTFS, so the journal mode is
    DELETE unconditionally on Windows. Other platforms (dev/tests)
    default to WAL unless overridden. Never silently trust a stale
    WAL file: see _prepare_journal_files()."""
    if requested and requested.lower() in ("delete", "wal", "truncate",
                                            "persist", "memory", "off"):
        return requested.lower()
    return "DELETE" if sys.platform.startswith("win") else "WAL"


def _quarantine(path: Path) -> Optional[str]:
    """Rename a suspect sidecar file to *.corrupt-<ts>; return new name."""
    stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    target = Path(str(path) + f".corrupt-{stamp}")
    try:
        path.rename(target)
        return target.name
    except OSError:
        return None

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS bootcamp(
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  planned_days INTEGER NOT NULL,
  state TEXT NOT NULL,
  taper_stage INTEGER NOT NULL DEFAULT 1,
  config_json TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS contract(
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  scope_date TEXT NOT NULL,
  state TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  sealed_at TEXT,
  supersedes TEXT);

CREATE TABLE IF NOT EXISTS day(
  id TEXT PRIMARY KEY,
  date TEXT NOT NULL UNIQUE,
  bootcamp_id TEXT,
  contract_id TEXT,
  state TEXT NOT NULL,
  window_start_at TEXT,
  day_close_at TEXT,
  window_end_at TEXT,
  released_at TEXT,
  targets_json TEXT,
  targets_met INTEGER NOT NULL DEFAULT 0,
  note TEXT);

CREATE TABLE IF NOT EXISTS session(
  id TEXT PRIMARY KEY,
  day_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  state TEXT NOT NULL,
  task TEXT NOT NULL,
  evidence_spec TEXT,
  experiment_condition TEXT,
  ended_at TEXT,
  outcome_json TEXT);

CREATE TABLE IF NOT EXISTS break_glass(
  id TEXT PRIMARY KEY,
  session_id TEXT,
  day_id TEXT,
  pressed_at TEXT NOT NULL,
  confirmed_at TEXT,
  reason TEXT,
  honored_delay INTEGER NOT NULL DEFAULT 0,
  cooldown_until TEXT,
  penalty_declared TEXT);

CREATE TABLE IF NOT EXISTS evidence(
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  class TEXT NOT NULL,
  kind TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  verdict TEXT NOT NULL DEFAULT 'PENDING',
  verdict_reason TEXT,
  checked_at TEXT);

CREATE TABLE IF NOT EXISTS research_pass(
  id TEXT PRIMARY KEY,
  session_id TEXT,
  day_id TEXT,
  started_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  dependency TEXT NOT NULL,
  allowed_sources_json TEXT NOT NULL,
  return_condition TEXT NOT NULL,
  state TEXT NOT NULL,
  returned_at TEXT,
  notes TEXT);

CREATE TABLE IF NOT EXISTS event(
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT UNIQUE NOT NULL,
  occurred_at_utc TEXT NOT NULL,
  monotonic_offset_ms INTEGER,
  session_id TEXT,
  case_id TEXT,
  source_adapter TEXT NOT NULL,
  source_version TEXT,
  event_type TEXT NOT NULL,
  parent_event_id TEXT,
  process_instance_id TEXT,
  observed_payload TEXT,
  raw_payload_reference TEXT,
  inference_payload TEXT,
  model_id_or_rule_version TEXT,
  policy_version TEXT,
  action_taken TEXT,
  telemetry_quality TEXT NOT NULL DEFAULT 'OK',
  prev_hash TEXT NOT NULL,
  row_hash TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS anchor(
  id TEXT PRIMARY KEY,
  at_utc TEXT NOT NULL,
  head_seq INTEGER NOT NULL,
  head_hash TEXT NOT NULL,
  prev_anchor TEXT);

CREATE TABLE IF NOT EXISTS heartbeat(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at_utc TEXT NOT NULL,
  pid INTEGER,
  host TEXT);

CREATE TABLE IF NOT EXISTS policy_snapshot(
  id TEXT PRIMARY KEY,
  version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  policy_json TEXT NOT NULL,
  contract_id TEXT,
  day_id TEXT);

CREATE TABLE IF NOT EXISTS policy_state(
  id INTEGER PRIMARY KEY CHECK (id = 1),
  current_version INTEGER,
  updated_at TEXT);

-- Curiosity parking lot (plan Part 1 §5.9 + "under-utilized mechanisms"
-- note): the wall's mail slot. A branch is captured in one line and
-- deferred to cold state instead of being followed or silently lost.
CREATE TABLE IF NOT EXISTS parking_lot(
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  session_id TEXT,
  day_id TEXT,
  question TEXT NOT NULL,
  origin TEXT,
  disposition TEXT NOT NULL DEFAULT 'parked',  -- parked|approved|dropped|explored
  disposition_at TEXT,
  disposition_note TEXT);

-- Cold-state review answers (D-031 competence source, graduation
-- meta-metric, evidence quality, surveillance comfort, out-of-scope
-- devices). Answers are SUBMITTED evidence: honest, not verified.
CREATE TABLE IF NOT EXISTS cold_review(
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  scope TEXT NOT NULL,               -- day:<date> | week:<monday>
  question_key TEXT NOT NULL,
  answer TEXT NOT NULL,
  day_date TEXT);

-- Declared leisure (D-047): the specimen's sharpest distinction —
-- chosen rest vs. drift ("if you are truly content being an audience
-- member, then own it"). A declaration is one-way, typed and bounded
-- in length, and it is a LABEL, never a permission (it unblocks
-- nothing). The aftermath shows declared rest next to undeclared
-- consumption ("drift") and the cold review asks whether it held.
CREATE TABLE IF NOT EXISTS leisure_declaration(
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  day_date TEXT NOT NULL,
  activity TEXT NOT NULL,
  planned_minutes INTEGER NOT NULL,
  ends_at TEXT NOT NULL,
  note TEXT);
CREATE INDEX IF NOT EXISTS idx_leisure_day
  ON leisure_declaration(day_date);

-- Break-glass reasons are contract-design feedback, not just shame
-- records: recurring reasons mean the cold-state plan is missing
-- something (allowed resource, dependency, obstacle plan).
CREATE INDEX IF NOT EXISTS idx_break_glass_confirmed
  ON break_glass(confirmed_at);
CREATE INDEX IF NOT EXISTS idx_parking_lot_disposition
  ON parking_lot(disposition);
CREATE INDEX IF NOT EXISTS idx_event_type_session
  ON event(event_type, session_id);
"""

# Append-only guards. An owner can drop these with enough effort — that is
# the accepted threat model; the hash chain still catches row edits.
TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS trg_event_no_update
       BEFORE UPDATE ON event
       BEGIN SELECT RAISE(ABORT, 'ledger events are append-only'); END;""",
    """CREATE TRIGGER IF NOT EXISTS trg_event_no_delete
       BEFORE DELETE ON event
       BEGIN SELECT RAISE(ABORT, 'ledger events are append-only'); END;""",
    """CREATE TRIGGER IF NOT EXISTS trg_contract_sealed_no_update
       BEFORE UPDATE ON contract WHEN OLD.state = 'SEALED'
       BEGIN SELECT RAISE(ABORT, 'sealed contracts are immutable'); END;""",
    """CREATE TRIGGER IF NOT EXISTS trg_contract_no_delete
       BEFORE DELETE ON contract
       BEGIN SELECT RAISE(ABORT, 'contracts are never deleted'); END;""",
]


class Database:
    """Thin, honest SQLite wrapper: single connection + lock."""

    def __init__(self, path, journal_mode: Optional[str] = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.journal_mode = resolve_journal_mode(journal_mode)
        self._open_with_recovery()
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _open_with_recovery(self):
        """Open the database and switch it to the target journal mode.

        Plan §4.10 startup procedure: clean stale WAL/SHM files before
        trusting them. If the previous run died mid-WAL, SQLite normally
        recovers on open; if the WAL itself is corrupt (the documented
        NTFS failure), the open raises and the suspect sidecars are
        quarantined (*.corrupt-<ts>, never deleted) before a retry. The
        hash chain then reports any lost tail honestly via `dhriti verify`.
        """
        try:
            self.conn = sqlite3.connect(str(self.path),
                                        check_same_thread=False)
            self.conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
        except sqlite3.DatabaseError:
            try:
                self.conn.close()
            except Exception:
                pass
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(self.path) + suffix)
                if sidecar.exists():
                    _quarantine(sidecar)
            self.conn = sqlite3.connect(str(self.path),
                                        check_same_thread=False)
            self.conn.execute(f"PRAGMA journal_mode={self.journal_mode}")

    # -- lifecycle ---------------------------------------------------------
    def _init_schema(self):
        with self._lock:
            for stmt in SCHEMA.split(";"):
                if stmt.strip():
                    self.conn.execute(stmt)
            for trigger in TRIGGERS:
                self.conn.execute(trigger)
            if self.get_meta("schema_version") is None:
                self.set_meta("schema_version", str(SCHEMA_VERSION))
            self.conn.commit()

    def close(self):
        """Idempotent close: closing twice is not an error (a swapped
        Database handle in tests or a daemon shutdown after db.close
        must never crash the caller)."""
        with self._lock:
            if getattr(self, "conn", None) is None:
                return
            try:
                self.conn.commit()
                self.conn.close()
            except sqlite3.ProgrammingError:
                pass  # already closed elsewhere
            self.conn = None

    # -- helpers -----------------------------------------------------------
    def execute(self, sql: str, params=()) -> None:
        with self._lock:
            self.conn.execute(sql, params)
            self.conn.commit()

    def query(self, sql: str, params=()) -> list:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def query_one(self, sql: str, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def get_meta(self, key: str):
        row = self.query_one("SELECT value FROM meta WHERE key=?", (key,))
        return row["value"] if row else None

    def set_meta(self, key: str, value: str):
        self.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    # -- domain helpers ----------------------------------------------------
    def insert(self, table: str, row: dict) -> None:
        cols = ", ".join(row.keys())
        marks = ", ".join(["?"] * len(row))
        self.execute(f"INSERT INTO {table}({cols}) VALUES({marks})",
                     tuple(row.values()))

    def update(self, table: str, row_id: str, row: dict) -> None:
        """UPDATE by primary key column `id`. Triggers guard immutability."""
        sets = ", ".join(f"{k}=?" for k in row)
        self.execute(
            f"UPDATE {table} SET {sets} WHERE id=?",
            tuple(row.values()) + (row_id,),
        )

    def integrity_check(self) -> bool:
        with self._lock:
            result = self.conn.execute("PRAGMA integrity_check").fetchone()
            return result[0] == "ok"
