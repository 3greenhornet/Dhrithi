"""Contracts: the cold-state ritual's output (PDF section 5, dossier 2.2,
plan v2.0 Artifact 1 / D-030).

A contract is written in a cold state, sealed, and becomes immutable.
Drafts may be superseded by newer drafts until sealing; sealed contracts
are never edited or deleted (DB triggers enforce, hash chain records).

Payload schema (docs/SCHEMAS.md):

  identity_statement    who this task serves (the user's own words)
  contract_line         the one line the wall shows — written cold
  main_belief           {"label": "..."} — the belief this traces to

D-030 group (v0.6.0 restoration, Part 1 §5 — required as a unit;
  every task traces to the main belief; the main belief is a filter,
  not a slogan):
  main_belief_metric        what would prove the belief is becoming real
  main_belief_current_state the honest assessment today ("I am failing
                            the course") — the failure state is the signal
  substitute_activities     known substitutes (guitar, multiplayer games)
  substitute_budget         time allowed for substitutes while healthy

  targets               [{label, evidence: {class: machine|file|manual,
                        command|path}}] — what counts as done
  profile               task profile name (coding|study|research|writing)
  workspace_dir         optional; absolute path to the directory the
                        evidence layer resolves relative paths against
                        (validated at seal time — Bug D, v0.6.0)
  declared_unknowns     optional; [{topic, current_state:
                        unknown|partial}] — mechanism 4: uncertainty
                        declared explicitly instead of false certainty
  research_fallback     optional {scope, sources[], max_minutes,
                        return_condition} — bounded allowance declared cold
  IF–THEN obstacle plan (optional group; present means complete):
    expected_obstacle / if_then_response / return_condition
"""

import datetime as _dt
import json
import uuid
from pathlib import Path
from typing import Optional

from .db import Database
from .errors import ContractError
from .models import ContractKind, ContractState
from .timeutil import Clock, RealClock

REQUIRED_DAILY_FIELDS = [
    "identity_statement", "contract_line",
]

# D-030 (v0.6.0 restoration): the four fields that complete the
# main-belief group. main_belief itself is the anchor; these are the
# exchange rate.
MAIN_BELIEF_FIELDS = [
    "main_belief_metric",
    "main_belief_current_state",
    "substitute_activities",
    "substitute_budget",
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

    # D-030 group (v0.6.0 restoration, Part 1 §5): required as a unit.
    missing_belief = [f for f in MAIN_BELIEF_FIELDS
                      if not _present(payload.get(f))]
    if missing_belief:
        problems.append(
            "main-belief group incomplete (D-030), missing: "
            + ", ".join(missing_belief))
    else:
        if not isinstance(payload.get("substitute_activities"), list) \
                or not payload["substitute_activities"]:
            problems.append(
                "substitute_activities must be a non-empty list of "
                "strings")
        if not isinstance(payload.get("substitute_budget"), str) \
                or not payload["substitute_budget"].strip():
            problems.append(
                "substitute_budget must be a non-empty string "
                "(e.g. '3 hours per week')")

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
                    or ev.get("class") not in ("machine", "file", "manual", "observed", "learning"):
                problems.append(
                    f"targets[{i}].evidence needs a class of "
                    "machine|file|manual|observed|learning")

    # Bug D (v0.6.0 Part 1 §4.1): workspace_dir is optional; when
    # present it must be an absolute path to a directory that exists
    # at seal time — the evidence layer resolves relative paths
    # against it, and a relative workspace would resolve against
    # whatever the shell happened to be in.
    workspace = payload.get("workspace_dir")
    if workspace is not None:
        if not isinstance(workspace, str):
            problems.append("workspace_dir must be a string")
        else:
            wp = Path(workspace).expanduser()
            if not wp.is_absolute():
                problems.append(
                    f"workspace_dir must be absolute (got {workspace!r}); "
                    "the evidence layer resolves relative paths against "
                    "it, and a relative workspace would resolve against "
                    "whatever the shell happened to be in")
            elif not wp.is_dir():
                problems.append(
                    f"workspace_dir {wp} does not exist or is not a "
                    "directory (checked at seal time; a workspace that "
                    "doesn't exist cannot carry evidence)")

    # Mechanism 4 (v0.6.0 Part 2 §2.2): declared uncertainty instead
    # of false certainty.
    unknowns = payload.get("declared_unknowns", [])
    if unknowns and not isinstance(unknowns, list):
        problems.append("declared_unknowns must be a list")

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
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

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

    # -- revision (mechanism 2: the false-positive correction path) ------
    def revise(self, contract_id: str, patch: dict,
               reason: str) -> dict:
        """Cold-state revision of a DRAFT. Sealed contracts are
        immutable (principle 1); the revision event is the record.
        The system does not author the contract's fields; it only
        re-validates what the operator rewrote."""
        row = self.get(contract_id)
        if row is None:
            raise ContractError(f"no such contract {contract_id}")
        if row["state"] == "SEALED":
            raise ContractError(
                "sealed contracts are immutable (principle 1); "
                "write a new draft with `dhriti contract write`")
        payload = dict(row["payload"])
        payload.update(patch)
        self.validate(payload)
        self.db.update("contract", contract_id, {
            "payload_json": json.dumps(payload, ensure_ascii=False,
                                       default=str)})
        self.ledger.record(
            "contract_revised",
            case_id=f"day-{row['scope_date']}",
            observed={"contract_id": contract_id,
                      "day": row["scope_date"],
                      "patched_fields": list(patch.keys()),
                      "reason": reason},
            action_taken="draft revised; re-validation passed")
        return self.get(contract_id)

    def get_history_of_field(self, field_name: str) -> list:
        """The sequence of a payload field's values across every sealed
        contract, oldest first (identity-revision; used for
        main_belief_current_state)."""
        history = []
        for row in self.db.query(
                "SELECT scope_date, payload_json FROM contract "
                "WHERE kind='daily' AND state='SEALED' "
                "ORDER BY scope_date"):
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                continue
            if _present(payload.get(field_name)):
                history.append({"date": row["scope_date"],
                                "value": payload[field_name]})
        return history

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
