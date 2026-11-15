"""The rituals (v0.7.0 Part 4): compost, absence, physical register,
broken-contract ceremony, letters, voice archive, quiet hour, debrief,
confession, the 90-day archive, meta-commitment review.

Every item here is buildable now, needs no external resource, and
defaults off unless it is obviously harmless (the Two-Sentence
Aftermath). Each is small; together they are the project's own answer
to 'the tool became the activity' — these rituals ask the OPERATOR to
show up, not the system.
"""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso


class CompostRitual:
    """§4.2: the quarterly letting-go. Lists what aged out of
    relevance; the operator types a letting-go note (or skips); the
    items are marked; the counts are recorded."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("compost", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    def due(self) -> bool:
        interval = int(self.config.get("interval_days", 90))
        last = self.db.query_one(
            "SELECT occurred_at_utc FROM event WHERE "
            "event_type='compost_ritual_completed' ORDER BY seq DESC "
            "LIMIT 1")
        if last is None:
            # no compost ever: due once there is something old
            return bool(self._aged_items() or self._aged_parked()
                        or self._unsealed_contracts())
        return (self.clock.now_utc()
                - parse_iso(last["occurred_at_utc"])).days >= interval

    def _aged_items(self) -> list:
        cutoff = (self.clock.now_utc()
                  - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.db.query(
            "SELECT id, title FROM content_item WHERE opened_at IS "
            "NULL AND abandoned_at IS NULL AND aged_out_at IS NULL "
            "AND saved_at_utc <= ?", (cutoff,))

    def _aged_parked(self) -> list:
        cutoff = (self.clock.now_utc()
                  - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.db.query(
            "SELECT id, question FROM parking_lot WHERE "
            "disposition IS NULL AND created_at <= ?", (cutoff,))

    def _unsealed_contracts(self) -> list:
        cutoff = (self.clock.now_utc()
                  - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.db.query(
            "SELECT id, scope_date FROM contract WHERE "
            "state='SUPERSEDED' AND created_at <= ?", (cutoff,))

    def candidates(self) -> dict:
        return {"content_items": self._aged_items(),
                "parked": self._aged_parked(),
                "unsealed_contracts": self._unsealed_contracts()}

    def complete(self, notes: dict) -> dict:
        """notes: {item_id: letting-go note or 'skip'}. Skipped items
        stay; noted items are abandoned/dropped/archived. An id that
        resolves to nothing is neither composted nor kept — it is
        reported to the caller by not counting."""
        counts = {"composted": 0, "kept": 0}
        now = to_iso(self.clock.now_utc())
        for item_id, note in (notes or {}).items():
            item = self.db.query_one(
                "SELECT id FROM content_item WHERE id=?", (item_id,))
            parked = None if item else self.db.query_one(
                "SELECT id FROM parking_lot WHERE id=?", (item_id,))
            if item is None and parked is None:
                continue  # unknown id: not counted either way
            if (note or "").strip().lower() == "skip":
                counts["kept"] += 1
                continue
            if item:
                self.db.execute(
                    "UPDATE content_item SET abandoned_at=?, "
                    "abandoned_reason=? WHERE id=?",
                    (now, f"composted: {note}"[:500], item_id))
                counts["composted"] += 1
                continue
            self.db.execute(
                "UPDATE parking_lot SET disposition='dropped', "
                "disposed_at=?, note=? WHERE id=?",
                (now, f"composted: {note}"[:500], item_id))
            counts["composted"] += 1
        if self.ledger is not None:
            self.ledger.record(
                "compost_ritual_completed",
                observed=counts,
                action_taken="the quarterly letting-go, done cold")
        return counts


class AbsenceTest:
    """§4.3: the monthly system-off day. Declared cold; on that day
    the daemon refuses to start sessions ('the absence test is
    active') and the next aftermath asks the one question."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("absence", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    def declare(self, date_iso: str) -> dict:
        month = date_iso[:7]
        month_rows = self.db.query(
            "SELECT date FROM absence_day WHERE date LIKE ?",
            (month + "%",))
        max_days = int(self.config.get("max_days_per_month", 1))
        if len(month_rows) >= max_days:
            raise ValueError(
                f"absence is capped at {max_days} day(s) per month — "
                "the test stays a test")
        self.db.execute(
            "INSERT OR IGNORE INTO absence_day(date, declared_at) "
            "VALUES (?, ?)", (date_iso, to_iso(self.clock.now_utc())))
        if self.ledger is not None:
            self.ledger.record(
                "absence_test_day",
                observed={"date": date_iso},
                action_taken="declared cold; the system will not "
                             "enforce that day")
        return {"date": date_iso}

    def is_active(self, date_iso: str) -> bool:
        row = self.db.query_one(
            "SELECT 1 AS one FROM absence_day WHERE date=?",
            (date_iso,))
        return row is not None


class CeremonyService:
    """§4.5: the broken-contract ceremony. The fact lives in the
    ledger (word count only); the feeling lives in
    broken_contracts.md — the record keeps the fact, the file keeps
    the feeling."""

    def __init__(self, db: Database, config: dict, home: Path,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("ceremony", {})
        self.home = Path(home)
        self.clock = clock or RealClock()
        self.ledger = ledger

    def eligible_dates(self) -> list:
        return self.db.query(
            "SELECT date, state FROM day WHERE state IN "
            "('CLOSED_INCOMPLETE', 'RECOVERED') ORDER BY date DESC "
            "LIMIT 7")

    def write(self, date_iso: str, paragraph: str,
              contract_line: str = "", identity: str = "") -> dict:
        paragraph = (paragraph or "").strip()
        if len(paragraph) < 20:
            raise ValueError(
                "one paragraph — at least a few honest sentences")
        target = self.home / "broken_contracts.md"
        with target.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {date_iso}\n\n{paragraph}\n\n")
            if contract_line:
                fh.write(f"- the contract line: {contract_line}\n")
            if identity:
                fh.write(f"- the identity line: {identity}\n")
        if self.ledger is not None:
            self.ledger.record(
                "broken_contract_ceremony",
                observed={"date": date_iso,
                          "word_count": len(paragraph.split())},
                action_taken="ceremony held; the file keeps the "
                             "feeling, the ledger keeps the fact")
        return {"date": date_iso,
                "word_count": len(paragraph.split()),
                "path": str(target)}


class LetterService:
    """§4.10: the 6-month letter. --now writes; --read returns the
    letter due this month (written 6 months ago)."""

    def __init__(self, db: Database, config: dict, home: Path,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("letters", {})
        self.home = Path(home)
        self.clock = clock or RealClock()
        self.ledger = ledger

    def write(self, text: str) -> dict:
        text = (text or "").strip()
        if len(text) < 50:
            raise ValueError(
                "a letter to future-self deserves at least a "
                "paragraph (50+ chars)")
        date = self.clock.now_utc().strftime("%Y-%m-%d")
        letters = self.home / "letters"
        letters.mkdir(parents=True, exist_ok=True)
        path = letters / f"{date}.txt"
        path.write_text(text, encoding="utf-8")
        if self.ledger is not None:
            self.ledger.record(
                "letter_written",
                observed={"date": date, "path": str(path)},
                action_taken="written to future-self")
        return {"date": date, "path": str(path)}

    def due(self) -> Optional[dict]:
        """The letter written ~6 months ago, if any."""
        cutoff = self.clock.now_utc() - timedelta(days=182)
        letters = sorted((self.home / "letters").glob("*.txt")) \
            if (self.home / "letters").is_dir() else []
        for path in letters:
            try:
                written = parse_iso(
                    path.stem + "T00:00:00Z")
            except Exception:
                continue
            if written <= cutoff:
                return {"date": path.stem, "path": str(path),
                        "text": path.read_text(encoding="utf-8")}
        return None


class VoiceArchive:
    """§4.11: the voice archive. The typed version works without any
    audio setup; recording actual audio is the user's setup (config
    voice_archive.enabled), off by default."""

    def __init__(self, db: Database, config: dict, home: Path,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("voice_archive", {})
        self.home = Path(home)
        self.clock = clock or RealClock()
        self.ledger = ledger

    def record_typed(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValueError("say something — the archive is yours")
        date = self.clock.now_utc().strftime("%Y-%m-%d")
        voice = self.home / "voice"
        voice.mkdir(parents=True, exist_ok=True)
        path = voice / f"{date}.md"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n## {to_iso(self.clock.now_utc())}\n\n"
                     f"{text}\n")
        if self.ledger is not None:
            self.ledger.record(
                "voice_memo_recorded",
                observed={"date": date, "mode": "typed"},
                action_taken="typed voice memo archived")
        return {"date": date, "path": str(path), "mode": "typed"}


class QuietHour:
    """§4.8: one hour per week where the daemon does no enforcement,
    no observation, no mirror. The user lives it."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("quiet_hour", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    def active_now(self) -> bool:
        if not self.config.get("enabled", False):
            return False
        from .timeutil import local_tz
        tz = local_tz("Asia/Kolkata")  # the daemon passes config in
        start = self.config.get("start_local", "16:00")
        duration = int(self.config.get("duration_minutes", 60))
        hh, mm = (int(x) for x in start.split(":"))
        now_local = self.clock.now_utc().astimezone(tz)
        start_local = now_local.replace(hour=hh, minute=mm,
                                        second=0, microsecond=0)
        end_local = start_local + timedelta(minutes=duration)
        return start_local <= now_local < end_local

    def mark_observed(self, date_iso: str):
        if self.ledger is not None:
            self.ledger.record(
                "quiet_hour_observed",
                observed={"date": date_iso},
                action_taken="the quiet hour was honored — no log "
                             "required")


class DebriefService:
    """§4.9: the 30-second transition. After every session finish,
    one optional prompt — 'What happened? (one sentence)'."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("debrief", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

    def record(self, session_id: str, one_sentence: str) -> dict:
        one_sentence = (one_sentence or "").strip()
        if not one_sentence:
            return {"skipped": True}  # optional means skippable
        if self.ledger is not None:
            self.ledger.record(
                "session_debrief",
                session_id=session_id,
                observed={"sentence": one_sentence[:300]},
                action_taken="the 30-second transition, recorded")
        return {"skipped": False, "sentence": one_sentence}


class ConfessionService:
    """§4.14: the bounded two-turn confession. No LLM needed — the
    mirror is a structural echo with a 'why' prompt. Two turns. No
    offers."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("confession", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    def mirror_turn(self, statement: str) -> str:
        """Turn 1: echo + 'why?'. Turn 2: echo + [session ends]."""
        statement = (statement or "").strip()
        if not statement:
            raise ValueError("name it — one honest sentence")
        return f"You said: \"{statement}\". Why?"

    def close_turn(self, statement: str) -> str:
        return f"You said: \"{(statement or '').strip()}\"."

    def record(self, first: str, second: str, break_record_id: str):
        if self.ledger is not None:
            self.ledger.record(
                "confession_event",
                observed={"break": break_record_id[:8],
                          "turns": 2},
                action_taken="two turns, no offers; the break-glass "
                             "proceeds (or does not)")
        return {"turns": [first, second]}


class ArchiveService:
    """§4.13: the 90-day archive — a book-length document of the
    quarter: every contract, session, break, review, mirror action,
    parking disposition."""

    def __init__(self, db: Database, config: dict, home: Path,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("archive", {})
        self.home = Path(home)
        self.clock = clock or RealClock()
        self.ledger = ledger

    def quarter_bounds(self, year: int, quarter: int) -> tuple:
        starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
        ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
        return (f"{year}-{starts[quarter]}",
                f"{year}-{ends[quarter]}")

    def generate(self, year: int, quarter: int) -> dict:
        start, end = self.quarter_bounds(year, quarter)
        lines = [f"# Dhriti archive — {year}-Q{quarter}", "",
                 f"Scope: {start} .. {end}", ""]
        for table, label in (
                ("contract", "Contracts"),
                ("session", "Sessions"),
                ("break_glass", "Breaks"),
                ("cold_review", "Reviews"),
                ("parking_lot", "Parking lot dispositions")):
            date_col = {"contract": "scope_date", "session":
                        "started_at", "break_glass": "pressed_at",
                        "cold_review": "created_at",
                        "parking_lot": "created_at"}[table]
            rows = self.db.query(
                f"SELECT * FROM {table} WHERE {date_col} >= ? AND "
                f"{date_col} <= ? ORDER BY {date_col}",
                (start, end + "T23:59:59Z"))
            lines.append(f"## {label} ({len(rows)})")
            for row in rows[:2000]:
                summary = row.get("contract_line") or \
                    row.get("task") or row.get("reason") or \
                    row.get("answer") or row.get("question") or ""
                if table == "contract" and not summary:
                    # the contract line lives in the payload JSON
                    # column, not a flat column
                    try:
                        payload = json.loads(row.get("payload_json")
                                             or "{}")
                        summary = payload.get("contract_line", "")
                    except Exception:
                        summary = ""
                state = row.get("state") or row.get("disposition") or ""
                lines.append(f"- {row.get('id', '')[:8]} "
                             f"[{state}] {str(summary)[:120]}")
            lines.append("")
        # mirror actions from the ledger
        mirror_events = self.db.query(
            "SELECT COUNT(*) AS n FROM event WHERE event_type LIKE "
            "'content_item_%' AND occurred_at_utc >= ? AND "
            "occurred_at_utc <= ?",
            (start + "T00:00:00Z", end + "T23:59:59Z"))
        lines.append(f"## Mirror actions "
                     f"({mirror_events[0]['n']} events)")
        lines.append("")
        reports = self.home / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        path = reports / f"archive-{year}-Q{quarter}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        if self.ledger is not None:
            self.ledger.record(
                "archive_generated",
                observed={"quarter": f"{year}-Q{quarter}",
                          "path": str(path)},
                action_taken="the quarter, in one document")
        return {"path": str(path), "quarter": f"{year}-Q{quarter}"}


class MetaCommitment:
    """§4.7: no config change during an active commitment. Off by
    default; when on, config edits mid-bootcamp are refused and
    routed through the meta-review."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("meta_commitment", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    def active(self) -> bool:
        return bool(self.config.get("enabled", False))

    def check_config_change(self, bootcamp_active: bool) -> None:
        """Raises when the commitment covers the change."""
        if not (self.active() and bootcamp_active):
            return
        raise PermissionError(
            "You committed to not changing the rules mid-bootcamp. "
            "End the bootcamp in cold state, or open the "
            "meta-commitment review (dhriti meta-review).")

    def review(self, choice: str, change: str) -> dict:
        """(a) genuine correction -> the commitment is lifted for
        THIS change; (b) avoidance -> refused; (c) unclear -> deferred
        24h."""
        if choice not in ("a", "b", "c"):
            raise ValueError("choice must be a|b|c")
        outcomes = {"a": "lifted for this change",
                    "b": "refused",
                    "c": "deferred 24h"}
        if self.ledger is not None:
            self.ledger.record(
                "meta_commitment_review",
                observed={"choice": choice, "change": change[:200],
                          "outcome": outcomes[choice]},
                action_taken="the meta-review, recorded")
        return {"choice": choice, "outcome": outcomes[choice]}
