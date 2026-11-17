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

    def create(self, day_id: str, contract_id: str,
               task: str = "", next_action: str = "", blocker: str = "") -> dict:
        session_id = str(uuid.uuid4())
        outcome = None
        if next_action or blocker:
            outcome = json.dumps({
                "resume_capsule": {
                    "next_action": next_action.strip(),
                    "blocker": blocker.strip(),
                    "updated_at": self.clock.iso()
                }
            })
        self.db.insert("session", {
            "id": session_id,
            "day_id": day_id,
            "contract_id": contract_id,
            "started_at": self.clock.iso(),
            "state": SessionState.DRAFT.value,
            "task": task,
            "evidence_spec": None,
            "experiment_condition": None,
            "ended_at": None,
            "outcome_json": outcome,
        })
        return self.get(session_id)

    def checkpoint(self, session_id: str, next_action: str = "", blocker: str = "",
                   artifact: str = "") -> dict:
        sess = self.get(session_id)
        if not sess:
            raise StateError("session not found")
        outcome = {}
        if sess.get("outcome_json"):
            try:
                outcome = json.loads(sess["outcome_json"]) or {}
            except Exception:
                outcome = {}
        capsule = outcome.get("resume_capsule", {})
        if next_action:
            capsule["next_action"] = next_action.strip()
        if blocker:
            capsule["blocker"] = blocker.strip()
        if artifact:
            capsule["artifact"] = artifact.strip()
        capsule["updated_at"] = self.clock.iso()
        outcome["resume_capsule"] = capsule
        self.db.update("session", session_id, {"outcome_json": json.dumps(outcome)})
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

    # -- lifecycle ------------------------------------------------------------
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

    def finish(self, session_id: str, state: SessionState,
               targets_met: Optional[bool] = None,
               note: str = "") -> dict:
        """Finish a session into one of the three honest terminal
        states. targets_met=True (SUCCESS) also marks the day's targets
        met — a finished proof is what the day was for."""
        extra = {"outcome_json": json.dumps({"note": note})}
        result = self._transition(session_id, state, extra)
        if state is SessionState.SUCCESS and targets_met:
            row = self.get(session_id)
            if row and row.get("day_id"):
                self.db.execute(
                    "UPDATE day SET targets_met=1 WHERE id=?",
                    (row["day_id"],))
        return result

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
