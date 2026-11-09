"""Bounded research passes (dossier 6.4, 6.5 — the finite research
environment), rebuilt in v0.5.0 as the topic-locked AI pass.

A pass is opened with a declared question and a minute budget. While
the pass is open, the declared sources (by default the AI-chat surfaces
the session already needs) are allowed. When the pass expires, its
sources stop being allowed — no renewal from inside the session. The
answer is returned (typed, cold-reviewable) and later ingested into
Vidura as a spaced item.

This replaces "universal semantic similarity" with a dependency chain:
  primary outcome -> obstacle -> declared question -> bounded sources ->
  answer -> return to task.
"""

import json
import uuid
from datetime import timedelta
from typing import Optional

from .db import Database
from .errors import DhritiError
from .models import ResearchPassState
from .profiles import CATEGORY_DOMAINS
from .timeutil import Clock, RealClock, parse_iso, to_iso


class ResearchPassError(DhritiError):
    pass


def _default_sources() -> list:
    """The AI-chat surfaces a topic-locked pass allows by default."""
    return sorted(CATEGORY_DOMAINS.get("ai_chat", []))


class ResearchService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None):
        self.db = db
        self.config = config
        self.default_max_minutes = int(
            config.get("research_pass", {}).get("default_max_minutes", 20))
        self.clock = clock or RealClock()

    # -- lifecycle ------------------------------------------------------------
    def open(self, session_id: str, question: str,
             minutes: Optional[int] = None,
             sources: Optional[list] = None) -> dict:
        """Open a pass: a declared question, a minute budget, a finite
        source list. The question is the topic lock — it is recorded
        and shown with the answer in the cold review. One pass at a
        time per session: the topic is singular, so is the pass."""
        existing = self.active(session_id)
        if existing is not None:
            raise ResearchPassError(
                "a pass is already open for this session — return from "
                "it (dhriti research return) before opening another")
        question = (question or "").strip()
        if not question:
            raise ResearchPassError(
                "a declared question is required — the pass is bounded "
                "by what it is for")
        minutes = int(self.default_max_minutes if minutes is None
                      else minutes)
        if minutes <= 0 or minutes > 120:
            raise ResearchPassError(
                "minutes must be in 1..120 — a pass is finite by design")
        pass_id = str(uuid.uuid4())
        now = self.clock.now_utc()
        row = {
            "id": pass_id,
            "session_id": session_id,
            "day_id": None,
            "question": question[:500],
            "sources_json": json.dumps(sources or _default_sources()),
            "opened_at": to_iso(now),
            "expires_at": to_iso(now + timedelta(minutes=minutes)),
            "state": ResearchPassState.OPEN.value,
            "returned_at": None,
            "answer": None,
            "expired_at": None,
        }
        self.db.insert("research_pass", row)
        return self.get(pass_id)

    def get(self, pass_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM research_pass WHERE id=?", (pass_id,))
        if row:
            row["sources"] = json.loads(row.pop("sources_json"))
        return row

    def return_pass(self, answer: str, pass_id: Optional[str] = None) -> dict:
        """Return from the pass with the answer (typed, kept for the
        cold review and the Vidura ingest)."""
        if pass_id is None:
            row = self.active()
            if row is None:
                raise ResearchPassError("no open pass to return from")
            pass_id = row["id"]
        row = self.db.query_one(
            "SELECT * FROM research_pass WHERE id=?", (pass_id,))
        if not row or row["state"] != ResearchPassState.OPEN.value:
            raise ResearchPassError("pass not open")
        self.db.update("research_pass", pass_id, {
            "state": ResearchPassState.RETURNED.value,
            "returned_at": self.clock.iso(),
            "answer": (answer or "")[:5000],
        })
        return self.get(pass_id)

    def expire(self, pass_id: str) -> dict:
        row = self.db.query_one(
            "SELECT * FROM research_pass WHERE id=?", (pass_id,))
        if not row or row["state"] != ResearchPassState.OPEN.value:
            return self.get(pass_id) if row else {"id": pass_id}
        self.db.update("research_pass", pass_id, {
            "state": ResearchPassState.EXPIRED.value,
            "expired_at": self.clock.iso(),
        })
        return self.get(pass_id)

    def expire_overdue(self, grace_seconds: int = 0) -> list:
        """Daemon tick: expire OPEN passes past their expiry (v0.5.0:
        hard expiry at expires_at; see v0.6.0 mechanism 5 for the grace
        period that accepts a mid-paragraph return)."""
        expired = []
        for row in self.db.query(
                "SELECT id, expires_at FROM research_pass "
                "WHERE state='OPEN'"):
            if self.clock.now_utc() > parse_iso(row["expires_at"]):
                self.expire(row["id"])
                expired.append(row["id"])
        return expired

    # -- queries ----------------------------------------------------------------
    def active(self, session_id: Optional[str] = None) -> Optional[dict]:
        """The open, unexpired pass (optionally for one session)."""
        rows = self.db.query(
            "SELECT * FROM research_pass WHERE state='OPEN' "
            "ORDER BY opened_at DESC")
        for row in rows:
            if parse_iso(row["expires_at"]) <= self.clock.now_utc():
                continue
            if session_id and row["session_id"] != session_id:
                continue
            row["sources"] = json.loads(row["sources_json"])
            return row
        return None

    def active_for(self, session_id=None) -> Optional[dict]:
        """v0.3.0 name kept as an alias (the daemon's policy snapshot
        uses it)."""
        return self.active(session_id)

    def active_sources(self) -> list:
        """The sources the policy engine should allow right now: only
        while a pass is open AND inside its window. After expiry the
        pass may still accept a late answer; its sources are gone."""
        active = self.active()
        if active is None:
            return []
        return active["sources"]

    def returned_on(self, date: str) -> list:
        """Passes returned on a local date (for the Vidura ingest)."""
        rows = self.db.query(
            "SELECT * FROM research_pass WHERE state='RETURNED' "
            "AND returned_at LIKE ? ORDER BY returned_at", (date + "%",))
        for row in rows:
            row["sources"] = json.loads(row.pop("sources_json"))
        return rows
