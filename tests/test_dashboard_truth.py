"""Tests for Dashboard Truth and Honest Bridge Endpoints (Package M)."""

import json
import os
import tempfile
import urllib.request
from pathlib import Path

from dhriti.bridge import BridgeServer, BridgeState
from dhriti.db import Database
from dhriti.ledger import Ledger
from dhriti.contract import ContractService
from dhriti.timeutil import RealClock


def test_dashboard_truth_bridge_endpoints():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    db = Database(Path(tmp.name))
    ledger = Ledger(db)
    state = BridgeState()
    token = "test-token-truth"

    server = BridgeServer("127.0.0.1", 0, token, state, ledger=ledger)
    server.start()

    try:
        base_url = f"http://127.0.0.1:{server.port_bound}"

        # 1. Test GET /stats/streak (Initially 0)
        with urllib.request.urlopen(f"{base_url}/stats/streak") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert data.get("streak") == 0

        # Seal a contract for today and verify streak updates
        import datetime as dt
        today = dt.date.today().isoformat()
        cs = ContractService(db, RealClock())
        payload = {
            "identity_statement": "I am a sovereign engineer.",
            "contract_line": "Placement Practice",
            "targets": [
                {"id": "t-1", "label": "DSA Drill", "kind": "learning", "evidence": {"class": "learning"}}
            ],
            "profile": "study",
            "main_belief": {"label": "Consistent deliberate study clears assessments."},
            "main_belief_metric": "DSA problems solved & interview readiness",
            "main_belief_current_state": "Active preparation",
            "substitute_activities": ["Passive browsing", "random videos"],
            "substitute_budget": "1 hour per week"
        }
        cs.seal(today, payload)

        with urllib.request.urlopen(f"{base_url}/stats/streak") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("streak") == 1

        # 2. Test GET /stats/stage_ratio
        with urllib.request.urlopen(f"{base_url}/stats/stage_ratio") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert "stage_ratio" in data

        # 3. Test POST /lockdown/engage
        req = urllib.request.Request(
            f"{base_url}/lockdown/engage",
            data=b'{"reason": "testing lockdown"}',
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert data.get("locked") is True

        # 4. Test GET /ledger/recent (Should now contain the lockdown event)
        with urllib.request.urlopen(f"{base_url}/ledger/recent?limit=10") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert "events" in data
            assert len(data["events"]) >= 1

        # 5. Test POST /targets/verify_recall
        valid_synthesis = (
            "We reviewed dynamic programming memoization techniques for the 0-1 knapsack problem. "
            "The recurrence relation considers two choices for each item: either exclude it or include "
            "it if remaining capacity permits. We visualized the 2D state matrix of size N times W, "
            "analyzed the pseudo-polynomial time complexity O(N*W), and optimized auxiliary space to "
            "a single 1D array by traversing capacities in reverse order."
        )
        body = json.dumps({"target_id": "t-1", "synthesis": valid_synthesis}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/targets/verify_recall",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert data.get("target_id") == "t-1"

        # 6. Test GET /api/oa/drill
        with urllib.request.urlopen(f"{base_url}/api/oa/drill") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert len(data.get("drill", [])) == 10

        # 7. Test POST /api/oa/submit
        sub_body = json.dumps({"answers": {"oa-quant-1": "B", "oa-logic-1": "B"}}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/oa/submit",
            data=sub_body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert data.get("total") == 10

        # 8. Test POST /api/defense/generate
        target_file = str(Path(__file__).parent.parent / "dhriti" / "stats.py")
        def_body = json.dumps({"file": target_file, "save_to_vidura": False}).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/defense/generate",
            data=def_body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("ok") is True
            assert len(data.get("questions", [])) == 5

    finally:
        server.stop()
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
