"""Declared leisure (D-047) — chosen rest vs. drift.

The specimen's sharpest ethical line, in its own words: "if you are
truly content being an audience member, then own it — chosen rest is
honest; undeclared drift is avoidance." Before v0.3 the system could
not express either half: evenings were unmeasured, and every
consumption hour was invisible or shame-loaded.

The mechanism is deliberately tiny:

  * `dhriti declare leisure --activity "..." --minutes 45` — one-way,
    typed, bounded (1..240 minutes; "the rest of the evening" is not a
    declaration, it is the absence of one);
  * a declaration is a LABEL, never a permission: it unblocks nothing,
    stops nothing, and requires no session (rest happens in the
    evening, when no session can exist);
  * the aftermath shows declared windows next to undeclared
    consumption ("drift") — the two numbers, side by side, no verdict;
  * the cold review asks whether the declarations held (conditional
    question: only asked when a declaration exists for the day).

This is the anti-shame, anti-permissive middle path: the system never
guesses whether an evening hour was rest or avoidance — the user
declares, the facts check.
"""

import uuid
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso

MAX_MINUTES = 240       # bounded, like everything else in Dhriti


class LeisureService:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def declare(self, activity: str, minutes: int, note: str = "",
                day_date: Optional[str] = None) -> dict:
        """Record one bounded declaration of chosen rest."""
        activity = (activity or "").strip()
        if not activity:
            raise ValueError("declare the activity, not an empty line")
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            raise ValueError("minutes must be a number")
        if not (1 <= minutes <= MAX_MINUTES):
            raise ValueError(
                f"minutes must be 1..{MAX_MINUTES} — unbounded rest is "
                "the thing being declared against")
        day_date = day_date or self.clock.iso()[:10]
        row_id = str(uuid.uuid4())
        created_at = self.clock.iso()
        ends_at = to_iso(parse_iso(created_at)
                         + _minutes_delta(minutes))
        self.db.insert("leisure_declaration", {
            "id": row_id,
            "created_at": created_at,
            "day_date": day_date,
            "activity": activity[:200],
            "planned_minutes": minutes,
            "ends_at": ends_at,
            "note": (note or "")[:500],
        })
        if self.ledger is not None:
            self.ledger.record(
                "leisure_declared",
                observed_payload={
                    "activity": activity[:100],
                    "planned_minutes": minutes,
                    "day_date": day_date,
                },
                action_taken="declared rest recorded — a label, not a "
                             "permission",
                telemetry_quality="OK")
        return self.get(row_id)

    def get(self, row_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM leisure_declaration WHERE id=?", (row_id,))

    def for_day(self, day_date: str) -> list:
        return self.db.query(
            "SELECT * FROM leisure_declaration WHERE day_date=? "
            "ORDER BY created_at", (day_date,))

    def between(self, start_date: str, end_date: str) -> list:
        return self.db.query(
            "SELECT * FROM leisure_declaration WHERE day_date>=? AND "
            "day_date<? ORDER BY created_at", (start_date, end_date))

    def list(self) -> list:
        return self.db.query(
            "SELECT * FROM leisure_declaration ORDER BY created_at")


def _minutes_delta(minutes: int):
    from datetime import timedelta
    return timedelta(minutes=minutes)
