"""Recovery + integration: daemon death, arming gate, full happy-path
day, bridge round-trip. These are the 'fail proof' tests."""

import json
import urllib.request

from dhriti.models import DayState, SessionState

from test_plumbing import DhritiTestCase, daily_payload


class TestDaemonIntegration(DhritiTestCase):
    def test_full_simulated_day(self):
        """bootcamp -> ritual -> day opens -> session -> proof -> success
        -> early release at day_close -> aftermath -> chain verifies."""
        daemon = self.make_daemon()
        # 1. bootcamp
        daemon.bootcamp.start(30)
        # 2. cold-state ritual (the one requirement: write something)
        payload = daily_payload()
        cid = daemon.days.contracts.create_draft(
            __import__("dhriti.models", fromlist=["ContractKind"])
            .ContractKind.DAILY, self.today.isoformat(), payload)
        daemon.days.contracts.seal(cid)
        # 3. daemon ticks: day should open exactly at window start
        daemon._tick()
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], DayState.OPEN.value)
        # 4. session start through the arming gate
        sess = daemon.start_session(
            "reverse the array", '[{"kind":"command"}]')
        self.assertEqual(sess["state"], SessionState.ACTIVE.value)
        # 5. proof: a real machine-checked command
        ev = daemon.evidence.machine_check_command(
            sess["id"], "python3 -c \"print('sorted')\"")
        self.assertEqual(ev["verdict"], "ACCEPTED")
        # 6. session success
        daemon.end_session_success(sess["id"])
        # 7. simulate a browser event through the bridge wiring
        daemon.ledger.record("browser_navigation",
                             source_adapter="extension",
                             session_id=sess["id"],
                             observed_payload={
                                 "url": "https://youtube.com/watch?v=x"})
        # 8. day_close passes with targets met -> early release
        self.clock.advance(hours=10, minutes=2)
        daemon._tick()
        day = daemon.days.get(self.today)
        self.assertEqual(day["state"], DayState.RELEASED_EARLY.value)
        # 9. aftermath + verification
        paths = daemon.run_aftermath(self.today.isoformat())
        self.assertTrue(paths["html"].endswith(".html"))
        result = daemon.ledger.verify_chain()
        self.assertTrue(result["ok"])
        daemon.release_lock()
        daemon.db.close()

    def test_arming_gate_blocks_active_without_required_adapter(self):
        daemon = self.make_daemon(
            enforcement={"required_adapters": ["extension_bridge"],
                         "level": "E1"},
            bridge={"port": 0})
        # no daemon bridge started -> policy provider returns None-ish
        payload = daily_payload()
        cid = daemon.days.contracts.create_draft(
            __import__("dhriti.models", fromlist=["ContractKind"])
            .ContractKind.DAILY, self.today.isoformat(), payload)
        daemon.days.contracts.seal(cid)
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
        payload = daily_payload()
        cid = daemon.days.contracts.create_draft(
            __import__("dhriti.models", fromlist=["ContractKind"])
            .ContractKind.DAILY, self.today.isoformat(), payload)
        daemon.days.contracts.seal(cid)
        daemon._tick()
        sess = daemon.start_session("task", "")
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
        payload = daily_payload()
        cid = daemon.days.contracts.create_draft(
            __import__("dhriti.models", fromlist=["ContractKind"])
            .ContractKind.DAILY, self.today.isoformat(), payload)
        daemon.days.contracts.seal(cid)
        daemon._tick()
        sess = daemon.start_session("task", "")
        daemon._publish()
        daemon.bridge.start()
        port = daemon.bridge._httpd.server_address[1]
        token = (daemon.home / "bridge_token").read_text().strip()
        base = f"http://127.0.0.1:{port}"
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
        rp = self.research.start(
            "JWT validation unknown",
            ["docs.spring.io"], "rerun the failing test")
        self.assertEqual(rp["state"], "OPEN")
        active = self.research.active_for()
        self.assertEqual(active["id"], rp["id"])
        self.clock.advance(minutes=25)  # default 20 min pass
        expired = self.research.expire_overdue()
        self.assertIn(rp["id"], expired)
        self.assertIsNone(self.research.active_for())

    def test_return_records_notes(self):
        rp = self.research.start(
            "syntax unknown", ["docs.oracle.com"], "write the loop")
        self.research.return_to_task(rp["id"], "found the overload")
        row = self.db.query_one(
            "SELECT * FROM research_pass WHERE id=?", (rp["id"],))
        self.assertEqual(row["state"], "RETURNED")
        self.assertEqual(row["notes"], "found the overload")

    def test_pass_requires_sources_and_return_condition(self):
        from dhriti.research_pass import ResearchPassError
        with self.assertRaises(ResearchPassError):
            self.research.start("dep", [], "back to work")
        with self.assertRaises(ResearchPassError):
            self.research.start("dep", ["a.com"], "")


if __name__ == "__main__":
    unittest.main()
