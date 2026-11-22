"""Tests for Agent-Free Capability Block & Placement Drills."""

import os
import tempfile
from pathlib import Path
import pytest

from dhriti.db import Database
from dhriti.ledger import Ledger
from dhriti.capability import CapabilityService, CapabilityError
from dhriti.contract import ContractService
from dhriti.timeutil import RealClock


@pytest.fixture
def temp_db_ledger():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    db = Database(Path(tmp.name))
    ledger = Ledger(db)
    yield db, ledger
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


def test_capability_list_drills(temp_db_ledger):
    db, ledger = temp_db_ledger
    svc = CapabilityService(db, ledger=ledger)
    drills = svc.list_drills()
    assert len(drills) >= 4
    drill_ids = [d["id"] for d in drills]
    assert "palindrome" in drill_ids
    assert "time_and_work" in drill_ids
    assert "two_sum" in drill_ids
    assert "speed_distance" in drill_ids


def test_capability_start_drill(temp_db_ledger, tmp_path):
    db, ledger = temp_db_ledger
    svc = CapabilityService(db, ledger=ledger, home=tmp_path)
    res = svc.start_drill("palindrome", out_dir=tmp_path / "drills", duration_min=30)
    assert res["ok"] is True
    assert res["drill_id"] == "palindrome"
    file_path = Path(res["file_path"])
    assert file_path.exists()
    content = file_path.read_text(encoding="utf-8")
    assert "def is_palindrome(val)" in content
    assert "30 minutes closed-world practice" in content

    # Check ledger recorded start
    ev = db.query_one("SELECT * FROM event WHERE event_type='capability_block_started'")
    assert ev is not None


def test_capability_verify_palindrome_success(temp_db_ledger, tmp_path):
    db, ledger = temp_db_ledger
    svc = CapabilityService(db, ledger=ledger, home=tmp_path)

    # Create dummy contract for today
    import datetime as dt
    today = dt.date.today().isoformat()
    cs = ContractService(db, RealClock())
    cs.seal(today, {
        "identity_statement": "I am a software engineer.",
        "contract_line": "Solve Basic DSA",
        "targets": [
            {"id": "t-pal", "label": "DSA Palindrome Drill", "kind": "capability", "evidence": {"class": "learning"}}
        ],
        "profile": "placement_prep",
        "main_belief": {"label": "Consistent deliberate practice clears technical interviews."},
        "main_belief_metric": "DSA problems solved & interview readiness",
        "main_belief_current_state": "Active practice",
        "substitute_activities": ["agent prompting", "passive tutorial watching"],
        "substitute_budget": "2 hours per day"
    })

    solution = """
def is_palindrome(val) -> bool:
    if isinstance(val, int):
        if val < 0:
            return False
        val = str(val)
    import re
    cleaned = re.sub(r'[^a-zA-Z0-9]', '', str(val)).lower()
    return cleaned == cleaned[::-1]
"""
    res = svc.verify_drill("palindrome", solution, scope_date=today)
    assert res["ok"] is True
    assert res["verified"] is True
    assert res["passed_tests"] == res["total_tests"]

    # Verify ledger and evidence table
    ev = db.query_one("SELECT * FROM event WHERE event_type='capability_drill_verified'")
    assert ev is not None

    claim_ev = db.query_one("SELECT * FROM event WHERE event_type='target_claimed'")
    assert claim_ev is not None

    evidence_row = db.query_one("SELECT * FROM evidence WHERE class='MACHINE_CHECKED'")
    assert evidence_row is not None
    import json
    ev_detail = json.loads(evidence_row["detail_json"])
    assert ev_detail["target_id"] == "t-pal"


def test_capability_verify_failure_honesty(temp_db_ledger, tmp_path):
    db, ledger = temp_db_ledger
    svc = CapabilityService(db, ledger=ledger, home=tmp_path)

    # Buggy solution
    buggy_code = """
def is_palindrome(val) -> bool:
    return True  # Fails for non-palindromes
"""
    res = svc.verify_drill("palindrome", buggy_code, accept_nonzero_exit=True)
    assert res["ok"] is True
    assert res["verified"] is False
    assert len(res["failures"]) > 0

    # L-2 Honesty: Attempt is recorded
    ev = db.query_one("SELECT * FROM event WHERE event_type='capability_drill_attempted'")
    assert ev is not None


def test_capability_verify_time_and_work(temp_db_ledger, tmp_path):
    db, ledger = temp_db_ledger
    svc = CapabilityService(db, ledger=ledger, home=tmp_path)

    solution = """
def remaining_work(a_days: float, b_days: float, worked_days: float) -> tuple[float, float]:
    rate = (1.0 / a_days) + (1.0 / b_days)
    done = min(1.0, rate * worked_days)
    rem = max(0.0, 1.0 - done)
    return round(done, 4), round(rem, 4)
"""
    res = svc.verify_drill("time_and_work", solution)
    assert res["ok"] is True
    assert res["verified"] is True
    assert res["passed_tests"] == res["total_tests"]


def test_capability_syntax_error_handled(temp_db_ledger, tmp_path):
    db, ledger = temp_db_ledger
    svc = CapabilityService(db, ledger=ledger, home=tmp_path)

    bad_syntax = "def is_palindrome(val) :::: invalid syntax"
    res = svc.verify_drill("palindrome", bad_syntax, accept_nonzero_exit=True)
    assert res["ok"] is True
    assert res["verified"] is False
    assert "Syntax or execution error" in res["message"]
