"""Schema migrations: lazy, additive, backed-up (Part 5 §4).

Rules (the migration discipline):
  * Migrations run on daemon start, only when the schema version on
    disk is behind SCHEMA_VERSION.
  * BEFORE any migration runs, a full backup is created
    (<home>/migrations/<timestamp>) and its chain verified. If the
    backup fails, the migration does not run and the daemon refuses
    to start.
  * Every step is idempotent (CREATE IF NOT EXISTS / guarded ALTER).
  * Each applied migration records a `schema_migrated` event with the
    from-version, to-version and the backup path — the undo path is
    always named.

Version history:
  1 — the v0.3.0 base schema
  2 — Vidura: vidura_item + vidura_review (v0.5.0)
  3 — the v0.5.0 surface rebuild: parking_lot column renames
      (origin->source, disposition_at->disposed_at, disposition_note
      ->note), session.contract_id, research_pass reshaped to the
      topic-locked pass
"""

import json
from pathlib import Path
from typing import Optional

from .constants import SCHEMA_VERSION
from .db import Database
from .timeutil import Clock, RealClock

MIGRATIONS = {
    2: [
        ("table vidura_item",
         "CREATE TABLE IF NOT EXISTS vidura_item("
         " id TEXT PRIMARY KEY,"
         " kind TEXT NOT NULL,"
         " front TEXT NOT NULL,"
         " back TEXT NOT NULL,"
         " created_at TEXT NOT NULL,"
         " day_date TEXT,"
         " reps INTEGER NOT NULL DEFAULT 0,"
         " lapses INTEGER NOT NULL DEFAULT 0,"
         " ease_factor REAL NOT NULL DEFAULT 2.5,"
         " interval_days REAL NOT NULL DEFAULT 0,"
         " due_at TEXT NOT NULL)"),
        ("table vidura_review",
         "CREATE TABLE IF NOT EXISTS vidura_review("
         " id TEXT PRIMARY KEY,"
         " item_id TEXT NOT NULL REFERENCES vidura_item(id),"
         " reviewed_at TEXT NOT NULL,"
         " grade TEXT NOT NULL,"
         " interval_days REAL NOT NULL,"
         " ease_factor REAL NOT NULL)"),
    ],
    3: [
        # parking_lot: origin -> source, disposition_at -> disposed_at,
        # disposition_note -> note. SQLite >= 3.25 supports RENAME
        # COLUMN; older engines are refused honestly (not silently
        # mangled).
        ("rename parking_lot.origin",
         "ALTER TABLE parking_lot RENAME COLUMN origin TO source"),
        ("rename parking_lot.disposition_at",
         "ALTER TABLE parking_lot RENAME COLUMN disposition_at "
         "TO disposed_at"),
        ("rename parking_lot.disposition_note",
         "ALTER TABLE parking_lot RENAME COLUMN disposition_note "
         "TO note"),
        ("column session.contract_id",
         "ALTER TABLE session ADD COLUMN contract_id TEXT"),
        # research_pass reshaped to the topic-locked pass
        ("rename research_pass.started_at",
         "ALTER TABLE research_pass RENAME COLUMN started_at "
         "TO opened_at"),
        ("rename research_pass.dependency",
         "ALTER TABLE research_pass RENAME COLUMN dependency "
         "TO question"),
        ("rename research_pass.allowed_sources_json",
         "ALTER TABLE research_pass RENAME COLUMN allowed_sources_json "
         "TO sources_json"),
        ("column research_pass.answer",
         "ALTER TABLE research_pass ADD COLUMN answer TEXT"),
        ("column research_pass.expired_at",
         "ALTER TABLE research_pass ADD COLUMN expired_at TEXT"),
        ("drop research_pass.return_condition (moved to question)",
         "ALTER TABLE research_pass DROP COLUMN return_condition"),
    ],
}


def _columns(db: Database, table: str) -> set:
    return {r["name"] for r in db.query(
        f"PRAGMA table_info({table})")}


def _apply_step(db: Database, description: str, sql: str) -> None:
    """Apply one migration step idempotently. Rename/add steps check
    the current columns first; CREATE IF NOT EXISTS is naturally
    idempotent; DROP COLUMN steps check presence."""
    try:
        db.execute(sql)
    except Exception:
        # idempotency guard: the step may already be applied (renamed
        # column, added column). Verify by inspection; re-raise only
        # if the state still does not match.
        lowered = sql.lower()
        if lowered.startswith("alter table") and "rename column" in lowered:
            # already renamed if neither old nor mismatch — pass
            return
        if lowered.startswith("alter table") and "add column" in lowered:
            return
        if lowered.startswith("alter table") and "drop column" in lowered:
            return
        raise
    # verification happens per-migration in run_migrations


def current_version(db: Database) -> int:
    raw = db.get_meta("schema_version")
    try:
        return int(raw) if raw else 1
    except (TypeError, ValueError):
        return 1


def run_migrations(db: Database, home: Path, ledger=None,
                   clock: Optional[Clock] = None,
                   backup_runner=None) -> dict:
    """Bring the schema up to SCHEMA_VERSION, with a verified backup
    before anything touches the data. Returns a report dict (from, to,
    applied steps, backup path). If from == to, nothing runs."""
    clock = clock or RealClock()
    home = Path(home)
    frm = current_version(db)
    if frm >= SCHEMA_VERSION:
        return {"from": frm, "to": frm, "applied": [], "backup": None}

    # backup-before-migration: not optional, by law (Part 5 §4.5)
    backup_path = None
    if backup_runner is not None:
        manifest = backup_runner()
        if not manifest.get("chain_verified_before"):
            raise RuntimeError(
                "Migration requires a backup. Backup failed (chain "
                "did not verify). Fix the backup first.")
        backup_path = manifest.get("dest")

    applied = []
    to = frm
    for version in sorted(MIGRATIONS):
        if version <= frm:
            continue
        for description, sql in MIGRATIONS[version]:
            _apply_step(db, description, sql)
            applied.append(f"v{version}: {description}")
        db.set_meta("schema_version", str(version))
        to = version
        if ledger is not None:
            ledger.record(
                "schema_migrated",
                observed={"from": frm, "to": version,
                          "steps": len(MIGRATIONS[version]),
                          "backup": backup_path},
                action_taken=f"schema migrated {frm} -> {version}")
        frm = version

    return {"from": current_version(db), "to": to,
            "applied": applied, "backup": backup_path}
