"""Sessions: atomic work blocks inside the open day (PDF 3.5, dossier 3.4).

Exactly three ways a session resolves:
  SUCCESS      accepted proof submitted
  INCOMPLETE   ended without accepted proof
  BREAK_GLASS  the user paid the toll

Plus the honest fourth: INTERRUPTED (daemon died) -> reviewed at next
boot into one of the three above. Nothing else exists. No pause, no
snooze, no "five more minutes" (Principle 2).
"""

import json
import uuid
from typing import Optional

from . import state_machine
from .db import Database
from .errors import StateError
from .models import SessionState
from .timeutil import Clock, RealClock


class SessionService:
    def __init__(self, db: Database, clock: Optional[Clock] = None):
        self.db = db
        self.clock = clock or RealClock()

    def start(self, day_id: str, task: str, evidence_spec: str = "",
              experiment_condition: Optional[str] = None) -> dict:
        session_id = str(uuid.uuid4())
        self.db.insert("session", {
            "id": session_id,
            "day_id": day_id,
            "started_at": self.clock.iso(),
            "state": SessionState.DRAFT.value,
            "task": task,
            "evidence_spec": evidence_spec,
            "experiment_condition": experiment_condition,
            "ended_at": None,
            "outcome_json": None,
        })
        return self.get(session_id)

    def get(self, session_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM session WHERE id=?", (session_id,))

    def _transition(self, session_id: str, target: SessionState,
                    extra: Optional[dict] = None) -> dict:
        row = self.get(session_id)
        if not row:
            raise StateError("session not found")
        current = SessionState(row["state"])
        state_machine.assert_transition("session", current, target)
        updates = {"state": target.value}
        if target in (SessionState.SUCCESS, SessionState.INCOMPLETE,
                      SessionState.BREAK_GLASS, SessionState.INTERRUPTED):
            updates["ended_at"] = self.clock.iso()
        if extra:
            updates.update(extra)
        self.db.update("session", session_id, updates)
        return self.get(session_id)

    # -- lifecycle helpers used by the daemon/CLI -----------------------------
    def seal(self, session_id: str) -> dict:
        return self._transition(session_id, SessionState.SEALED)

    def arming(self, session_id: str) -> dict:
        return self._transition(session_id, SessionState.ARMING)

    def activate(self, session_id: str) -> dict:
        return self._transition(session_id, SessionState.ACTIVE)

    def arming_failed(self, session_id: str, reason: str) -> dict:
        return self._transition(session_id, SessionState.ARMING_FAILED,
                                {"outcome_json": json.dumps(
                                    {"arming_failure": reason})})

    def end_success(self, session_id: str, note: str = "") -> dict:
        return self._transition(session_id, SessionState.SUCCESS,
                                {"outcome_json": json.dumps({"note": note})})

    def end_incomplete(self, session_id: str, note: str = "") -> dict:
        return self._transition(session_id, SessionState.INCOMPLETE,
                                {"outcome_json": json.dumps({"note": note})})

    def end_break_glass(self, session_id: str, reason: str) -> dict:
        return self._transition(session_id, SessionState.BREAK_GLASS,
                                {"outcome_json": json.dumps(
                                    {"reason": reason})})

    def mark_interrupted(self, session_id: str) -> dict:
        """Recovery path: called at daemon boot for sessions left in
        ARMING/ACTIVE when the previous daemon died."""
        return self._transition(session_id, SessionState.INTERRUPTED)

    # -- queries ----------------------------------------------------------------
    def sessions_for_day(self, day_id: str) -> list:
        return self.db.query(
            "SELECT * FROM session WHERE day_id=? ORDER BY started_at",
            (day_id,))

    def unfinished(self) -> list:
        return self.db.query(
            "SELECT * FROM session WHERE state IN ('SEALED','ARMING',"
            "'ACTIVE','ARMING_FAILED')")

    def active(self) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM session WHERE state='ACTIVE' "
            "ORDER BY started_at DESC LIMIT 1")

    def accepted_evidence_count(self, session_id: str) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) AS n FROM evidence WHERE session_id=? AND "
            "verdict='ACCEPTED'", (session_id,))
        return row["n"]
