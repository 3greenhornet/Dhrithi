"""Test plumbing: shared fixtures for a fully simulated environment
(v0.5.0 shape — the Context-era services)."""

import datetime as _dt
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhriti.aftermath import AftermathService
from dhriti.bootcamp import BootcampService
from dhriti.break_glass import BreakGlassService
from dhriti.constants import DEFAULT_CONFIG, load_config
from dhriti.contract import ContractService
from dhriti.daemon import Daemon
from dhriti.db import Database
from dhriti.day_window import DayService
from dhriti.evidence import EvidenceService
from dhriti.ledger import Ledger
from dhriti.leisure import LeisureService
from dhriti.models import SessionState
from dhriti.policy import PolicyEngine
from dhriti.research_pass import ResearchService
from dhriti.review import ColdReviewService, ParkingLotService
from dhriti.session import SessionService
from dhriti.timeutil import SimulatedClock, local_tz
from dhriti.vidura import ViduraService

# A fixed, boring Monday in the user's timezone (Asia/Kolkata = UTC+5:30).
# 2026-11-02 04:30 UTC == 2026-11-02 10:00 local == exactly window start.
LOCAL_TZ = "Asia/Kolkata"
CLOCK_START = _dt.datetime(2026, 11, 2, 4, 30, tzinfo=_dt.timezone.utc)


def make_config(**overrides) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["timezone"] = LOCAL_TZ
    cfg["bridge"]["port"] = 0  # ephemeral port for tests
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def daily_payload() -> dict:
    """The v0.5.0 contract shape: identity, contract line, main belief
    label, targets with evidence classes. (v0.6.0 Part 1 §5 restores
    the full five-field D-030 group; the fixture grows there.)"""
    return {
        "identity_statement": (
            "I am the person who writes the compiler, not the person "
            "who reads about compilers."),
        "contract_line": "reverse the array in Java, in place",
        "main_belief": {"label": "compiler practice"},
        "profile": "coding",
        "targets": [
            {"label": "reversal passes its test",
             "evidence": {"class": "machine",
                          "command": "python3 -c \"print('ok')\""}},
        ],
    }


class DhritiTestCase(unittest.TestCase):
    """Temp home + simulated clock + wired services (v0.5.0 names)."""

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
        self.evidence = EvidenceService(self.db, self.clock,
                                        home=self.home)
        self.passes = ResearchService(self.db, self.config, self.clock)
        self.bootcamp = BootcampService(self.db, self.config, self.clock)
        self.breaks = BreakGlassService(
            self.db, self.config, self.clock, self.ledger)
        self.aftermath = AftermathService(
            self.db, self.config, self.clock, self.ledger)
        self.parking = ParkingLotService(self.db, self.clock, self.ledger)
        self.review = ColdReviewService(self.db, self.clock, self.ledger)
        self.leisure = LeisureService(self.db, self.clock, self.ledger)
        self.vidura = ViduraService(self.db, self.config, self.clock,
                                    self.ledger)
        self.policy = PolicyEngine(self.db, self.clock)
        self.today = self.clock.now_utc().astimezone(
            local_tz(LOCAL_TZ)).date()

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers ------------------------------------------------------------
    def seal_today(self, payload=None):
        payload = payload or daily_payload()
        # NOTE: no ensure_day first — the day row is created on demand
        # AFTER the seal, so it is born PLANNED (not NO_CONTRACT),
        # exactly like the daemon's order: contract cold, then day.
        return self.contracts.seal(self.today.isoformat(), payload)

    def walk_to_active(self, session_id: str) -> dict:
        """DRAFT -> SEALED -> ARMING -> ACTIVE (no adapter gate; tests
        exercise the state machine, not the bridge)."""
        row = self.sessions.seal(session_id)
        row = self.sessions.arming(session_id)
        return self.sessions.activate(session_id)

    def open_today(self):
        """Seal + open today; returns (day, contract, session)."""
        self.seal_today()
        day = self.days.today()
        contract = self.contracts.for_day(day["date"])
        day = self.days.try_open(day, contract)
        return day, contract

    def start_session(self, task="task"):
        """Seal + open + create + activate a session on today."""
        day, contract = self.open_today()
        session = self.sessions.create(day["id"], contract["id"], task)
        self.walk_to_active(session["id"])
        return self.sessions.get(session["id"])

    def make_daemon(self, **config_overrides) -> Daemon:
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
        # Bug 3 (Phase 0): reassign every service handle so stale
        # references to the closed database cannot silently pass.
        self.ledger = daemon.ledger
        self.contracts = daemon.contracts
        self.days = daemon.days
        self.sessions = daemon.sessions
        self.evidence = daemon.evidence
        self.passes = daemon.passes
        self.bootcamp = daemon.bootcamp
        self.breaks = daemon.breaks
        self.aftermath = daemon.aftermath
        self.parking = daemon.parking
        self.review = daemon.review
        self.vidura = daemon.vidura
        self.leisure = LeisureService(self.db, self.clock, self.ledger)
        self.policy = daemon.policy_engine
        return daemon

    def make_cli_context(self):
        """A Context built the way the CLI builds one: its own database
        connection to the same file. close() closes only that handle."""
        from dhriti.cli import Context
        return Context(self.home, config=json.loads(
            json.dumps(self.config)), clock=self.clock)

    def _run(self, command: str, args: dict):
        """Run one CLI command by name with a fresh Context; catches
        SystemExit; closes the context."""
        import argparse
        import contextlib
        import io
        from dhriti import cli
        ctx = self.make_cli_context()
        out = io.StringIO()
        exit_code = None
        try:
            with contextlib.redirect_stdout(out):
                try:
                    getattr(cli, command)(
                        argparse.Namespace(**args), ctx)
                except SystemExit as exc:
                    exit_code = exc.code
        finally:
            ctx.close()
        return out.getvalue(), exit_code


if __name__ == "__main__":
    unittest.main()
