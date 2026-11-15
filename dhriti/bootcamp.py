"""Bootcamp container + evidence-based taper (PDF section 9, dossier
D-018/D-022 resolutions).

  * The commitment period (30/60/90 days) is the policy container.
  * No ordinary rule changes inside the period; reviews happen at
    pre-established intervals (weekly cold review), not on demand.
  * The taper is computed from evidence (compliance rate, proof rate,
    break-glass frequency) — never from elapsed time alone, and never
    guaranteed: "no taper until 30 days of evidence" is a floor, not a
    promise (dossier: graduation is a long-term experiment).
"""

import json
import uuid
from datetime import timedelta
from typing import Optional

from . import state_machine
from .db import Database
from .models import BootcampState, TaperStage
from .timeutil import Clock, RealClock, parse_iso, to_iso


class BootcampService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None):
        self.db = db
        self.config = config
        self.taper_cfg = config.get("taper", {})
        self.clock = clock or RealClock()

    def active(self) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM bootcamp WHERE state IN ('ACTIVE','TAPERED') "
            "ORDER BY started_at DESC LIMIT 1")

    def start(self, days: int = 30) -> dict:
        if self.active():
            raise ValueError(
                "a bootcamp is already running — finish or abandon it in a "
                "cold review first (no mid-period restarts)")
        if days not in (30, 60, 90):
            raise ValueError("bootcamp length must be 30, 60 or 90 days")
        bootcamp_id = str(uuid.uuid4())
        self.db.insert("bootcamp", {
            "id": bootcamp_id,
            "started_at": self.clock.iso(),
            "planned_days": days,
            "state": BootcampState.ACTIVE.value,
            "taper_stage": TaperStage.FULL_LOCK,
            "config_json": json.dumps(self.config),
        })
        return self.get(bootcamp_id)

    def get(self, bootcamp_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM bootcamp WHERE id=?", (bootcamp_id,))
        if row:
            row["config"] = json.loads(row.pop("config_json"))
        return row

    # -- evidence ------------------------------------------------------------
    def evidence_summary(self) -> dict:
        """The numbers the taper decision is allowed to look at."""
        bc = self.active()
        if not bc:
            return {"days_elapsed": 0, "days_total": 0, "days_with_day": 0,
                    "compliance_rate": 0.0, "proof_rate": 0.0,
                    "break_glass_7d": 0, "can_consider_taper": False}
        started = parse_iso(bc["started_at"])
        days_elapsed = (self.clock.now_utc() - started).days + 1
        # Bug 4 (Phase 0): filter by the bootcamp's own window. The old
        # query counted every day/session ever recorded, so restarting a
        # bootcamp inherited the previous bootcamp's history.
        started_iso = to_iso(started)
        days = self.db.query(
            "SELECT state, targets_met FROM day WHERE date>=?",
            (started_iso[:10],))
        days_total = len(days)
        complete = [d for d in days if d["state"] in
                    ("RELEASED_EARLY", "CLOSED_COMPLETE")]
        sessions = self.db.query(
            "SELECT state FROM session WHERE started_at>=?", (started_iso,))
        finished = [s for s in sessions
                    if s["state"] in ("SUCCESS", "INCOMPLETE",
                                      "BREAK_GLASS", "INTERRUPTED")]
        successes = [s for s in sessions if s["state"] == "SUCCESS"]
        since = to_iso(self.clock.now_utc() - timedelta(days=7))
        breaks = self.db.query_one(
            "SELECT COUNT(*) AS n FROM break_glass WHERE confirmed_at>=? "
            "AND confirmed_at IS NOT NULL", (since,))["n"]
        proof_rate = (len(successes) / len(finished)) if finished else 0.0
        compliance = (len(complete) / days_total) if days_total else 0.0
        min_days = int(self.taper_cfg.get("min_days", 30))
        return {
            "days_elapsed": days_elapsed,
            "days_with_day": days_total,
            "compliance_rate": round(compliance, 3),
            "proof_rate": round(proof_rate, 3),
            "break_glass_7d": breaks,
            "can_consider_taper": days_elapsed >= min_days,
        }

    def compute_taper(self) -> dict:
        """Recommend the stage the evidence supports. Never advances by
        date alone; never advances past what thresholds allow."""
        stats = self.evidence_summary()
        if not stats["can_consider_taper"]:
            return {"recommended_stage": TaperStage.FULL_LOCK,
                    "reason": f"fewer than "
                              f"{self.taper_cfg.get('min_days', 30)} days "
                              f"of evidence", "stats": stats}
        if stats["break_glass_7d"] > int(
                self.taper_cfg.get("breakglass_max_per_week", 1)):
            return {"recommended_stage": TaperStage.FULL_LOCK,
                    "reason": "break-glass frequency above threshold",
                    "stats": stats}
        if stats["compliance_rate"] >= float(
                self.taper_cfg.get("compliance_threshold", 0.80)) and \
                stats["proof_rate"] >= float(
                    self.taper_cfg.get("proof_threshold", 0.70)):
            current = (self.active() or {"taper_stage": 1})["taper_stage"]
            return {"recommended_stage": min(current + 1,
                                             TaperStage.ADVISORY),
                    "reason": "evidence thresholds met", "stats": stats}
        return {"recommended_stage": TaperStage.FULL_LOCK,
                "reason": "evidence thresholds not met", "stats": stats}

    def apply_taper(self, stage: int, reason: str) -> dict:
        bc = self.active()
        if not bc:
            raise ValueError("no active bootcamp")
        if int(stage) < int(bc["taper_stage"]):
            raise ValueError(
                "tightening back is a cold-review decision; recorded but "
                "requires explicit review — use force with intent")
        state_machine.assert_transition(
            "bootcamp", BootcampState(bc["state"]), BootcampState(bc["state"]))
        self.db.update("bootcamp", bc["id"], {
            "state": BootcampState.TAPERED.value if stage > 1
            else bc["state"],
            "taper_stage": int(stage),
        })
        return self.get(bc["id"])

    def graduate(self) -> dict:
        bc = self.active()
        if not bc:
            raise ValueError("no active bootcamp")
        state_machine.assert_transition(
            "bootcamp", BootcampState(bc["state"]),
            BootcampState.GRADUATED)
        self.db.update("bootcamp", bc["id"], {
            "state": BootcampState.GRADUATED.value})
        return self.get(bc["id"])
