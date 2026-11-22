"""Tests for Placement Readiness Modules (Package L, I, J)."""

import os
import tempfile
from pathlib import Path
import pytest

from dhriti.db import Database
from dhriti.ledger import Ledger
from dhriti.project_defense import ProjectDefenseService
from dhriti.learning_proof import LearningProofService, LearningProofError
from dhriti.oa_simulator import OASimulator
from dhriti.vidura_corpus import ViduraCorpus
from dhriti.vidura_feed import ViduraFeedService


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


@pytest.fixture
def temp_vidura():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    corpus = ViduraCorpus(Path(tmp.name))
    yield corpus
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


def test_project_defense_ast_analysis():
    svc = ProjectDefenseService()
    # Test on an existing python file
    target = Path(__file__).parent.parent / "dhriti" / "topic_gate.py"
    res = svc.generate_defense_questions(target)
    
    assert res["ok"] is True
    assert len(res["questions"]) == 5
    categories = [q["category"] for q in res["questions"]]
    assert "Role & Architecture" in categories
    assert "Design Patterns & Trade-offs" in categories
    assert "Execution Path & Request Flow" in categories
    assert "Failure Modes & Edge Cases" in categories
    assert "Algorithmic Complexity & Scaling" in categories


def test_project_defense_save_to_vidura(temp_vidura):
    svc = ProjectDefenseService()
    target = Path(__file__).parent.parent / "dhriti" / "pivot.py"
    res = svc.generate_defense_questions(target)
    
    ids = svc.save_to_vidura(temp_vidura, target, res["questions"])
    assert len(ids) == 5
    
    # Verify items are in Vidura
    items = temp_vidura.search("Project Defense")
    assert len(items) >= 5


def test_learning_proof_word_count_enforcement(temp_db_ledger):
    db, ledger = temp_db_ledger
    svc = LearningProofService(db, ledger=ledger)

    # Rejection 1: Short synthesis
    with pytest.raises(LearningProofError) as exc_info:
        svc.verify_synthesis("Just watched a video on binary trees and it was good.")
    assert "at least 50 words" in str(exc_info.value)

    # Rejection 2: Repeated spam
    with pytest.raises(LearningProofError) as exc_info:
        svc.verify_synthesis("tree " * 55)
    assert "lexical diversity" in str(exc_info.value)

    # Valid synthesis: 50+ diverse words
    valid_text = (
        "In this module on Binary Search Trees, we analyzed the structural properties "
        "and recursion invariants governing node insertion and deletion. In a balanced BST, "
        "search time complexity is strictly bounded by O(log N), whereas an unbalanced degenerate "
        "tree exhibits O(N) linear degradation. We traced the in-order predecessor replacement "
        "pattern for two-child node deletions and discussed rebalancing heuristics like AVL rotations."
    )
    meta = svc.verify_synthesis(valid_text)
    assert meta["valid"] is True
    assert meta["word_count"] >= 50
    assert len(meta["sha256"]) == 64


def test_learning_proof_claim_target(temp_db_ledger):
    db, ledger = temp_db_ledger
    svc = LearningProofService(db, ledger=ledger)

    import datetime as dt
    today = dt.date.today().isoformat()

    # Create dummy contract with a target
    from dhriti.contract import ContractService
    from dhriti.timeutil import RealClock
    cs = ContractService(db, RealClock())
    payload = {
        "identity_statement": "I am a sovereign engineer.",
        "contract_line": "Master Tree Traversals",
        "targets": [
            {"id": "t-1", "label": "Binary Search Tree Deletion Algorithm", "kind": "learning", "evidence": {"class": "learning"}}
        ],
        "profile": "study",
        "main_belief": {"label": "Consistent deliberate study clears assessments."},
        "main_belief_metric": "DSA problems solved & interview readiness",
        "main_belief_current_state": "Active preparation",
        "substitute_activities": ["reading about trees", "passive browsing"],
        "substitute_budget": "2 hours per week"
    }
    cs.seal(today, payload)

    valid_text = (
        "In this module on Binary Search Trees, we analyzed the structural properties "
        "and recursion invariants governing node insertion and deletion. In a balanced BST, "
        "search time complexity is strictly bounded by O(log N), whereas an unbalanced degenerate "
        "tree exhibits O(N) linear degradation. We traced the in-order predecessor replacement "
        "pattern for two-child node deletions and discussed rebalancing heuristics like AVL rotations."
    )

    res = svc.claim_with_proof("t-1", valid_text)
    assert res["ok"] is True
    assert res["target_id"] == "t-1"

    assert len(res["proof_hash"]) == 64
    # Verify ledger/event audit table recorded the verified proof
    ev_row = db.query_one("SELECT * FROM event WHERE event_type='learning_proof_verified'")
    assert ev_row is not None
    import json
    ev_payload = json.loads(ev_row["observed_payload"])
    assert ev_payload["target_id"] == "t-1"
    assert "proof_hash" in ev_payload


def test_oa_simulator(temp_db_ledger):
    db, ledger = temp_db_ledger
    sim = OASimulator(db, ledger=ledger)

    drill = sim.get_daily_drill()
    assert len(drill) == 10
    assert "answer" not in drill[0]  # Answers stripped for student

    # Submit answers
    submission = {
        "oa-quant-1": "B",
        "oa-quant-2": "B",
        "oa-logic-1": "B",
        "oa-cs-1": "C"
    }
    result = sim.submit_drill(submission)
    assert result["ok"] is True
    assert result["total"] == 10
    assert result["correct"] == 4
    assert result["score_pct"] == 40
    assert len(result["review"]) == 10


def test_vidura_deduplication(temp_vidura):
    # Add first time
    id1 = temp_vidura.add_item(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Never Gonna Give You Up",
        source="youtube",
        external_id="dQw4w9WgXcQ"
    )

    # Add second time with same external_id
    id2 = temp_vidura.add_item(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Never Gonna Give You Up (Duplicate)",
        source="youtube",
        external_id="dQw4w9WgXcQ"
    )

    assert id1 == id2  # Deduplicated!
