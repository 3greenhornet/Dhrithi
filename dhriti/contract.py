"""Contracts: the cold-state ritual's output (PDF section 5, dossier 2.2,
plan v2.0 Artifact 1 / D-030).

A contract is written in a cold state, sealed, and becomes immutable.
Drafts may be superseded by newer drafts until sealing; sealed contracts
are never edited or deleted (DB triggers enforce, hash chain records).

Payload schema (docs/SCHEMAS.md):

  mandatory_task        what must be done
  smallest_next_action  the first physical step
  evidence              [{kind, spec}] what counts as proof
  targets               [{kind, count|description}] day/session targets
  allowed_tools         [] permitted apps/domains
  blocked_tools         [] forbidden apps/domains (beyond profile defaults)
  duration_minutes      session length hint (free, not enforced content)
  core_belief           why this matters (user's own words)
  identity_statement    who this task serves (user's own words)
  interruption_policy   which events permit ending early
  work_mode             closed_world | bounded_research | open_exploration

D-030 group (required — every task traces to the main belief; the main
belief is a filter, not a slogan):
  main_belief               "I want to be a software engineer"
  main_belief_metric        what would prove the belief is becoming real
  main_belief_current_state the honest assessment today ("I am failing the
                            course") — the failure state is the signal
  substitute_activities     known substitutes (guitar, multiplayer games)
  substitute_budget         time allowed for substitutes while healthy

IF–THEN obstacle plan group (optional, but all-or-nothing: a half-written
plan is worse than none, so the fields validate as a unit):
  expected_obstacle    the likely first obstacle
  if_then_response     the planned response to the obstacle
  return_condition     when to return to the main task
  research_fallback    {scope, sources[], max_minutes, return_condition}
                       bounded research allowance declared cold

emergency_policy (D-019): one sentence naming what counts as an
emergency — it makes the emergency path honest instead of a loophole.
"""

import datetime as _dt
import json
import uuid
from typing import Optional

from .db import Database
from .errors import ContractError
from .models import ContractKind, ContractState
from .timeutil import Clock, RealClock

REQUIRED_DAILY_FIELDS = [
    "mandatory_task", "smallest_next_action", "evidence",
    "core_belief", "identity_statement",
]

# D-030: the main belief and its exchange rate with substitutes.
MAIN_BELIEF_FIELDS = [
    "main_belief", "main_belief_metric", "main_belief_current_state",
    "substitute_activities", "substitute_budget",
]

# IF–THEN obstacle plan (plan v2.0 Artifact 1). Optional as a group;
# present means complete.
IF_THEN_FIELDS = ["expected_obstacle", "if_then_response",
                  "return_condition"]


def validate_payload(kind: ContractKind, payload: dict) -> list:
    """Return a list of problems (empty list = valid). Human-talks-to-human:
    the ritual wizard uses this to refuse incomplete contracts."""
    problems = []
    if kind == ContractKind.DAILY:
        for field in REQUIRED_DAILY_FIELDS:
            value = payload.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                problems.append(f"missing field: {field}")
        evidence = payload.get("evidence") or []
        if not isinstance(evidence, list) or not evidence:
            problems.append("evidence must be a non-empty list")
        elif not all(isinstance(e, dict) and e.get("kind") for e in evidence):
            problems.append("each evidence item needs at least a 'kind'")

        # D-030: the main-belief group is required and complete.
        missing_belief = [f for f in MAIN_BELIEF_FIELDS
                          if not _present(payload.get(f))]
        if missing_belief:
            problems.append(
                "main-belief group incomplete (D-030), missing: "
                + ", ".join(missing_belief))
        elif not isinstance(payload.get("substitute_budget"), (int, str)):
            problems.append("substitute_budget must be a number or string")

        # IF–THEN group: all or nothing.
        present_if_then = [f for f in IF_THEN_FIELDS
                           if _present(payload.get(f))]
        if present_if_then and len(present_if_then) != len(IF_THEN_FIELDS):
            problems.append(
                "if-then plan is partial (all-or-nothing), missing: "
                + ", ".join(f for f in IF_THEN_FIELDS
                            if f not in present_if_then))
        fallback = payload.get("research_fallback")
        if fallback is not None:
            if not (isinstance(fallback, dict) and fallback.get("scope")
                    and fallback.get("return_condition")):
                problems.append(
                    "research_fallback needs scope and return_condition "
                    "(bounded allowance, not a browsing exemption)")
        if present_if_then and not _present(payload.get("research_fallback")):
            # a plan without a fallback is still valid; note nothing.
            pass
    return problems


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


class ContractService:
    def __init__(self, db: Database, clock: Optional[Clock] = None):
        self.db = db
        self.clock = clock or RealClock()

    def create_draft(self, kind: ContractKind, scope_date: str,
                     payload: dict) -> str:
        problems = validate_payload(kind, payload)
        if problems:
            raise ContractError("invalid contract: " + "; ".join(problems))
        # supersede any existing DRAFT for the same scope
        existing_draft = self.db.query_one(
            "SELECT id FROM contract WHERE kind=? AND scope_date=? AND state=?",
            (kind.value, scope_date, ContractState.DRAFT.value))
        new_id = str(uuid.uuid4())
        supersedes = None
        if existing_draft:
            supersedes = existing_draft["id"]
            self.db.update("contract", existing_draft["id"],
                           {"state": ContractState.SUPERSEDED.value})
        self.db.insert("contract", {
            "id": new_id,
            "kind": kind.value,
            "scope_date": scope_date,
            "state": ContractState.DRAFT.value,
            "version": 1,
            "payload_json": json.dumps(payload, default=str),
            "created_at": self.clock.iso(),
            "sealed_at": None,
            "supersedes": supersedes,
        })
        return new_id

    def seal(self, contract_id: str) -> dict:
        row = self.get(contract_id)
        if not row:
            raise ContractError("contract not found")
        if row["state"] != ContractState.DRAFT.value:
            raise ContractError(
                f"cannot seal contract in state {row['state']} "
                "(sealed contracts are immutable)")
        sealed_at = self.clock.iso()
        self.db.update("contract", contract_id, {
            "state": ContractState.SEALED.value,
            "sealed_at": sealed_at,
        })
        return self.get(contract_id)

    def get(self, contract_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM contract WHERE id=?", (contract_id,))
        if row:
            row["payload"] = json.loads(row.pop("payload_json"))
        return row

    def sealed_for(self, kind: ContractKind, scope_date: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM contract WHERE kind=? AND scope_date=? "
            "AND state='SEALED'", (kind.value, scope_date))

    def require_sealed_daily(self, local_date: _dt.date) -> dict:
        """The one requirement of the day-window model (PDF 3.9): something
        must be written before the day can open."""
        row = self.sealed_for(ContractKind.DAILY, local_date.isoformat())
        if not row:
            raise ContractError(
                f"no sealed daily contract for {local_date.isoformat()}; "
                "run: dhriti ritual")
        row["payload"] = json.loads(row["payload_json"])
        return row

    def daily_scope(date: _dt.date) -> str:
        return date.isoformat()

    def weekly_scope(date: _dt.date) -> str:
        """ISO week start (Monday) as the weekly scope."""
        monday = date - _dt.timedelta(days=date.weekday())
        return monday.isoformat()

    def monthly_scope(date: _dt.date) -> str:
        return f"{date.year:04d}-{date.month:02d}"
