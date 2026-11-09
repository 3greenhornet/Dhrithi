"""Vidura: the spaced-review scheduler for the user's own answers
(v0.5.0). Named for Vidura — the counsel who says the thing once.

What Vidura is NOT (yet): the saved-content mirror. The mirror
(Part 3) records and surfaces saved content; Vidura schedules the
user's own declarations — research-pass answers first, identity
statements never (see docs/VIDURA.md; identity lines are shown, not
spaced — the v0.6.0 correction of the v0.5.0 mistake).

The scheduler is an SM-2 variant (docs/VIDURA.md §3): the ease-factor
update and grade mapping follow SM-2; the interval sequence is
I(n) = I(n-1) * EF' from the first review onward, not the textbook
I(2)=6 jump. First review always produces a 1-day interval.
"""

import json
import uuid
from datetime import timedelta
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, to_iso

GRADES = ("again", "hard", "good", "easy")

# SM-2 ease-factor bounds.
EF_MIN, EF_MAX = 1.3, 2.5
EF_DEFAULT = 2.5

# Item kinds (v0.6.0, Bug B): identity statements are NOT Vidura
# items — they are shown at the top of the day report, never spaced
# (serving "2026-11-02 — identity" as a recall prompt is a category
# error: the user wrote it; there is nothing to recall from a date).
KINDS = ("research_answer", "note")


def _ef_update(ef: float, grade: str) -> float:
    """The SM-2 ease-factor update, clamped to [1.3, 2.5]."""
    q = {"again": 0, "hard": 3, "good": 4, "easy": 5}[grade]
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    if grade == "again":
        return EF_MIN
    return max(EF_MIN, min(EF_MAX, ef + delta))


class ViduraService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("vidura", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    # -- ingest ----------------------------------------------------------------
    def add(self, kind: str, front: str, back: str,
            day_date: Optional[str] = None) -> dict:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        front, back = (front or "").strip(), (back or "").strip()
        if not front or not back:
            raise ValueError("an item needs a front and a back")
        item_id = str(uuid.uuid4())
        now = self.clock.now_utc()
        self.db.insert("vidura_item", {
            "id": item_id,
            "kind": kind,
            "front": front[:500],
            "back": back[:2000],
            "created_at": to_iso(now),
            "day_date": day_date,
            "reps": 0,
            "lapses": 0,
            "ease_factor": EF_DEFAULT,
            "interval_days": 0.0,
            "due_at": to_iso(now + timedelta(days=1)),
        })
        if self.ledger is not None:
            self.ledger.record(
                "vidura_item_ingested",
                observed={"kind": kind, "front": front[:100]},
                action_taken="item scheduled for spaced review")
        return self.item(item_id)

    def ingest_identity_line(self, contract: dict) -> None:
        """v0.6.0 (Bug B): removed. Identity statements are not spaced
        items; they are shown at the top of the day report. The method
        intentionally no longer exists — this stub documents the
        removal and raises so old callers fail loudly, not silently."""
        raise AttributeError(
            "ingest_identity_line was removed in v0.6.0 (Bug B): "
            "identity statements are shown in the day report, not "
            "spaced. See docs/VIDURA.md §2 and D-065.")

    def ingest_pass_answers(self, date: str, passes=None) -> list:
        """Ingest the research-pass answers returned on `date` as
        spaced items: front = the declared question, back = the
        returned answer."""
        if passes is None:
            from .research_pass import ResearchService
            passes = ResearchService(
                self.db, {"research_pass": {}}, self.clock
            ).returned_on(date)
        items = []
        for p in passes:
            if not (p.get("answer") or "").strip():
                continue
            items.append(self.add(
                "research_answer", p["question"], p["answer"],
                day_date=date))
        return items

    # -- review ------------------------------------------------------------------
    def item(self, item_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM vidura_item WHERE id=?", (item_id,))

    def due(self, on_date: Optional[str] = None) -> list:
        now = self.clock.now_utc()
        return self.db.query(
            "SELECT * FROM vidura_item WHERE due_at<=? "
            "ORDER BY due_at", (on_date or to_iso(now),))

    def review(self, item_id: str, grade: str) -> dict:
        if grade not in GRADES:
            raise ValueError(f"grade must be one of {GRADES}, "
                             f"got {grade!r}")
        row = self.item(item_id)
        if not row:
            raise ValueError(f"no such item {item_id}")
        ef = float(row["ease_factor"])
        interval = float(row["interval_days"])
        reps = int(row["reps"])

        if grade == "again":
            reps = 0
            lapses = int(row["lapses"]) + 1
            new_interval = 1.0
            new_ef = _ef_update(ef, grade)
        elif grade == "hard":
            new_interval = max(1.0, interval * 1.2)
            lapses = int(row["lapses"])
            new_ef = _ef_update(ef, grade)
            reps += 1
        else:
            new_ef = _ef_update(ef, grade)
            reps += 1
            lapses = int(row["lapses"])
            if reps == 1:
                new_interval = 1.0
            elif grade == "easy":
                new_interval = interval * new_ef * 1.3
            else:
                new_interval = interval * new_ef

        now = self.clock.now_utc()
        due_at = to_iso(now + timedelta(days=new_interval))
        self.db.update("vidura_item", item_id, {
            "reps": reps, "lapses": lapses,
            "ease_factor": round(new_ef, 4),
            "interval_days": round(new_interval, 4),
            "due_at": due_at,
        })
        review_id = str(uuid.uuid4())
        self.db.insert("vidura_review", {
            "id": review_id,
            "item_id": item_id,
            "reviewed_at": to_iso(now),
            "grade": grade,
            "interval_days": round(new_interval, 4),
            "ease_factor": round(new_ef, 4),
        })
        if self.ledger is not None:
            self.ledger.record(
                "vidura_item_reviewed",
                observed={"item": item_id[:8], "grade": grade,
                          "interval_days": round(new_interval, 2)},
                action_taken="review recorded")
        return self.item(item_id)
