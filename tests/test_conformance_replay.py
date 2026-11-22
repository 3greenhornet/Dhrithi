"""Tests for Normative Process Conformance Replay & Petri Net (§8.1–§8.3)."""

from datetime import datetime
import pytest
from dhriti.conform import (
    build_normative,
    stdlib_check,
    pm4py_check,
    render_conformance_md,
    NormativePetriNet,
)


def test_build_normative_stages():
    stages = build_normative({"start": "09:00", "day_close": "19:00", "end": "20:00"}, expected_evidence=2)
    assert len(stages) >= 5
    stage_names = [s["name"] for s in stages]
    assert "sealed_contract" in stage_names
    assert "session_active" in stage_names
    assert "evidence_submitted" in stage_names
    assert "deep_work" in stage_names
    assert "day_close" in stage_names


def test_petri_net_compliant_trace():
    stages = build_normative({})
    net = NormativePetriNet(stages)

    trace = [
        {"type": "contract_sealed", "ts": "2026-11-23T09:00:00Z"},
        {"type": "session_active", "ts": "2026-11-23T09:05:00Z"},
        {"type": "target_progress", "ts": "2026-11-23T10:00:00Z"},
        {"type": "evidence_submitted", "ts": "2026-11-23T18:00:00Z"},
        {"type": "day_close", "ts": "2026-11-23T19:00:00Z"},
    ]

    res = net.replay_trace(trace)
    assert res["compliant"] is True
    assert res["fitness"] >= 0.95
    assert res["missing"] == 0
    assert res["remaining"] == 0
    assert res["first_divergence"] is None


def test_petri_net_protocol_violations():
    stages = build_normative({})
    net = NormativePetriNet(stages)

    # 1. Skipping contract_sealed (missing prerequisite token)
    trace_skip_contract = [
        {"type": "session_active", "ts": "2026-11-23T09:05:00Z"},
        {"type": "evidence_submitted", "ts": "2026-11-23T18:00:00Z"},
        {"type": "day_close", "ts": "2026-11-23T19:00:00Z"},
    ]
    res1 = net.replay_trace(trace_skip_contract)
    assert res1["missing"] >= 1
    assert res1["first_divergence"] is not None

    # 2. Forbidden event occurring during session
    trace_forbidden = [
        {"type": "contract_sealed", "ts": "2026-11-23T09:00:00Z"},
        {"type": "session_active", "ts": "2026-11-23T09:05:00Z"},
        {"type": "browser_navigation", "category": "blocked_category", "ts": "2026-11-23T11:00:00Z"},
        {"type": "evidence_submitted", "ts": "2026-11-23T18:00:00Z"},
        {"type": "day_close", "ts": "2026-11-23T19:00:00Z"},
    ]
    res2 = net.replay_trace(trace_forbidden)
    assert res2["missing"] >= 1
    assert res2["fitness"] < 0.95
    assert res2["first_divergence"]["reason"].startswith("forbidden_event")


def test_stdlib_check_and_report_rendering():
    stages = build_normative({})
    compliant_trace = [
        {"type": "contract_sealed", "ts": "2026-11-23T09:00:00Z"},
        {"type": "session_active", "ts": "2026-11-23T09:05:00Z"},
        {"type": "evidence_submitted", "ts": "2026-11-23T18:00:00Z"},
        {"type": "day_close", "ts": "2026-11-23T19:00:00Z"},
    ]
    res = stdlib_check(compliant_trace, stages, evidence_count=1)
    assert res["conformant"] is True
    assert res["protocol_violation"] is False

    md = render_conformance_md(res)
    assert "## Conformance" in md
    assert "conformance: PASS" in md
    assert "petri_net_fitness: 1.0" in md
    assert "protocol_violation: NO" in md


def test_pm4py_honest_availability():
    res = pm4py_check([{"type": "contract_sealed"}])
    assert "available" in res
    assert "note" in res
