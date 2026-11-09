"""Test plumbing: shared fixtures for a fully simulated environment."""

import datetime as _dt
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhriti.bootcamp import BootcampService
from dhriti.break_glass import BreakGlassService
from dhriti.constants import DEFAULT_CONFIG, load_config
from dhriti.contract import ContractService
from dhriti.daemon import Daemon
from dhriti.db import Database
from dhriti.day_window import DayService
from dhriti.evidence import EvidenceService
from dhriti.ledger import Ledger
from dhriti.models import ContractKind
from dhriti.policy import PolicyEngine
from dhriti.research_pass import ResearchService
from dhriti.session import SessionService
from dhriti.timeutil import SimulatedClock, local_tz

# A fixed, boring Monday in the user's timezone (Asia/Kolkata = UTC+5:30).
# 2026-11-02 04:30 UTC == 2026-11-02 10:00 local == exactly window start.
LOCAL_TZ = "Asia/Kolkata"
CLOCK_START = _dt.datetime(2026, 11, 2, 4, 30, tzinfo=_dt.timezone.utc)


def make_config(**overrides) -> dict:
    import json
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["timezone"] = LOCAL_TZ
    cfg["bridge"]["port"] = 0  # ephemeral port for tests
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def daily_payload(task="reverse the array in Java"):
    return {
        "mandatory_task": task,
        "smallest_next_action": "open ReverseArray.java and write the "
                                "swap loop header",
        "evidence": [{"kind": "command"}],
        "targets": [{"kind": "session_count", "count": 1}],
        "allowed_tools": [],
        "blocked_tools": [],
        "core_belief": "I am becoming a backend engineer",
        "identity_statement": "I am someone who ships code daily",
        "work_mode": "closed_world",
        # D-030: the main belief and its exchange rate with substitutes.
        "main_belief": "I want to be a software engineer",
        "main_belief_metric": "pass the CS course; ship a working project",
        "main_belief_current_state": "I am behind on the course and "
                                      "avoiding the compiler",
        "substitute_activities": ["guitar practice", "multiplayer games"],
        "substitute_budget": "3 hours per week",
        # IF–THEN obstacle plan (optional group; complete when present).
        "expected_obstacle": "the reverse loop throws IndexOutOfBounds",
        "if_then_response": "check the loop bounds against the array "
                            "length before the swap",
        "return_condition": "rerun the test after the fix",
        "emergency_policy": "medical, family, or the laptop is on fire",
    }


class DhritiTestCase(unittest.TestCase):
    """Temp home + simulated clock + wired services."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dhriti-test-")
        self.home = Path(self.tmp)
        self.clock = SimulatedClock(CLOCK_START)
        self.config = make_config()
        self.db = Database(self.home / "dhriti.sqlite3")
        self.ledger = Ledger(self.db, self.clock, anchor_interval=5)
        self.contracts = ContractService(self.db, self.clock)
        self.days = DayService(self.db, self.config, self.clock)
        self.sessions = SessionService(self.db, self.clock)
        self.evidence = EvidenceService(self.db, self.clock)
        self.research = ResearchService(self.db, self.config, self.clock)
        self.bootcamp = BootcampService(self.db, self.config, self.clock)
        self.break_glass = BreakGlassService(
            self.db, self.config, self.clock, self.ledger)
        self.policy = PolicyEngine(self.db, self.clock)
        self.today = self.clock.now_utc().astimezone(
            local_tz(LOCAL_TZ)).date()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ------------------------------------------------------------
    def seal_today(self, payload=None):
        payload = payload or daily_payload()
        cid = self.contracts.create_draft(
            ContractKind.DAILY, self.today.isoformat(), payload)
        return self.contracts.seal(cid)

    def make_daemon(self, **config_overrides) -> Daemon:
        import json
        cfg = json.loads(json.dumps(self.config))
        for key, value in config_overrides.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
        # share the same DB file: close ours, let the daemon own it
        self.db.close()
        daemon = Daemon(self.home, config=cfg, clock=self.clock,
                        tick_seconds=0.0)
        self.db = daemon.db  # keep a handle for assertions
        return daemon


if __name__ == "__main__":
    unittest.main()
