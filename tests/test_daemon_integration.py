"""Recovery + integration: daemon death, arming gate, full happy-path
day, bridge round-trip. These are the 'fail proof' tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest

import json
import urllib.error
import urllib.request

from dhriti.models import DayState, SessionState

from test_plumbing import DhritiTestCase, daily_payload


def _seal(daemon, today, payload=None):
    payload = payload or daily_payload()
    return daemon.days.contracts.seal(today.isoformat(), payload)


class TestDaemonIntegration(DhritiTestCase):
    def test_full_simulated_day(self):
        """bootcamp -> ritual -> day opens -> session -> proof -> success
        -> early release at day_close -> aftermath -> chain verifies."""
        daemon = self.make_daemon()
        # 1. bootcamp
        daemon.bootcamp.start(30)
        # 2. cold-state ritual (the one requirement: write something)
        _seal(daemon, self.today)
        # 3. daemon ticks: day should open exactly at window start
        daemon._tick()
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], DayState.OPEN.value)
        # 4. session start through the arming gate
        sess = daemon.start_session("reverse the array")
        self.assertEqual(sess["state"], SessionState.ACTIVE.value)
        # 5. proof: the contract's declared command, machine-checked
        ev = daemon.evidence.machine_check_command(
            sess["id"], "reversal passes its test",
            daily_payload()["targets"][0]["evidence"]["command"])
        self.assertEqual(ev["verdict"], "ACCEPTED")
        # 6. session success
        daemon.end_session_success(sess["id"])
        # 7. simulate a browser event through the bridge wiring
        daemon.ledger.record("browser_navigation",
                             source_adapter="extension",
                             session_id=sess["id"],
                             observed={
                                 "url": "https://youtube.com/watch?v=x"})
        # 8. day_close passes with targets met -> early release
        self.clock.advance(hours=10, minutes=2)
        daemon._tick()
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], DayState.RELEASED_EARLY.value)
        # 9. aftermath + verification
        paths = daemon.run_aftermath(self.today.isoformat())
        self.assertTrue(str(paths["html"]).endswith(".html"))
        result = daemon.ledger.verify_chain()
        self.assertTrue(result["ok"])
        daemon.release_lock()
        daemon.db.close()

    def test_arming_gate_blocks_active_without_required_adapter(self):
        daemon = self.make_daemon(
            enforcement={"required_adapters": ["extension_bridge"],
                         "level": "E1"},
            bridge={"port": 0})
        _seal(daemon, self.today)
        daemon._tick()
        # force arming failure by pointing required at a dead adapter
        daemon.config["enforcement"]["required_adapters"] = ["focusme"]
        daemon.config["adapters"]["focusme"] = {
            "enabled": True, "executable": "definitely-missing-tool",
            "arm_cmd": [], "disarm_cmd": []}
        daemon.adapters = __import__(
            "dhriti.adapters.registry", fromlist=["build_adapters"]
        ).build_adapters(daemon.config, daemon.home,
                         daemon._policy_provider)
        with self.assertRaises(RuntimeError) as ctx:
            daemon.start_session("task")
        self.assertIn("arming failed", str(ctx.exception))
        sess = daemon.sessions.active()
        self.assertIsNone(sess, "session must NOT be ACTIVE")
        row = daemon.db.query_one(
            "SELECT state FROM session ORDER BY started_at DESC")
        self.assertEqual(row["state"], SessionState.ARMING_FAILED.value)
        daemon.release_lock()
        daemon.db.close()

    def test_dead_daemon_sessions_recovered(self):
        daemon = self.make_daemon()
        daemon.bootcamp.start(30)
        _seal(daemon, self.today)
        daemon._tick()
        sess = daemon.start_session("task")
        self.assertEqual(sess["state"], SessionState.ACTIVE.value)
        # daemon dies (no shutdown ran); a new daemon boots next day
        self.clock.advance(days=1)
        daemon.release_lock()
        daemon2 = self.make_daemon()
        notes = daemon2.recover()
        self.assertTrue(any("INTERRUPTED" in n for n in notes))
        row = daemon2.db.query_one(
            "SELECT state FROM session WHERE id=?", (sess["id"],))
        self.assertEqual(row["state"], SessionState.INTERRUPTED.value)
        result = daemon2.ledger.verify_chain()
        self.assertTrue(result["ok"], "recovery must not break the chain")
        daemon2.release_lock()
        daemon2.db.close()

    def test_bridge_serves_policy_and_ingests_events(self):
        daemon = self.make_daemon()
        daemon.bootcamp.start(30)
        _seal(daemon, self.today)
        daemon._tick()
        sess = daemon.start_session("task")
        daemon._publish()
        daemon.bridge.start()
        port = daemon.bridge.port_bound
        token = (daemon.home / "bridge_token").read_text().strip()
        base = f"http://127.0.0.1:{port}"
        # authorized status fetch (the /status payload carries "day")
        request = urllib.request.Request(
            base + "/status", headers={"X-Dhriti-Token": token})
        with urllib.request.urlopen(request, timeout=5) as resp:
            status = json.loads(resp.read().decode())
        self.assertIn("day", status)
        # authorized policy fetch
        request = urllib.request.Request(
            base + "/policy", headers={"X-Dhriti-Token": token})
        with urllib.request.urlopen(request, timeout=5) as resp:
            pol = json.loads(resp.read().decode())
        self.assertTrue(pol["enforce"])
        self.assertIn("blocked_domains", pol)
        self.assertIn("expires_at", pol, "fail-safe TTL required")
        # unauthorized fetch refused
        try:
            urllib.request.urlopen(base + "/policy", timeout=5)
            self.fail("expected 401")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 401)
        # event ingest
        body = json.dumps({"url": "https://docs.oracle.com/x",
                           "title": "Java docs"}).encode()
        request = urllib.request.Request(
            base + "/events", data=body, method="POST",
            headers={"X-Dhriti-Token": token,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as resp:
            out = json.loads(resp.read().decode())
        self.assertEqual(out["ingested"], 1)
        events = daemon.ledger.events("browser_navigation")
        self.assertEqual(len(events), 1)
        daemon.bridge.stop()
        daemon.release_lock()
        daemon.db.close()

    def test_dormant_policy_when_day_not_open(self):
        daemon = self.make_daemon()
        pol = daemon._current_extension_policy()
        self.assertFalse(pol["enforce"])
        self.assertIn("no open day", pol.get("reason", ""))
        daemon.release_lock()
        daemon.db.close()


class TestResearchPass(DhritiTestCase):
    def test_pass_expiry_removes_allowance(self):
        session = self.start_session()
        rp = self.passes.open(session["id"], "JWT validation unknown",
                              minutes=20,
                              sources=["docs.spring.io"])
        self.assertEqual(rp["state"], "OPEN")
        active = self.passes.active()
        self.assertEqual(active["id"], rp["id"])
        self.assertEqual(self.passes.active_sources(), ["docs.spring.io"])
        self.clock.advance(minutes=25)
        expired = self.passes.expire_overdue()
        self.assertIn(rp["id"], expired)
        self.assertIsNone(self.passes.active())
        self.assertEqual(self.passes.active_sources(), [])

    def test_return_records_answer(self):
        session = self.start_session()
        rp = self.passes.open(session["id"], "syntax unknown",
                              minutes=5)
        row = self.passes.return_pass("found the overload")
        self.assertEqual(row["state"], "RETURNED")
        self.assertEqual(row["answer"], "found the overload")

    def test_pass_requires_question_and_finite_minutes(self):
        from dhriti.research_pass import ResearchPassError
        session = self.start_session()
        with self.assertRaises(ResearchPassError):
            self.passes.open(session["id"], "  ")
        with self.assertRaises(ResearchPassError):
            self.passes.open(session["id"], "q", minutes=0)
        with self.assertRaises(ResearchPassError):
            self.passes.open(session["id"], "q", minutes=500)


class TestDoubleActiveSession(DhritiTestCase):
    def test_double_active_session_refused(self):
        """Bug 5 (Phase 0): the daemon refuses a second concurrent
        session instead of leaving two ACTIVE rows."""
        daemon = self.make_daemon()
        try:
            _seal(daemon, self.today)
            daemon._tick()
            first = daemon.start_session("task one")
            self.assertEqual(first["state"], SessionState.ACTIVE.value)
            with self.assertRaises(RuntimeError) as ctx:
                daemon.start_session("task two")
            self.assertIn("already ACTIVE", str(ctx.exception))
        finally:
            daemon.release_lock()
            daemon.db.close()


class TestBuilderClauseAllowlist(DhritiTestCase):
    def test_allowlist_wins_over_builder_clause(self):
        """Bug 7 (Phase 0): a builder-clause domain that is also in the
        profile allowlist is NOT blocked; the override is recorded as
        builder_clause_overridden_by_allowlist."""
        daemon = self.make_daemon(
            builder_clause={"enabled": True,
                            "blocked_domains": ["github.com",
                                                "example-distraction.com"]})
        try:
            payload = daily_payload()
            # github.com is allowed work surface for this contract
            payload["allowed_tools"] = ["github.com"]
            daemon.days.contracts.seal(self.today.isoformat(), payload)
            daemon._tick()
            session = daemon.start_session("task")
            # the override event exists
            events = daemon.ledger.events(
                event_type="builder_clause_overridden_by_allowlist")
            self.assertEqual(len(events), 1)
            import json as _json
            observed = _json.loads(events[0]["observed_payload"])
            self.assertEqual(observed["domains"], ["github.com"])
            # and the policy snapshot blocks only the residual domain
            snap = daemon.policy_engine.current_snapshot()
            self.assertIn("example-distraction.com",
                          snap["blocked_domains"])
            self.assertNotIn("github.com", snap["blocked_domains"])
        finally:
            daemon.release_lock()
            daemon.db.close()


if __name__ == "__main__":
    unittest.main()
