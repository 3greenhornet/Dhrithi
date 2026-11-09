"""Bounded research passes (dossier 6.4, 6.5 — the finite research
environment): a dependency triggers a pass with an explicit scope,
finite source list, expiry and return condition. When the pass expires,
its sources stop being allowed — no renewal from inside the session.

This replaces "universal semantic similarity" with a dependency chain:
  primary outcome -> obstacle -> dependency -> permitted resource ->
  finding -> return to task.
"""

import json
import uuid
from datetime import timedelta
from typing import Optional

from .db import Database
from .errors import DhritiError
from .models import ResearchPassState
from .timeutil import Clock, RealClock, parse_iso, to_iso


class ResearchPassError(DhritiError):
    pass


class ResearchService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None):
        self.db = db
        self.default_max_minutes = int(
            config.get("research_pass", {}).get("default_max_minutes", 20))
        self.clock = clock or RealClock()

    def start(self, dependency: str, sources: list,
              return_condition: str,
              session_id: Optional[str] = None,
              day_id: Optional[str] = None,
              max_minutes: Optional[int] = None) -> dict:
        if not dependency.strip():
            raise ResearchPassError("dependency required (what obstacle "
                                    "blocks the task?)")
        if not sources:
            raise ResearchPassError(
                "at least one declared source required — a pass is finite "
                "by design")
        if not return_condition.strip():
            raise ResearchPassError(
                "return condition required (what sends you back to the "
                "task?)")
        minutes = int(max_minutes or self.default_max_minutes)
        pass_id = str(uuid.uuid4())
        now = self.clock.now_utc()
        row = {
            "id": pass_id,
            "session_id": session_id,
            "day_id": day_id,
            "started_at": to_iso(now),
            "expires_at": to_iso(now + timedelta(minutes=minutes)),
            "dependency": dependency.strip(),
            "allowed_sources_json": json.dumps(sources),
            "return_condition": return_condition.strip(),
            "state": ResearchPassState.OPEN.value,
            "returned_at": None,
            "notes": None,
        }
        self.db.insert("research_pass", row)
        return self.get(pass_id)

    def get(self, pass_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM research_pass WHERE id=?", (pass_id,))
        if row:
            row["sources"] = json.loads(row.pop("allowed_sources_json"))
        return row

    def return_to_task(self, pass_id: str, notes: str = "") -> dict:
        row = self.db.query_one(
            "SELECT * FROM research_pass WHERE id=?", (pass_id,))
        if not row or row["state"] != ResearchPassState.OPEN.value:
            raise ResearchPassError("pass not open")
        self.db.update("research_pass", pass_id, {
            "state": ResearchPassState.RETURNED.value,
            "returned_at": self.clock.iso(),
            "notes": notes,
        })
        return self.get(pass_id)

    def expire_overdue(self) -> list:
        """Daemon tick: expire OPEN passes past their expiry."""
        expired = []
        for row in self.db.query(
                "SELECT id, expires_at FROM research_pass "
                "WHERE state='OPEN'"):
            if self.clock.now_utc() > parse_iso(row["expires_at"]):
                self.db.update("research_pass", row["id"], {
                    "state": ResearchPassState.EXPIRED.value,
                })
                expired.append(row["id"])
        return expired

    def active_for(self, session_id: Optional[str] = None) -> Optional[dict]:
        """The pass whose sources the policy engine should allow now."""
        rows = self.db.query(
            "SELECT * FROM research_pass WHERE state='OPEN' "
            "ORDER BY started_at DESC")
        for row in rows:
            if parse_iso(row["expires_at"]) <= self.clock.now_utc():
                continue
            if session_id and row["session_id"] not in (None, session_id):
                continue
            row["sources"] = json.loads(row["allowed_sources_json"])
            return row
        return None
