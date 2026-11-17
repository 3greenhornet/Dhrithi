"""Dhriti Guard Kit -- external blocker CLI probe (D-088).

Borrowed from the raw material's enforcement-tools table, verbatim facts:
  - Cold Turkey Blocker v4.9+ has a CLI: `-list-blocks`, `-add-block`,
    `-status`, `-password lock`. A locked block cannot be stopped or
    uninstalled during the block.
  - Known bypass: renaming the service executables
    (ServiceHub.Power / ServiceHub.Helper / CTMsgHostChrome|Edge|Firefox)
    breaks the lock. One-time purchase, Windows-first.

House shape: the external blocker is an ENFORCEMENT adapter in the
adapter-registry sense -- audit-gated before arming (same gate as the
FocusMe / Plucky / Focuser placeholders), evidence class
MACHINE_CHECKED (the CLI exit code is the evidence, never a claim),
and fail-visible: a compromised stack becomes an EVENT, not silence.

L-4 note: process names and exit codes are structure, not content.
D-005 note (test before building): this probe DELEGATES; Dhriti adds
only verification, never a second blocker.
"""

from __future__ import annotations

import subprocess
from typing import Callable, Optional

EVENT_STACK_BYPASS_RISK = "guard_stack_bypass_risk"

# The service image names that must be present for a Cold Turkey lock to
# mean what it says (from the public bypass record).
CT_EXPECTED_PROCESSES = (
    "ServiceHub.Power",
    "ServiceHub.Helper",
    "CTMsgHostChrome",
    "CTMsgHostEdge",
    "CTMsgHostFirefox",
)


def run_cli(cli_path: str, args: list[str],
            timeout: float = 8.0) -> dict:
    """Run an external blocker CLI. Never raises; returns
    {ok, exit_code, stdout, stderr, status: MACHINE_CHECKED|FAILED}."""
    try:
        proc = subprocess.run([cli_path, *args], capture_output=True,
                              text=True, timeout=timeout)
        return {"ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "")[:2000],
                "stderr": (proc.stderr or "")[:500],
                "status": "MACHINE_CHECKED"}
    except FileNotFoundError:
        return {"ok": False, "exit_code": None, "stdout": "",
                "stderr": f"executable not found: {cli_path}",
                "status": "FAILED"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": None, "stdout": "",
                "stderr": f"timed out after {timeout}s",
                "status": "FAILED"}
    except Exception as exc:  # honest unknown, not silent pass
        return {"ok": False, "exit_code": None, "stdout": "",
                "stderr": str(exc)[:200], "status": "FAILED"}


def cold_turkey_status(cli_path: str) -> dict:
    """`<ctcli> -status`. locked=True only when the tool SAYS so on a
    zero exit code. The fact is recorded either way -- cannot-control is
    an honest fact, per the AppLock precedent in the stack adapter."""
    res = run_cli(cli_path, ["-status"])
    out = (res.get("stdout") or "").lower()
    locked = res["ok"] and ("locked" in out and "unlocked" not in out)
    blocks = None
    if res["ok"]:
        lb = run_cli(cli_path, ["-list-blocks"])
        if lb["ok"]:
            blocks = [ln.strip() for ln in lb["stdout"].splitlines()
                      if ln.strip()]
    return {**res, "locked": locked, "blocks": blocks}


def list_processes(lister: Optional[Callable[[], str]] = None) -> list[str]:
    """Process image names, Windows-first via `tasklist /FO CSV /NH`.
    Injectable for tests (pass a callable returning the raw output)."""
    raw = lister() if lister else _tasklist()
    names = []
    for ln in (raw or "").splitlines():
        ln = ln.strip().strip('"')
        if not ln or ln.startswith("Image Name") or ln.startswith("="):
            continue
        # CSV row: "name","pid",...  OR plain first token fallback
        name = ln.split('","')[0].strip('"') if '","' in ln \
            else ln.split()[0]
        names.append(name)
    return names


def _tasklist() -> str:
    try:
        proc = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                              capture_output=True, text=True, timeout=10)
        return proc.stdout or ""
    except Exception:
        return ""


def rename_bypass_canary(process_names: list[str],
                         expected: tuple = CT_EXPECTED_PROCESSES,
                         locked_claimed: bool = True) -> dict:
    """If a block claims to be active but the service image names are
    missing from the process table, the stack is compromised (the
    documented rename bypass). Silence becomes an event (D-077 logic
    applied to the EXTERNAL stack)."""
    present = {n.lower() for n in process_names}
    missing = [n for n in expected if n.lower() not in present]
    risk = bool(locked_claimed and missing)
    out = {"locked_claimed": locked_claimed,
           "expected": list(expected),
           "missing": missing,
           "bypass_risk": risk}
    if risk:
        out["event"] = EVENT_STACK_BYPASS_RISK
        out["detail"] = ("block claims active but service images missing: "
                         + ", ".join(missing))
    return out


def audit_gate(cli_path: str = "",
               process_names: Optional[list[str]] = None) -> dict:
    """The arming-gate probe, adapter-registry shape (probe -> arm).
    Refuses to arm unless BOTH: the CLI answers with MACHINE_CHECKED
    evidence AND (if a block is claimed) no bypass signature. Mirrors
    the audit-gated enforcement placeholders (FocusMe/Plucky/Focuser):
    refuses to arm until the audit passes."""
    result: dict = {"adapter": "cold_turkey_cli", "armed": False,
                    "checks": {}}
    if not cli_path:
        result["checks"]["presence"] = "NOT_INSTALLED (honest placeholder)"
        return result
    status = cold_turkey_status(cli_path)
    result["checks"]["status"] = status["status"]
    result["checks"]["locked"] = status["locked"]
    if not status["ok"]:
        result["reason"] = status["stderr"] or "CLI probe failed"
        return result
    if process_names is None:
        process_names = list_processes()
    canary = rename_bypass_canary(process_names,
                                  locked_claimed=status["locked"])
    result["checks"]["bypass_canary"] = canary
    result["armed"] = not canary["bypass_risk"]
    if canary["bypass_risk"]:
        result["reason"] = canary["detail"]
        result["event"] = EVENT_STACK_BYPASS_RISK
    return result
