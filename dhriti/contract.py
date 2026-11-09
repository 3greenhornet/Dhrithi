"""Contracts: the cold-state ritual's output (PDF section 5, dossier 2.2,
plan v2.0 Artifact 1 / D-030).

A contract is written in a cold state, sealed, and becomes immutable.
Drafts may be superseded by newer drafts until sealing; sealed contracts
are never edited or deleted (DB triggers enforce, hash chain records).

Payload schema (docs/SCHEMAS.md):

  identity_statement    who this task serves (the user's own words)
  contract_line         the one line the wall shows — written cold
  main_belief           {"label": "..."} — the belief this traces to
  targets               [{label, evidence: {class: machine|file|manual,
                        command|path}}] — what counts as done
  profile               task profile name (coding|study|research|writing)
  research_fallback     optional {scope, sources[], max_minutes,
                        return_condition} — bounded allowance declared cold
  IF–THEN obstacle plan (optional group; present means complete):
    expected_obstacle / if_then_response / return_condition
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
    "identity_statement", "contract_line",
]

IF_THEN_FIELDS = ["expected_obstacle", "if_then_response",
                  "return_condition"]


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def validate(payload: dict) -> None:
    """Validate a daily payload; raise ContractError with the problems.

    The v0.5.0 schema: identity + contract line + main belief label +
    at least one target with an evidence class.
    """
    problems = []
    for field in REQUIRED_DAILY_FIELDS:
        if not _present(payload.get(field)):
            problems.append(f"missing field: {field}")

    belief = payload.get("main_belief")
    if not isinstance(belief, dict) or not _present(belief.get("label")):
        problems.append(
            "main_belief must be an object with a non-empty 'label' "
            "(e.g. {\"label\": \"compiler practice\"})")

    targets = payload.get("targets")
    if not isinstance(targets, list) or not targets:
        problems.append("targets must be a non-empty list")
    else:
        for i, target in enumerate(targets):
            if not isinstance(target, dict) \
                    or not _present(target.get("label")):
                problems.append(f"targets[{i}] needs a label")
            ev = target.get("evidence")
            if not isinstance(ev, dict) \
                    or ev.get("class") not in ("machine", "file", "manual"):
                problems.append(
                    f"targets[{i}].evidence needs a class of "
                    "machine|file|manual")

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

    if problems:
        raise ContractError("invalid contract: " + "; ".join(problems))


class ContractService:
    def __init__(self, db: Database, clock: Optional[Clock] = None):
        self.db = db
        self.clock = clock or RealClock()

    # -- validation ----------------------------------------------------------
    def validate(self, payload: dict) -> None:
        validate(payload)

    # -- create / seal --------------------------------------------------------
    def create_draft(self, kind: ContractKind, scope_date: str,
                     payload: dict) -> str:
        self.validate(payload)
        existing_draft = self.db.query_one(
            "SELECT id FROM contract WHERE kind=? AND scope_date=? "
            "AND state=?", (kind.value, scope_date,
                            ContractState.DRAFT.value))
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
            "payload_json": json.dumps(payload, default=str,
                                       ensure_ascii=False),
            "created_at": self.clock.iso(),
            "sealed_at": None,
            "supersedes": supersedes,
        })
        return new_id

    def seal(self, day: dict, payload: dict) -> dict:
        """Create + seal the daily contract for `day` (a day row or a
        date string). Refuses if a sealed contract already exists for
        the date (commitment is not double-written)."""
        date = day["date"] if isinstance(day, dict) else str(day)
        if self.for_day(date) is not None:
            raise ContractError(
                f"a sealed contract already exists for {date}; "
                "sealed contracts are immutable (principle 1)")
        contract_id = self.create_draft(ContractKind.DAILY, date, payload)
        self.db.update("contract", contract_id, {
            "state": ContractState.SEALED.value,
            "sealed_at": self.clock.iso(),
        })
        return self.get(contract_id)

    def seal_id(self, contract_id: str) -> dict:
        row = self.get(contract_id)
        if not row:
            raise ContractError("contract not found")
        if row["state"] != ContractState.DRAFT.value:
            raise ContractError(
                f"cannot seal contract in state {row['state']}")
        self.db.update("contract", contract_id, {
            "state": ContractState.SEALED.value,
            "sealed_at": self.clock.iso(),
        })
        return self.get(contract_id)

    # -- queries ----------------------------------------------------------------
    def get(self, contract_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM contract WHERE id=?", (contract_id,))
        if row:
            row["payload"] = json.loads(row.pop("payload_json"))
        return row

    def payload_of(self, contract: Optional[dict]) -> dict:
        if contract is None:
            return {}
        if "payload" in contract:
            return contract["payload"]
        return json.loads(contract["payload_json"])

    def for_day(self, date: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM contract WHERE kind='daily' AND scope_date=? "
            "AND state='SEALED'", (date,))
        if row:
            row["payload"] = json.loads(row.pop("payload_json"))
        return row

    def require_sealed_daily(self, local_date: _dt.date) -> dict:
        row = self.for_day(local_date.isoformat())
        if not row:
            raise ContractError(
                f"no sealed daily contract for {local_date.isoformat()}; "
                "run: dhriti ritual")
        return row
