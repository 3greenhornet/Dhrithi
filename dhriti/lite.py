"""Dhriti Lite (v0.7.0 Part 4 §4.21): the smallest working thing.

The full system is intimidating. Lite is three contract fields (task,
action, evidence), one session, one evidence submission, one
aftermath. No mirror, no bootcamp, no taper, no review. ~200 lines by
law — when Lite grows past what fits on one screen, it has become
the full system and must be split back.

`dhriti lite` enters Lite mode; while a Lite day is unfinished, lite
refuses to run any other command (the point is finishing one day).
"""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, to_iso


class LiteMode:
    def __init__(self, db: Database, home: Path,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.home = Path(home)
        self.clock = clock or RealClock()
        self.ledger = ledger

    # -- state ----------------------------------------------------------------
    def active(self) -> bool:
        row = self.db.query_one(
            "SELECT value FROM meta WHERE "
            "key='lite_mode_active'")
        return bool(row and row["value"] == "1")

    def _set_active(self, value: bool):
        self.db.set_meta("lite_mode_active", "1" if value else "0")

    def current_day(self) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM lite_day WHERE finished_at IS NULL "
            "ORDER BY started_at DESC LIMIT 1")

    # -- the flow ----------------------------------------------------------------
    def start(self, task: str, action: str, evidence_kind: str) -> dict:
        """The three fields. That is the whole contract."""
        task = (task or "").strip()
        action = (action or "").strip()
        if not task or not action:
            raise ValueError("lite needs a task and the smallest "
                             "next action — three fields, that's all")
        if evidence_kind not in ("machine", "file", "manual"):
            raise ValueError("evidence kind: machine|file|manual")
        if self.current_day():
            raise ValueError(
                "a lite day is already open — finish it first "
                "(lite is the smallest thing, including its exit)")
        self._set_active(True)
        if self.ledger is not None:
            self.ledger.record(
                "lite_mode_active",
                observed={"task": task[:100]},
                action_taken="lite mode entered; the smallest working "
                             "thing")
        day = {"id": str(uuid.uuid4()),
               "started_at": to_iso(self.clock.now_utc()),
               "task": task[:300],
               "action": action[:300],
               "evidence_kind": evidence_kind,
               "evidence_submitted": 0,
               "finished_at": None}
        self.db.insert("lite_day", day)
        return day

    def submit_evidence(self, detail: str = "") -> dict:
        day = self.current_day()
        if not day:
            raise ValueError("no open lite day")
        self.db.execute(
            "UPDATE lite_day SET evidence_submitted=1 WHERE id=?",
            (day["id"],))
        if self.ledger is not None:
            self.ledger.record(
                "lite_evidence_submitted",
                observed={"task": day["task"][:100],
                          "detail": (detail or "")[:200]},
                action_taken="lite evidence recorded")
        return self.current_day()

    def finish(self) -> dict:
        day = self.current_day()
        if not day:
            raise ValueError("no open lite day")
        if not day["evidence_submitted"]:
            raise ValueError(
                "submit the evidence first — lite has one rule: "
                "finish means proof")
        self.db.execute(
            "UPDATE lite_day SET finished_at=? WHERE id=?",
            (to_iso(self.clock.now_utc()), day["id"]))
        self._set_active(False)
        if self.ledger is not None:
            self.ledger.record(
                "lite_day_completed",
                observed={"task": day["task"][:100]},
                action_taken="one lite day done — the smallest "
                             "working thing, worked")
        return self.db.query_one(
            "SELECT * FROM lite_day WHERE id=?", (day["id"],))

    def guard_other_commands(self) -> None:
        """While a lite day is unfinished, lite refuses to run any
        other command — the point is finishing one day."""
        if self.current_day():
            raise PermissionError(
                "a lite day is open; finish it first "
                "(dhriti lite finish). Lite is the smallest thing, "
                "including its exit.")

    # -- the aftermath ----------------------------------------------------------
    def report(self) -> str:
        day = self.current_day() or self.db.query_one(
            "SELECT * FROM lite_day ORDER BY started_at DESC "
            "LIMIT 1")
        if not day:
            return "no lite day yet — dhriti lite start"
        lines = [
            "# Lite day",
            f"task: {day['task']}",
            f"action: {day['action']}",
            f"evidence ({day['evidence_kind']}): "
            f"{'submitted' if day['evidence_submitted'] else 'not yet'}",
            f"started: {day['started_at']}",
            f"finished: {day['finished_at'] or '(open)'}",
        ]
        return "\n".join(lines)
