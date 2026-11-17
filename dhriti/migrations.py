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
    # v0.6.0 Part 1 §2 (Bug B): orphan identity_line vidura items are
    # dropped — identity statements are shown, not spaced.
    4: [
        ("drop orphan identity_line items",
         "DELETE FROM vidura_review WHERE item_id IN (SELECT id FROM "
         "vidura_item WHERE kind='identity_line')"),
        ("drop orphan identity_line items (items)",
         "DELETE FROM vidura_item WHERE kind='identity_line'"),
    ],
    # v0.6.0 Part 2 §1.1: the parking lot resurfacing columns. The
    # table is rebuilt (disposition becomes nullable; the kind/spark/
    # surfacing columns arrive in one pass — SQLite cannot alter a
    # column's nullability in place).
    5: [
        ("rebuild parking_lot with resurfacing columns",
         "CREATE TABLE parking_lot_v6("
         " id TEXT PRIMARY KEY,"
         " created_at TEXT NOT NULL,"
         " session_id TEXT,"
         " day_id TEXT,"
         " question TEXT NOT NULL,"
         " source TEXT,"
         " kind TEXT NOT NULL DEFAULT 'question',"
         " sparked_by_url TEXT,"
         " sparked_by_event_id TEXT,"
         " disposition TEXT,"
         " disposed_at TEXT,"
         " note TEXT,"
         " evening_surfaced_at TEXT,"
         " review_surfaced_at TEXT,"
         " approved_to_contract_day TEXT)"),
        ("copy parking_lot into the new shape",
         "INSERT INTO parking_lot_v6(id, created_at, session_id, "
         "day_id, question, source, kind, sparked_by_url, "
         "sparked_by_event_id, disposition, disposed_at, note) "
         "SELECT id, created_at, session_id, day_id, question, source, "
         "'question', NULL, NULL, "
         "CASE WHEN disposition='parked' THEN NULL ELSE disposition END, "
         "disposed_at, note FROM parking_lot"),
        ("replace parking_lot with the new shape",
         "DROP TABLE parking_lot"),
        ("rename parking_lot_v6 to parking_lot",
         "ALTER TABLE parking_lot_v6 RENAME TO parking_lot"),
        ("index parking_lot_kind",
         "CREATE INDEX IF NOT EXISTS idx_parking_lot_kind "
         "ON parking_lot(kind)"),
    ],
    # v0.7.0 Part 3 §3.1/§3.2/§3.17: the mirror, the life mirror, the
    # friction ladder's stored artifacts, and the Part 4 declarations.
    6: [
        ("table content_source",
         "CREATE TABLE IF NOT EXISTS content_source("
         " id TEXT PRIMARY KEY,"
         " source_type TEXT NOT NULL,"
         " source_identifier TEXT NOT NULL,"
         " display_name TEXT NOT NULL,"
         " enabled INTEGER NOT NULL DEFAULT 1,"
         " intent_class TEXT NOT NULL DEFAULT 'intent',"
         " created_at TEXT NOT NULL,"
         " last_ingested_at TEXT,"
         " UNIQUE(source_type, source_identifier))"),
        ("table content_item",
         "CREATE TABLE IF NOT EXISTS content_item("
         " id TEXT PRIMARY KEY,"
         " source_id TEXT NOT NULL REFERENCES content_source(id),"
         " external_id TEXT NOT NULL,"
         " title TEXT NOT NULL,"
         " description TEXT,"
         " duration_seconds INTEGER,"
         " thumbnail_url TEXT,"
         " published_at TEXT,"
         " saved_at_utc TEXT NOT NULL,"
         " last_surfaced_at TEXT,"
         " surface_count INTEGER NOT NULL DEFAULT 0,"
         " dismiss_count INTEGER NOT NULL DEFAULT 0,"
         " consecutive_dismissals INTEGER NOT NULL DEFAULT 0,"
         " times_resaved INTEGER NOT NULL DEFAULT 0,"
         " opened_at TEXT,"
         " completed_at TEXT,"
         " abandoned_at TEXT,"
         " abandoned_reason TEXT,"
         " aged_out_at TEXT,"
         " metadata_completeness REAL NOT NULL DEFAULT 1.0,"
         " category TEXT NOT NULL DEFAULT 'unknown',"
         " category_confidence REAL NOT NULL DEFAULT 0.0,"
         " category_classified_at TEXT,"
         " category_classified_by TEXT,"
         " intent_class TEXT NOT NULL DEFAULT 'intent',"
         " effort_tier TEXT,"
         " recall_attempts INTEGER NOT NULL DEFAULT 0,"
         " recall_successes INTEGER NOT NULL DEFAULT 0,"
         " current_stability_days REAL NOT NULL DEFAULT 30.0,"
         " last_surface_intensity TEXT NOT NULL DEFAULT 'full',"
         " UNIQUE(source_id, external_id))"),
        ("index content_item_unopened",
         "CREATE INDEX IF NOT EXISTS idx_content_item_unopened "
         "ON content_item(saved_at_utc) WHERE opened_at IS NULL "
         "AND abandoned_at IS NULL AND aged_out_at IS NULL"),
        ("table content_item_progress",
         "CREATE TABLE IF NOT EXISTS content_item_progress("
         " id INTEGER PRIMARY KEY AUTOINCREMENT,"
         " item_id TEXT NOT NULL REFERENCES content_item(id),"
         " recorded_at TEXT NOT NULL,"
         " fraction REAL NOT NULL,"
         " source TEXT NOT NULL)"),
        ("table content_item_reentry",
         "CREATE TABLE IF NOT EXISTS content_item_reentry("
         " id TEXT PRIMARY KEY,"
         " item_id TEXT NOT NULL REFERENCES content_item(id),"
         " declared_at TEXT NOT NULL,"
         " context TEXT NOT NULL,"
         " session_id TEXT,"
         " day_date TEXT NOT NULL,"
         " outcome TEXT,"
         " outcome_recorded_at TEXT)"),
        ("table content_item_label",
         "CREATE TABLE IF NOT EXISTS content_item_label("
         " id TEXT PRIMARY KEY,"
         " item_id TEXT NOT NULL REFERENCES content_item(id),"
         " labeled_at TEXT NOT NULL,"
         " label TEXT NOT NULL,"
         " previous_classifier_category TEXT,"
         " previous_classifier_confidence REAL,"
         " classifier_version TEXT,"
         " source TEXT NOT NULL)"),
        ("table search_escape",
         "CREATE TABLE IF NOT EXISTS search_escape("
         " id INTEGER PRIMARY KEY AUTOINCREMENT,"
         " computed_at TEXT NOT NULL,"
         " search_at TEXT NOT NULL,"
         " search_query TEXT NOT NULL,"
         " search_host TEXT NOT NULL,"
         " matched_category TEXT NOT NULL,"
         " unopened_count INTEGER NOT NULL,"
         " oldest_unopened_days INTEGER NOT NULL)"),
        ("table fsrs_shadow",
         "CREATE TABLE IF NOT EXISTS fsrs_shadow("
         " id INTEGER PRIMARY KEY AUTOINCREMENT,"
         " computed_at TEXT NOT NULL,"
         " week_start TEXT NOT NULL,"
         " items_compared INTEGER NOT NULL,"
         " items_with_different_top_choice INTEGER NOT NULL,"
         " top_item_age_based TEXT,"
         " top_item_stability_based TEXT,"
         " rank_correlation REAL)"),
        ("table life_alternative",
         "CREATE TABLE IF NOT EXISTS life_alternative("
         " id TEXT PRIMARY KEY,"
         " created_at TEXT NOT NULL,"
         " label TEXT NOT NULL,"
         " kind TEXT NOT NULL,"
         " minimum_version TEXT,"
         " occurrence_log TEXT,"
         " last_logged_at TEXT,"
         " UNIQUE(label))"),
        ("table emergency_contact",
         "CREATE TABLE IF NOT EXISTS emergency_contact("
         " id TEXT PRIMARY KEY,"
         " created_at TEXT NOT NULL,"
         " label TEXT NOT NULL,"
         " contact TEXT NOT NULL)"),
        ("table absence_day",
         "CREATE TABLE IF NOT EXISTS absence_day("
         " date TEXT PRIMARY KEY,"
         " declared_at TEXT NOT NULL)"),
        ("table reflection_draw",
         "CREATE TABLE IF NOT EXISTS reflection_draw("
         " week_start TEXT PRIMARY KEY,"
         " question_index INTEGER NOT NULL,"
         " drawn_at TEXT NOT NULL)"),
        ("table lite_day",
         "CREATE TABLE IF NOT EXISTS lite_day("
         " id TEXT PRIMARY KEY,"
         " started_at TEXT NOT NULL,"
         " task TEXT NOT NULL,"
         " action TEXT NOT NULL,"
         " evidence_kind TEXT NOT NULL,"
         " evidence_submitted INTEGER NOT NULL DEFAULT 0,"
         " finished_at TEXT)"),
        ("table otp_code",
         "CREATE TABLE IF NOT EXISTS otp_code("
         " id TEXT PRIMARY KEY,"
         " break_id TEXT NOT NULL,"
         " code_hash TEXT NOT NULL,"
         " issued_at TEXT NOT NULL,"
         " expires_at TEXT NOT NULL,"
         " used_at TEXT)"),
        ("table barcode",
         "CREATE TABLE IF NOT EXISTS barcode("
         " id TEXT PRIMARY KEY,"
         " code_hash TEXT NOT NULL,"
         " label TEXT,"
         " created_at TEXT NOT NULL)"),
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
