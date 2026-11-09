"""Proof-of-work: task-specific evidence, three honest classes (PDF 6,
dossier 7.3). Elapsed time is never proof. A failed attempt with a
documented error IS proof (meaningful progress, not completion).

  OBSERVED          adapter saw it happen (e.g. an IDE save event)
  SUBMITTED         the user handed something over (file, note)
  MACHINE_CHECKED   a local command ran / artifact verified — exit code,
                    file existence, hash — checked deterministically

Verdicts are computed against the contract's target evidence classes
(the `kind` names the target the proof is for). A manual claim is
kept for review but never accepted as machine proof.

v0.5.0: paths resolve against the CLI's CWD when relative (the Bug D
mistake — v0.6.0 Part 1 §4 fixes this to resolve against the
contract's workspace_dir, never CWD).
"""

import hashlib
import json
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from .db import Database
from .errors import EvidenceError
from .models import EvidenceClass, EvidenceVerdict
from .timeutil import Clock, RealClock

MACHINE_CHECK_TIMEOUT = 60  # seconds


class EvidenceService:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 home: Optional[Path] = None):
        self.db = db
        self.clock = clock or RealClock()
        self.home = Path(home) if home else Path.home() / ".dhriti"

    # -- submissions ---------------------------------------------------------
    def submit_file(self, session_id: str, kind: str, path: str,
                    note: str = "",
                    workspace: Optional[Path] = None) -> dict:
        target = Path(path).expanduser()
        if not target.is_absolute():
            # v0.5.0 behaviour (Bug D): relative to the process CWD.
            target = Path.cwd() / target
        if not target.is_file():
            return self._record(
                session_id, EvidenceClass.SUBMITTED, kind, "file",
                {"path": str(target),
                 "note": note,
                 "verdict_reason": f"file not found: {target}"},
                verdict=EvidenceVerdict.REJECTED,
                reason=f"file not found: {target}")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return self._record(
            session_id, EvidenceClass.SUBMITTED, kind, "file",
            {"path": str(target), "sha256": digest,
             "size_bytes": target.stat().st_size, "note": note},
            verdict=EvidenceVerdict.ACCEPTED,
            reason="file exists; sha256 recorded")

    def submit_manual(self, session_id: str, kind: str,
                      note: str) -> dict:
        if not (note or "").strip():
            raise EvidenceError("manual submission needs a note")
        return self._record(
            session_id, EvidenceClass.SUBMITTED, kind, "manual",
            {"note": note.strip()},
            verdict=EvidenceVerdict.REJECTED,
            reason="a claim is not proof; kept for review")

    def machine_check_command(self, session_id: str, kind: str,
                              command: str,
                              accept_nonzero_exit: bool = False,
                              workspace: Optional[Path] = None,
                              timeout_seconds: int = MACHINE_CHECK_TIMEOUT
                              ) -> dict:
        """Run a command locally; the exit code is the machine-checked
        fact. A NON-ZERO exit is still recorded and is ACCEPTED when
        the target declares a documented failure counts (PDF 6.1)."""
        if not command or not command.strip():
            raise EvidenceError("command required")
        try:
            proc = subprocess.run(
                shlex.split(command), capture_output=True, text=True,
                timeout=timeout_seconds,
                cwd=str(workspace) if workspace else None,
                shell=False)
            detail = {
                "command": command,
                "exit_code": proc.returncode,
                "stdout_tail": proc.stdout[-2000:],
                "stderr_tail": proc.stderr[-2000:],
            }
            exit_code = proc.returncode
        except FileNotFoundError as exc:
            detail = {"command": command, "exit_code": None,
                      "error": f"command not found: {exc}"}
            exit_code = None
        except subprocess.TimeoutExpired:
            detail = {"command": command, "exit_code": None,
                      "error": f"timeout after {timeout_seconds}s"}
            exit_code = None

        if exit_code is None:
            return self._record(
                session_id, EvidenceClass.MACHINE_CHECKED, kind,
                "command", detail,
                verdict=EvidenceVerdict.REJECTED,
                reason=detail["error"])
        if exit_code == 0 or accept_nonzero_exit:
            return self._record(
                session_id, EvidenceClass.MACHINE_CHECKED, kind,
                "command", detail,
                verdict=EvidenceVerdict.ACCEPTED,
                reason=(f"exit_code={exit_code}"
                        + (" (documented-failure proof accepted)"
                           if exit_code != 0 else "")))
        return self._record(
            session_id, EvidenceClass.MACHINE_CHECKED, kind, "command",
            detail,
            verdict=EvidenceVerdict.REJECTED,
            reason=f"exit_code={exit_code}")

    def record_observed(self, session_id: str, kind: str,
                        payload: dict) -> dict:
        """Used by observation adapters (e.g. an IDE save event)."""
        return self._record(session_id, EvidenceClass.OBSERVED, kind,
                            payload.get("subkind", "observed"), payload,
                            verdict=EvidenceVerdict.PENDING,
                            reason="observation recorded; awaiting "
                                   "confirmation")

    # -- verdicts --------------------------------------------------------------
    def _record(self, session_id: str, evidence_class: EvidenceClass,
                kind: str, subkind: str, detail: dict,
                verdict: EvidenceVerdict = EvidenceVerdict.PENDING,
                reason: str = "pending") -> dict:
        evidence_id = str(uuid.uuid4())
        self.db.insert("evidence", {
            "id": evidence_id,
            "session_id": session_id,
            "class": evidence_class.value,
            "kind": kind,
            "submitted_at": self.clock.iso(),
            "detail_json": json.dumps(detail, default=str),
            "verdict": verdict.value,
            "verdict_reason": reason,
            "checked_at": self.clock.iso(),
        })
        return self.get(evidence_id)

    def get(self, evidence_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM evidence WHERE id=?", (evidence_id,))
        if row:
            row["detail"] = json.loads(row.pop("detail_json"))
        return row

    def for_session(self, session_id: str) -> list:
        rows = self.db.query(
            "SELECT * FROM evidence WHERE session_id=? "
            "ORDER BY submitted_at", (session_id,))
        for row in rows:
            row["detail"] = json.loads(row.pop("detail_json"))
        return rows
