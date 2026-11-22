"""The day-window enforcement model (PDF section 3 + RESOLUTIONS.md R1).

The enforcement boundary is the commitment period, not the session: the
daemon runs for the whole bootcamp; the wall is up for the whole window.

One local date resolves to a DayWindow:
    window_start (10:00) ... day_close (20:00) ... window_end (21:00)

  * Between window_start and window_end the day is OPEN — wall up. The
    user is on stage or offline. Audience mode is not available.
  * Finishing targets early does NOT release before day_close (closes
    the easy-contract loophole, PDF 3.7).
  * At/after day_close, met targets release the day early.
  * At window_end everything releases unconditionally — bounded release,
    never an indefinite lock (dossier D-018 resolution).
  * A day with no sealed contract never opens: it is recorded
    NO_CONTRACT and counts as a non-compliant day. Honest, not punitive.
"""

import datetime as _dt
import json
import uuid
from typing import Optional

from . import state_machine
from .contract import ContractService
from .db import Database
from .errors import ContractError
from .models import DayState, DayWindow
from .timeutil import Clock, RealClock, local_tz, parse_hhmm, parse_iso, to_iso


def resolve_window(local_date: _dt.date, config: dict) -> DayWindow:
    tz = local_tz(config.get("timezone", "UTC"))
    win = config.get("day_window", {})
    start_t = parse_hhmm(win.get("start", "10:00"))
    close_t = parse_hhmm(win.get("day_close", "20:00"))
    end_t = parse_hhmm(win.get("end", "21:00"))
    if not (start_t < close_t <= end_t):
        raise ValueError(
            "day_window requires start < day_close <= end "
            f"(got {win.get('start')} / {win.get('day_close')} / "
            f"{win.get('end')})")
    window_start = _dt.datetime.combine(local_date, start_t, tzinfo=tz)
    day_close = _dt.datetime.combine(local_date, close_t, tzinfo=tz)
    window_end = _dt.datetime.combine(local_date, end_t, tzinfo=tz)
    return DayWindow(local_date, config.get("timezone", "UTC"),
                     window_start, day_close, window_end)


def resolve_observation_end(local_date: _dt.date, config: dict) -> _dt.datetime:
    """D-048: where OBSERVATION ends. Enforcement ends at window_end and
    nothing may change that; observation may run longer (evening) when
    observation_evening is enabled — until day_end, bounded, consented
    cold under the surveillance_comfort question. day_end must not be
    before window_end (an observation ceiling below the enforcement
    ceiling would be incoherent)."""
    tz = local_tz(config.get("timezone", "UTC"))
    end_t = parse_hhmm(config.get("observation_evening", {})
                       .get("day_end", "23:59"))
    obs_end = _dt.datetime.combine(local_date, end_t, tzinfo=tz)
    win = resolve_window(local_date, config)
    if obs_end < win.window_end:
        obs_end = win.window_end
    return obs_end


class DayService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None):
        self.db = db
        self.config = config
        self.clock = clock or RealClock()
        self.contracts = ContractService(db, clock)

    # -- create / fetch ------------------------------------------------------
    def ensure_day(self, local_date,
                   bootcamp_id: Optional[str] = None) -> dict:
        if isinstance(local_date, str):
            local_date = _dt.date.fromisoformat(local_date)
        row = self.get(local_date)
        if row:
            return row
        win = resolve_window(local_date, self.config)
        contract = None
        try:
            contract = self.contracts.require_sealed_daily(local_date)
        except ContractError:
            pass  # recorded below; the day cannot OPEN without a contract
        day_id = str(uuid.uuid4())
        state = (DayState.PLANNED if contract
                 else DayState.NO_CONTRACT).value
        self.db.insert("day", {
            "id": day_id,
            "date": local_date.isoformat(),
            "bootcamp_id": bootcamp_id,
            "contract_id": contract["id"] if contract else None,
            "state": state,
            "window_start_at": to_iso(win.window_start),
            "day_close_at": to_iso(win.day_close),
            "window_end_at": to_iso(win.window_end),
            "released_at": None,
            "targets_json": json.dumps(
                (contract["payload"].get("targets")
                 if contract else None) or []),
            "targets_met": 0,
            "note": None,
        })
        return self.get(local_date)

    def get(self, local_date) -> Optional[dict]:
        if isinstance(local_date, str):
            local_date = _dt.date.fromisoformat(local_date)
        return self.db.query_one(
            "SELECT * FROM day WHERE date=?", (local_date.isoformat(),))

    def today(self) -> dict:
        """Ensure + return today's day row."""
        tz = local_tz(self.config.get("timezone", "UTC"))
        return self.ensure_day(
            self.clock.now_utc().astimezone(tz).date())

    def get_by_id(self, day_id: str) -> Optional[dict]:
        return self.db.query_one("SELECT * FROM day WHERE id=?", (day_id,))

    # -- transitions ----------------------------------------------------------
    def try_open(self, day: dict, contract: Optional[dict] = None) -> dict:
        """Open the wall at/after window_start. Requires a sealed
        contract (passed in or looked up). Opens from PLANNED, and
        from NO_CONTRACT when a contract was sealed after the row was
        created (the daemon's order: contract cold, then day)."""
        now = self.clock.now_utc()
        current = DayState(day["state"])
        if current not in (DayState.PLANNED, DayState.NO_CONTRACT):
            return day
        win = resolve_window(_dt.date.fromisoformat(day["date"]), self.config)
        if now < win.window_start:
            return day
        if contract is None:
            try:
                contract = self.contracts.require_sealed_daily(
                    _dt.date.fromisoformat(day["date"]))
            except ContractError:
                return day  # stays NO_CONTRACT / PLANNED until a contract seals
        state_machine.assert_transition("day", current, DayState.OPEN)
        self.db.update("day", day["id"], {
            "state": DayState.OPEN.value,
            "contract_id": contract["id"],
            "targets_json": json.dumps(
                contract["payload"].get("targets") or []),
        })
        return self.get_by_id(day["id"])

    def evaluate(self, day: dict, targets_met_now: bool) -> dict:
        """Clock-driven evaluation; the daemon calls this every tick.

        Ordering guarantees (fail-proof): the unconditional window_end
        release is checked FIRST, so no target/early-release logic can
        ever extend the day beyond the ceiling.
        """
        now = self.clock.now_utc()
        current = DayState(day["state"])
        if current not in (DayState.OPEN, DayState.NO_CONTRACT):
            return day
        date = _dt.date.fromisoformat(day["date"])
        win = resolve_window(date, self.config)

        # 1. unconditional ceiling
        if now >= win.window_end:
            final = (DayState.CLOSED_COMPLETE if targets_met_now
                     else DayState.CLOSED_INCOMPLETE)
            if current is DayState.NO_CONTRACT:
                final = DayState.CLOSED_INCOMPLETE
            state_machine.assert_transition("day", current, final)
            self.db.update("day", day["id"], {
                "state": final.value,
                "released_at": to_iso(win.window_end),
                "targets_met": 1 if targets_met_now else 0,
            })
            return self.get_by_id(day["id"])

        if current is DayState.NO_CONTRACT:
            # A contract may still seal mid-window and open the day.
            return self.try_open(day)

        # 2. early release only at/after day_close AND targets met
        if targets_met_now and now >= win.day_close:
            state_machine.assert_transition(
                "day", current, DayState.RELEASED_EARLY)
            self.db.update("day", day["id"], {
                "state": DayState.RELEASED_EARLY.value,
                "released_at": to_iso(now),
                "targets_met": 1,
            })
            return self.get_by_id(day["id"])

        return day

    # -- targets ----------------------------------------------------------------
    def targets_met(self, day: dict) -> bool:
        """Targets are honest and simple: each target names an evidence
        class; a target is met when evidence of that class was ACCEPTED
        for a session on this day. No targets: any accepted evidence
        counts. The day's contract defines the targets; the software
        does not judge content."""
        targets = json.loads(day.get("targets_json") or "[]")
        accepted = self.db.query(
            "SELECT e.class AS class, e.kind AS kind, e.detail_json AS "
            "detail FROM evidence e JOIN session s ON e.session_id=s.id "
            "WHERE s.day_id=? AND e.verdict='ACCEPTED'", (day["id"],))

        # Check ledger/event table for verified learning proof events for this contract/date
        verified_learning_target_ids = set()
        try:
            contract_row = self.db.query_one("SELECT id FROM contract WHERE scope_date=?", (day["date"],))
            contract_id = contract_row["id"] if contract_row else None
            ev_rows = self.db.query("SELECT observed_payload FROM event WHERE event_type='learning_proof_verified'")
            for r in ev_rows:
                try:
                    payload = json.loads(r["observed_payload"] or "{}")
                    cid = payload.get("contract_id")
                    if cid is None or str(cid) == str(contract_id):
                        tid = payload.get("target_id")
                        if tid is not None:
                            verified_learning_target_ids.add(str(tid))
                except Exception:
                    pass
        except Exception:
            pass

        if not targets:
            return len(accepted) > 0 or len(verified_learning_target_ids) > 0

        for target in targets:
            tid = str(target.get("id", ""))
            if tid and tid in verified_learning_target_ids:
                continue
            ev = target.get("evidence") or {}
            ev_class = ev.get("class")
            if tid and "target_id" not in ev:
                ev = {**ev, "target_id": tid}
            if not any(self._matches_target(a, ev) for a in accepted):
                return False
        return True

    @staticmethod
    def _matches_target(accepted_row: dict, ev_spec: dict) -> bool:
        """Does one accepted evidence row satisfy one target's
        evidence spec? class must match; command/path match when the
        target names one."""
        ev_class = ev_spec.get("class")
        row_class = {"machine": "MACHINE_CHECKED",
                     "file": "SUBMITTED",
                     "manual": "SUBMITTED",
                     "learning": "MACHINE_CHECKED"}.get(ev_class, ev_class)
        if accepted_row["class"] != row_class:
            return False
        if ev_class == "manual":
            # manual claims are never accepted as proof — a manual
            # target can only be met by review, i.e. never by the
            # machine; honest default.
            return False
        try:
            detail = json.loads(accepted_row.get("detail") or "{}")
        except Exception:
            detail = {}
        if ev_class == "learning":
            wanted_id = str(ev_spec.get("target_id") or "").strip()
            if wanted_id and "target_id" in detail:
                return str(detail.get("target_id") or "").strip() == wanted_id
            return accepted_row["kind"] == "learning_proof" or detail.get("kind") == "learning_proof"
        if ev_class == "machine":
            wanted_cmd = (ev_spec.get("command") or "").strip()
            if wanted_cmd:
                return (detail.get("command") or "").strip() == wanted_cmd
            return accepted_row["kind"] != "manual"
        if ev_class == "file":
            wanted_path = (ev_spec.get("path") or "").strip()
            if wanted_path:
                return detail.get("path", "").endswith(wanted_path)
            return accepted_row["kind"] == "file"
        return True

    # -- recovery ------------------------------------------------------------
    def recover_open_days(self) -> list:
        """Called once at daemon start: any day still OPEN/NO_CONTRACT whose
        window_end already passed while we were down closes honestly as
        RECOVERED (dossier: unexpected termination is marked, not hidden)."""
        recovered = []
        for day in self.db.query(
                "SELECT * FROM day WHERE state IN ('OPEN','NO_CONTRACT')"):
            date = _dt.date.fromisoformat(day["date"])
            win = resolve_window(date, self.config)
            if self.clock.now_utc() > win.window_end:
                state_machine.assert_transition(
                    "day", DayState(day["state"]), DayState.RECOVERED)
                self.db.update("day", day["id"], {
                    "state": DayState.RECOVERED.value,
                    "note": "daemon was not running at window_end; "
                            "outcome could not be verified",
                })
                recovered.append(day["id"])
        return recovered
