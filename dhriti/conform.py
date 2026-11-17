"""Dhriti Guard Kit -- conformance view (D-083): the contract as a normative
process model.

PM4Py is already in the stack (offline, D-010) but was aimed at nothing.
This module aims it at the artefact that makes Dhriti Dhriti: the sealed
contract. Two paths:

1. stdlib path (always available): declared-day vs observed-day deviation
   report -- required events missing, navigation into blocked categories
   inside a deep-work stage, passes expired UNANSWERED, first divergence
   timestamp.
2. PM4Py path (optional, lazy import, offline): token replay of the day's
   event log against the normative model. ImportError is caught and
   reported honestly -- never silently skipped.

Integration point: aftermath day report gains a "Conformance" block.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


# --------------------------------------------------------------------------
# Normative model from the contract + day window config
# --------------------------------------------------------------------------

def build_normative(day_window: dict, contract_line: str = "",
                    expected_evidence: int = 1) -> list[dict]:
    """day_window: {"start": "HH:MM", "day_close": "HH:MM", "end": "HH:MM"}
    Returns ordered stages with required/forbidden event predicates."""
    return [
        {"name": "sealed_contract",
         "require": ("contract_sealed",), "forbid": (),
         "note": contract_line or "contract present"},
        {"name": "session_active",
         "require": ("session_active",), "forbid": (),
         "note": f"evidence events >= {expected_evidence}"},
        {"name": "deep_work",
         "require": (), "forbid": ("browser_navigation:blocked_category",),
         "note": "no blocked-category navigation while ACTIVE"},
        {"name": "pass_closure",
         "require": (), "forbid": ("research_pass_expired",),
         "note": "no pass expires UNANSWERED"},
        {"name": "day_close",
         "require": (), "forbid": (),
         "note": "release at window_end (L-5)"},
    ]


# --------------------------------------------------------------------------
# stdlib conformance check
# --------------------------------------------------------------------------

def stdlib_check(events: list[dict], stages: list[dict],
                 evidence_count: int = 0) -> dict:
    """events: [{"type": "session_active", "ts": ...}, ...] for the day.
    Deviations are facts, not judgments (L-7): no softening phrases."""
    types = [e.get("type", "") for e in events]
    deviations = []

    for st in stages:
        for req in st["require"]:
            if req not in types:
                deviations.append({"kind": "missing_required",
                                   "stage": st["name"], "detail": req})
        for fb in st["forbid"]:
            if ":" in fb:
                base, sub = fb.split(":", 1)
                hit = [e for e in events if e.get("type") == base
                       and e.get("category") == sub]
            else:
                hit = [e for e in events if e.get("type") == fb]
            for e in hit:
                deviations.append({"kind": "forbidden_occurred",
                                   "stage": st["name"],
                                   "detail": fb, "ts": e.get("ts")})

    if stages[1]["name"] == "session_active" and \
            evidence_count < expected_evidence_of(stages):
        deviations.append({"kind": "evidence_shortfall",
                           "stage": "session_active",
                           "detail": f"{evidence_count} evidence events"})

    # First divergence: first forbidden or first guard hold after session
    first = None
    for e in events:
        if str(e.get("type", "")).startswith(("guard_", "break_")):
            first = e
            break
    return {"deviations": deviations,
            "first_divergence": first,
            "conformant": not deviations}


def expected_evidence_of(stages: list[dict]) -> int:
    for st in stages:
        if st["name"] == "session_active":
            try:
                return int(str(st["note"]).split(">=")[1].strip())
            except Exception:
                return 1
    return 1


# --------------------------------------------------------------------------
# PM4Py path (optional, offline, lazy)
# --------------------------------------------------------------------------

def pm4py_check(events: list[dict]) -> Optional[dict]:
    """Token replay of the day's log. Requires `pip install pm4py` (already
    named in the stack, offline per D-010). Returns None + note if absent."""
    try:
        import pm4py  # noqa: delay import on purpose
    except ImportError:
        return {"available": False,
                "note": "pm4py not installed; stdlib path used (honest)"}
    log = [{"case:concept:name": "day",
            "concept:name": e.get("type", "unknown"),
            "time:timestamp": e.get("ts") or datetime.min}
           for e in events]
    try:
        net, im, fm = pm4py.discover_process_tree_inductive(log)
        replay = pm4py.conformance_diagnostics_token_based_replay(
            log, net, im, fm)
        return {"available": True, "replay": replay,
                "note": "discovered model replay; read as structure, "
                        "not truth"}
    except Exception as exc:
        return {"available": False, "note": f"pm4py replay failed: {exc}"}


# --------------------------------------------------------------------------
# Report block
# --------------------------------------------------------------------------

def render_conformance_md(result: dict) -> str:
    lines = ["## Conformance", ""]
    lines.append(f"- conformance: "
                 f"{'PASS' if result.get('conformant') else 'DEVIATIONS'}")
    for d in result.get("deviations", []):
        ts = f" @ {d['ts']}" if d.get("ts") else ""
        lines.append(f"  - [{d['kind']}] {d['stage']}: {d['detail']}{ts}")
    fd = result.get("first_divergence")
    if fd:
        lines.append(f"- first divergence: {fd.get('type')} @ {fd.get('ts')}")
    pm = result.get("pm4py")
    if pm:
        lines.append(f"- pm4py: {'replayed' if pm.get('available') else pm.get('note')}")
    return "\n".join(lines)
