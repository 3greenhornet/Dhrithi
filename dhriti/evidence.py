"""Proof-of-work: task-specific evidence, three honest classes (PDF 6,
dossier 7.3). Elapsed time is never proof. A failed attempt with a
documented error IS proof (meaningful progress, not completion).

  OBSERVED          adapter saw it happen (e.g. an IDE save event)
  SUBMITTED         the user handed something over (file, note)
  MACHINE_CHECKED   a local command ran / artifact verified — exit code,
                    file existence, hash — checked deterministically

Verdicts are computed against the session's contract evidence spec. The
optional screenshot -> vision-model workflow is deliberately DISABLED in
v1: it needs an API key / model download, so it raises DisabledFeature
with a pointer to integrations/vision-proof/SETUP.md (a well-made
placeholder, never a silent fake).
"""

import hashlib
import json
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from .db import Database
from .errors import DisabledFeature, EvidenceError
from .models import EvidenceClass, EvidenceVerdict
from .timeutil import Clock, RealClock

MACHINE_CHECK_TIMEOUT = 30  # seconds


class EvidenceService:
    def __init__(self, db: Database, clock: Optional[Clock] = None):
        self.db = db
        self.clock = clock or RealClock()

    # -- submissions ---------------------------------------------------------
    def submit_file(self, session_id: str, path: str,
                    note: str = "") -> dict:
        target = Path(path).expanduser()
        if not target.is_file():
            raise EvidenceError(f"file not found: {path}")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return self._record(
            session_id, EvidenceClass.SUBMITTED, "file",
            {"path": str(target), "sha256": digest,
             "size_bytes": target.stat().st_size, "note": note})

    def submit_manual(self, session_id: str, note: str) -> dict:
        if not (note or "").strip():
            raise EvidenceError("manual submission needs a note")
        return self._record(
            session_id, EvidenceClass.SUBMITTED, "manual",
            {"note": note.strip()})

    def machine_check_command(self, session_id: str, command: str,
                              cwd: Optional[str] = None) -> dict:
        """Run a command locally; the exit code is the machine-checked fact.

        A NON-ZERO exit is still recorded and can still be ACCEPTED when
        the contract's evidence spec says a documented failure counts
        (PDF 6.1: a documented failed attempt is proof).
        """
        if not command or not command.strip():
            raise EvidenceError("command required")
        try:
            proc = subprocess.run(
                shlex.split(command), capture_output=True, text=True,
                timeout=MACHINE_CHECK_TIMEOUT, cwd=cwd, shell=False)
            detail = {
                "command": command,
                "exit_code": proc.returncode,
                "stdout_tail": proc.stdout[-2000:],
                "stderr_tail": proc.stderr[-2000:],
            }
        except FileNotFoundError as exc:
            detail = {"command": command, "exit_code": None,
                      "error": f"command not found: {exc}"}
        except subprocess.TimeoutExpired:
            detail = {"command": command, "exit_code": None,
                      "error": f"timeout after {MACHINE_CHECK_TIMEOUT}s"}
        return self._record(
            session_id, EvidenceClass.MACHINE_CHECKED, "command", detail)

    def record_observed(self, session_id: str, kind: str,
                        payload: dict) -> dict:
        """Used by observation adapters (e.g. an IDE save event)."""
        return self._record(session_id, EvidenceClass.OBSERVED, kind, payload)

    def submit_screenshot(self, session_id: str, path: str) -> dict:
        raise DisabledFeature(
            "screenshot -> vision-model proof is disabled in v1: it needs a "
            "vision provider (API key or local model download). See "
            "integrations/vision-proof/SETUP.md. Until configured, use "
            "submit_file / machine_check_command instead.")

    # -- verdicts --------------------------------------------------------------
    def _record(self, session_id: str, evidence_class: EvidenceClass,
                kind: str, detail: dict) -> dict:
        evidence_id = str(uuid.uuid4())
        self.db.insert("evidence", {
            "id": evidence_id,
            "session_id": session_id,
            "class": evidence_class.value,
            "kind": kind,
            "submitted_at": self.clock.iso(),
            "detail_json": json.dumps(detail, default=str),
            "verdict": EvidenceVerdict.PENDING.value,
            "verdict_reason": None,
            "checked_at": None,
        })
        row = self.get(evidence_id)
        return self.evaluate(row)

    def get(self, evidence_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM evidence WHERE id=?", (evidence_id,))
        if row:
            row["detail"] = json.loads(row.pop("detail_json"))
        return row

    def evaluate(self, evidence: dict) -> dict:
        """Deterministic verdict against the session's evidence spec.

        Defaults (when the spec is empty or generic):
          command  -> ACCEPTED if exit_code == 0
          file     -> ACCEPTED if it exists (hash recorded)
          manual   -> REJECTED for session success (a claim is not proof),
                      but kept in the ledger for the review
          observed -> PENDING (observations accumulate; the daemon accepts
                      a session only on explicit user confirmation)
        If the spec declares kinds (e.g. [{"kind":"command"}]), the
        evidence kind must match. A spec may declare
        {"accept_nonzero_exit": true} to honor documented-failure proof.
        """
        session = self.db.query_one(
            "SELECT * FROM session WHERE id=?",
            (evidence["session_id"],))
        spec = []
        try:
            spec = json.loads(session.get("evidence_spec") or "[]")
        except Exception:
            spec = []
        accept_nonzero = any(
            s.get("accept_nonzero_exit") for s in spec if isinstance(s, dict))

        kind = evidence["kind"]
        detail = evidence.get("detail", {})
        if spec and isinstance(spec, list):
            wanted = {s.get("kind") for s in spec
                      if isinstance(s, dict) and s.get("kind")}
            if wanted and kind not in wanted:
                verdict, reason = (EvidenceVerdict.REJECTED,
                                   f"kind '{kind}' not in declared evidence "
                                   f"spec {sorted(wanted)}")
            elif kind == "command" and detail.get("exit_code") is not None:
                if detail["exit_code"] == 0 or accept_nonzero:
                    verdict = EvidenceVerdict.ACCEPTED
                    reason = (f"exit_code={detail['exit_code']}"
                              + (" (documented-failure proof accepted)"
                                 if detail["exit_code"] != 0 else ""))
                else:
                    verdict, reason = (EvidenceVerdict.REJECTED,
                                       f"exit_code={detail['exit_code']}")
            elif kind == "file":
                verdict = EvidenceVerdict.ACCEPTED
                reason = "file exists; sha256 recorded"
            elif kind == "manual":
                verdict, reason = (EvidenceVerdict.REJECTED,
                                   "a claim is not proof; kept for review")
            elif kind == "observed":
                verdict, reason = (EvidenceVerdict.PENDING,
                                   "observation recorded; awaiting "
                                   "confirmation")
            else:
                verdict, reason = (EvidenceVerdict.PENDING,
                                   "no rule for this kind")
        else:
            # No spec: fall back to the same defaults.
            if kind == "command" and detail.get("exit_code") == 0:
                verdict, reason = EvidenceVerdict.ACCEPTED, "exit_code=0"
            elif kind == "file":
                verdict, reason = EvidenceVerdict.ACCEPTED, "file exists"
            elif kind == "command" and accept_nonzero:
                verdict, reason = EvidenceVerdict.ACCEPTED, "documented failure"
            else:
                verdict, reason = (EvidenceVerdict.PENDING,
                                   "no declared spec; awaiting review")

        self.db.update("evidence", evidence["id"], {
            "verdict": verdict.value,
            "verdict_reason": reason,
            "checked_at": self.clock.iso(),
        })
        updated = self.get(evidence["id"])
        return updated

    def for_session(self, session_id: str) -> list:
        rows = self.db.query(
            "SELECT * FROM evidence WHERE session_id=? "
            "ORDER BY submitted_at", (session_id,))
        for row in rows:
            row["detail"] = json.loads(row.pop("detail_json"))
        return rows
