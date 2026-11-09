"""Break-glass: the only exit, and it is a toll, not a wall (PDF section 7).

Flow (deliberately boring, no commentary, no guilt):
  1. initiate()  — records the press instant and returns a confirm
                   deadline (default 60s). No "are you sure?" dialog.
  2. confirm()   — requires the typed reason (>= min chars), checks the
                   delay was honored and no cooldown is active. If the
                   delay was bypassed (confirmed early), that fact is
                   logged honestly as honored_delay=0 — the system does
                   not pretend it could stop you (tamper-evident, not
                   tamper-proof).
  3. The declared cold-state penalty is recorded as DECLARED, never
                   auto-executed (dossier: consequences never depend on
                   destructive actions; the system does not claim to
                   impose what it merely logs).
  4. cooldown_until is set — new sessions cannot start until it passes.
"""

import json
import uuid
from datetime import timedelta
from typing import Optional

from .db import Database
from .errors import BreakGlassError
from .models import SessionState
from .timeutil import Clock, RealClock, parse_iso, to_iso


class BreakGlassService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("break_glass", {})
        self.clock = clock or RealClock()
        self.ledger = ledger  # optional: Ledger for tamper-evident events

    @property
    def delay_seconds(self) -> int:
        return int(self.config.get("delay_seconds", 60))

    @property
    def cooldown_hours(self) -> float:
        return float(self.config.get("cooldown_hours", 2))

    def _last_confirmed(self):
        return self.db.query_one(
            "SELECT * FROM break_glass WHERE confirmed_at IS NOT NULL "
            "ORDER BY confirmed_at DESC LIMIT 1")

    def cooldown_active(self) -> Optional[str]:
        last = self._last_confirmed()
        if not last or not last["cooldown_until"]:
            return None
        if self.clock.now_utc() < parse_iso(last["cooldown_until"]):
            return last["cooldown_until"]
        return None

    def initiate(self, session_id: Optional[str] = None,
                 day_id: Optional[str] = None) -> dict:
        """The button press. Returns the handle + confirm deadline."""
        if self.cooldown_active():
            until = self.cooldown_active()
            raise BreakGlassError(
                f"cooldown active until {until}; no new break-glass or "
                "session may start")
        handle = str(uuid.uuid4())
        pressed_at = self.clock.now_utc()
        deadline = pressed_at + timedelta(seconds=self.delay_seconds)
        self.db.insert("break_glass", {
            "id": handle,
            "session_id": session_id,
            "day_id": day_id,
            "pressed_at": to_iso(pressed_at),
            "confirmed_at": None,
            "reason": None,
            "honored_delay": 0,
            "cooldown_until": None,
            "penalty_declared": json.dumps(
                self.config.get("penalties", [])),
        })
        return {
            "handle": handle,
            "confirm_not_before": to_iso(deadline),
            "delay_seconds": self.delay_seconds,
            "instruction": "wait, then confirm with a typed reason",
        }

    def confirm(self, handle: str, reason: str,
                session_service=None) -> dict:
        """The toll booth. Enforces the typed reason and records whether
        the delay was honored."""
        row = self.db.query_one(
            "SELECT * FROM break_glass WHERE id=?", (handle,))
        if not row:
            raise BreakGlassError("unknown break-glass handle")
        if row["confirmed_at"]:
            raise BreakGlassError("handle already confirmed")
        reason = (reason or "").strip()
        min_chars = int(self.config.get("min_reason_chars", 20))
        if len(reason) < min_chars:
            raise BreakGlassError(
                f"typed reason required ({len(reason)}/{min_chars} chars) — "
                "typed words, not a dropdown")
        now = self.clock.now_utc()
        pressed = parse_iso(row["pressed_at"])
        deadline = pressed + timedelta(seconds=self.delay_seconds)
        honored = int(now >= deadline)
        if not honored:
            # Bypassing the wait is possible (owner of the machine); it is
            # recorded through the ledger, not prevented-and-pretended.
            if self.ledger is not None:
                self.ledger.record(
                    "break_glass_delay_bypassed",
                    session_id=row["session_id"],
                    observed_payload={
                        "handle": handle,
                        "seconds_early": int((deadline - now).total_seconds()),
                    },
                    action_taken="logged", telemetry_quality="OK")
        cooldown_until = to_iso(now + timedelta(hours=self.cooldown_hours))
        self.db.update("break_glass", handle, {
            "confirmed_at": to_iso(now),
            "reason": reason,
            "honored_delay": honored,
            "cooldown_until": cooldown_until,
        })
        result = {"handle": handle, "honored_delay": bool(honored),
                  "cooldown_until": cooldown_until,
                  "penalty_declared": json.loads(row["penalty_declared"] or "[]")}
        # end the session if one was attached and still active
        if session_service and row["session_id"]:
            sess = session_service.get(row["session_id"])
            if sess and sess["state"] == SessionState.ACTIVE.value:
                session_service.end_break_glass(row["session_id"], reason)
        return result

    # -- emergency path (D-019) ------------------------------------------------
    def emergency(self, reason: str, session_id: Optional[str] = None,
                  day_id: Optional[str] = None,
                  session_service=None) -> dict:
        """The immediate emergency exit — distinct from the ordinary toll.

        D-019: there is always an immediate path for genuine emergencies
        (medical, family, system on fire). It is NOT a cheaper break-glass:
          * a typed reason is still required (shorter minimum — urgency
            is real, but the log entry is not optional);
          * no cooldown is set, because a real emergency must not lock
            the user out of starting work again;
          * it is recorded as `emergency_exception`, never as SUCCESS,
            and the aftermath shows it separately from break-glass so a
            pattern of "emergencies" is visible in cold review.
        The system does not judge whether it was a real emergency. It
        records the claim; the cold review reads the pattern.
        """
        reason = (reason or "").strip()
        min_chars = int(self.config.get("emergency_min_reason_chars", 10))
        if len(reason) < min_chars:
            raise BreakGlassError(
                f"emergency reason required ({len(reason)}/{min_chars} "
                "chars) — one honest sentence for the log")
        now = self.clock.now_utc()
        handle = str(uuid.uuid4())
        self.db.insert("break_glass", {
            "id": handle,
            "session_id": session_id,
            "day_id": day_id,
            "pressed_at": to_iso(now),
            "confirmed_at": to_iso(now),
            "reason": reason,
            "honored_delay": 1,          # no delay was due
            "cooldown_until": None,      # emergencies never lock work out
            "penalty_declared": json.dumps(
                {"type": "emergency", "policy": "no penalty; logged and "
                 "reviewed in cold state"}),
        })
        if self.ledger is not None:
            self.ledger.record(
                "emergency_exception",
                session_id=session_id,
                observed_payload={"reason": reason},
                action_taken="immediate release; logged for cold review",
                telemetry_quality="OK")
        if session_service and session_id:
            sess = session_service.get(session_id)
            if sess and sess["state"] == SessionState.ACTIVE.value:
                session_service.end_break_glass(session_id, reason)
        return {"handle": handle, "emergency": True,
                "reason": reason}

    def history(self, limit: int = 50) -> list:
        return self.db.query(
            "SELECT * FROM break_glass ORDER BY pressed_at DESC LIMIT ?",
            (limit,))

    def check_session_start_allowed(self):
        """Cooldown also blocks starting a new session (prevents the
        break-restart-break loop, PDF 7.2.5)."""
        until = self.cooldown_active()
        if until:
            raise BreakGlassError(
                f"break-glass cooldown active until {until}")
