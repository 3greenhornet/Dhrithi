"""The daemon: the wall's keeper for the whole commitment period
(PDF 3.1 — the enforcement boundary is the bootcamp, not the session).

Run: `dhriti daemon` (one instance per home; a lockfile guards against
double-starts).

Every tick (default 5s):
  1. heartbeat (survives crashes; recovery uses it)
  2. ensure today's day row exists
  3. open the day when the window starts (requires sealed contract)
  4. evaluate the open day: unconditional window_end release FIRST,
     then early-release-at-day_close-if-targets-met
  5. expire overdue research passes
  6. poll observation adapters (if enabled)
  7. publish status + extension policy on the bridge
  8. disclose adapter health honestly in the experiment record

Startup recovery (dossier 3.4, PDF 3.4):
  * sessions left SEALED/ARMING/ACTIVE by a dead daemon -> INTERRUPTED,
    then reviewed to an honest terminal state;
  * days still OPEN past window_end -> RECOVERED (unverifiable outcome);
  * everything recorded, nothing hidden, no penalty claimed.
"""

import datetime as _dt
import hashlib
import json
import os
import signal
import socket
import tempfile
from pathlib import Path
from typing import Optional

from .adapters.registry import build_adapters, build_gate
from .bootcamp import BootcampService
from .bridge import BridgeServer, BridgeState, ensure_token, \
    handle_extension_event
from .constants import load_config
from .day_window import DayService, resolve_observation_end
from .db import Database
from .evidence import EvidenceService
from .errors import BreakGlassError
from .ledger import Ledger
from .models import SessionState, WorkMode
from .policy import PolicyEngine
from .profiles import CATEGORY_DOMAINS, load_profiles
from .research_pass import ResearchService
from .review import ColdReviewService, ParkingLotService
from .session import SessionService
from .timeutil import Clock, RealClock, local_tz, parse_iso, to_iso
from .break_glass import BreakGlassService
from .aftermath import AftermathService


class Daemon:
    def __init__(self, home: Path, config: Optional[dict] = None,
                 clock: Optional[Clock] = None, tick_seconds: float = 5.0):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.config = config or load_config(self.home)
        self.clock = clock or RealClock()
        self.tick_seconds = tick_seconds
        self.db = Database(
            self.home / "dhriti.sqlite3",
            journal_mode=(self.config.get("database", {})
                          .get("journal_mode")))
        self.ledger = Ledger(
            self.db, self.clock,
            int(self.config.get("ledger", {}).get(
                "anchor_interval_events", 100)))
        self.contracts = None  # set after services init
        self.days = DayService(self.db, self.config, self.clock)
        self.sessions = SessionService(self.db, self.clock)
        self.evidence = EvidenceService(self.db, self.clock)
        self.research = ResearchService(self.db, self.config, self.clock)
        self.bootcamp = BootcampService(self.db, self.config, self.clock)
        self.break_glass = BreakGlassService(
            self.db, self.config, self.clock, self.ledger)
        self.aftermath = AftermathService(
            self.db, self.config, self.clock, self.ledger)
        self.parking = ParkingLotService(self.db, self.clock, self.ledger)
        self.review = ColdReviewService(self.db, self.clock, self.ledger)
        self.policy_engine = PolicyEngine(self.db, self.clock)
        self.profiles = load_profiles(self.home)
        # D-050 (configuration immutability): the running daemon never
        # hot-reloads config or profiles. The loaded rules are
        # fingerprinted at start; a config/profile file that changes on
        # disk WHILE the daemon runs is recorded as drift — visible,
        # never hot-loaded. The edit takes effect at next start, by law.
        self._loaded_fingerprint = self._fingerprint(
            self.config, self.profiles)
        self._disk_fingerprint_at_start = self._disk_fingerprint()
        self._evening_marker_date = None    # D-048 dedupe
        self._earned_marker_date = None     # D-049 dedupe

        self._bridge_state = BridgeState()
        self._policy_provider = self._current_extension_policy
        self.adapters = build_adapters(
            self.config, self.home, self._policy_provider)
        self.gate = build_gate(self.ledger)
        self.bridge = self._build_bridge()
        self._stop = False
        self._lock_path = self.home / "daemon.lock"

    # -- bridge wiring ---------------------------------------------------------
    @staticmethod
    def _fingerprint(config: dict, profiles: dict) -> str:
        """D-050: a stable hash of everything the daemon enforces with."""
        payload = json.dumps({"config": config, "profiles": profiles},
                             sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _disk_fingerprint(self) -> Optional[str]:
        """Fingerprint of the config/profile files as they are on disk
        right now (None if unreadable — never a crash, never a guess)."""
        try:
            return self._fingerprint(load_config(self.home),
                                     load_profiles(self.home))
        except Exception:
            return None

    def _check_config_drift(self):
        """D-050: did the config/profile files change on disk while this
        daemon was running? Recorded, never hot-loaded — the edit takes
        effect at the next daemon start, by law."""
        disk_now = self._disk_fingerprint()
        if disk_now is None \
                or self._disk_fingerprint_at_start is None \
                or disk_now == self._disk_fingerprint_at_start:
            return
        self.ledger.record(
            "config_drift_detected",
            observed_payload={"at_start": self._disk_fingerprint_at_start,
                              "on_disk_now": disk_now},
            action_taken="no hot reload — change takes effect at "
                        "next daemon start (D-050)",
            telemetry_quality="DEGRADED")
        self._disk_fingerprint_at_start = disk_now
        # one event per change is enough to make the drift visible

    def _observation_end(self, local_date: _dt.date) -> _dt.datetime:
        return resolve_observation_end(local_date, self.config)

    def _evening_observation_active(self) -> bool:
        """D-048: enforcement ended at window_end; observation may run
        on (enabled cold, under surveillance_comfort) until day_end."""
        if not self.config.get("observation_evening", {}).get("enabled"):
            return False
        today = self._local_today()
        day = self.days.get(today)
        if not day or not day.get("window_end_at"):
            return False
        now = self.clock.now_utc()
        if now < parse_iso(day["window_end_at"]):
            return False
        return now < self._observation_end(today)

    def _build_bridge(self) -> BridgeServer:
        cfg = self.config.get("bridge", {})
        token = ensure_token(self.home)
        daemon = self

        def on_event(ledger, event):
            if event.get("type") == "browser_proof":
                daemon.ledger.record(
                    "browser_proof_submitted",
                    source_adapter="extension",
                    observed_payload=event)
                return
            active = daemon.sessions.active()
            handle_extension_event(
                ledger, event,
                session_resolver=(lambda: active["id"]) if active else None)
            for adapter in daemon.adapters:
                if adapter.name == "extension_bridge":
                    adapter.note_extension_seen()

        return BridgeServer(
            host=cfg.get("host", "127.0.0.1"),
            port=int(cfg.get("port", 7311)),
            token=token,
            state=self._bridge_state,
            ledger=self.ledger,
            on_event=on_event)

    def _current_extension_policy(self) -> Optional[dict]:
        """What the bridge serves at /policy right now. Dormant unless a
        day is OPEN (fail-safe: the extension's cache also expires) —
        except the earned evening (D-049): after window_end, on a day
        whose targets were NOT met, consumption categories stay blocked
        until day_end (bounded, D-018; enabled cold, like D-035)."""
        day = self.days.get(self._local_today())
        if not day or day["state"] != "OPEN":
            earned = self._earned_evening_policy(day)
            if earned:
                return earned
            return {"enforce": False, "version": 0,
                    "reason": "no open day"}
        snapshot = self.policy_engine.current_snapshot()
        if not snapshot:
            return {"enforce": False, "version": 0,
                    "reason": "no policy snapshot"}
        rules = self.policy_engine.extension_rules(snapshot)
        ttl_minutes = int(self.config.get("bridge", {}).get(
            "policy_ttl_minutes", 720))
        from datetime import timedelta
        rules["expires_at"] = to_iso(
            self.clock.now_utc() + timedelta(minutes=ttl_minutes))
        # fold in the current research pass sources (bounded allowance)
        active_pass = self.research.active_for()
        if active_pass:
            rules["research_sources"] = active_pass["sources"]
            rules["research_expires_at"] = active_pass["expires_at"]
        else:
            rules["research_sources"] = []
            rules["research_expires_at"] = None
        return rules

    def _earned_evening_policy(self, day: Optional[dict]) -> Optional[dict]:
        """D-049: the specimen's own protocol, generalized. On a closed
        day whose targets were NOT met, the configured consumption
        categories stay blocked until day_end. Meeting the day's targets
        is what earns an open evening. Default OFF; enabling is a
        cold-state act (config), exactly like the builder clause."""
        cfg = self.config.get("earned_evening", {})
        if not cfg.get("enabled") or not day:
            return None
        if day["state"] in ("PLANNED", "NO_CONTRACT", "OPEN"):
            return None                     # the window is not over yet
        if day["targets_met"]:
            return None                     # earned: the evening is open
        now = self.clock.now_utc()
        today = self._local_today()
        until = self._observation_end(today)
        if now >= until:
            return None                     # bounded ceiling (D-018)
        categories = [c for c in cfg.get("blocked_categories", [])
                      if c in CATEGORY_DOMAINS]
        if not categories:
            return None
        blocked = sorted({d for c in categories
                          for d in CATEGORY_DOMAINS.get(c, [])})
        if self._earned_marker_date != day["date"]:
            self._earned_marker_date = day["date"]
            self.ledger.record(
                "earned_evening_applied",
                observed_payload={"date": day["date"],
                                  "categories": categories,
                                  "until": to_iso(until),
                                  "targets_met": False},
                action_taken="consumption categories blocked until "
                            "day_end — day targets unmet (D-049)",
                telemetry_quality="OK")
        contract_line = ""
        if day.get("contract_id"):
            row = self.db.query_one(
                "SELECT payload_json FROM contract WHERE id=?",
                (day["contract_id"],))
            if row:
                try:
                    contract_line = (json.loads(row["payload_json"])
                                     .get("mandatory_task") or "")
                except Exception:
                    contract_line = ""
        return {
            "version": 0,          # day-level rules; frozen by D-050
            "enforce": True,
            "mode": "earned_evening",
            "taper_stage": 1,
            "work_mode": "earned_evening",
            "blocked_domains": blocked,
            "allowed_domains": [],
            "suppress_surfaces": True,
            "contract_line": contract_line,
            "expires_at": to_iso(until),
            "research_sources": [],
            "research_expires_at": None,
        }

    # -- lifecycle --------------------------------------------------------------
    def _local_today(self) -> _dt.date:
        tz = local_tz(self.config.get("timezone", "UTC"))
        return self.clock.now_utc().astimezone(tz).date()

    def acquire_lock(self) -> bool:
        try:
            if self._lock_path.exists():
                pid = self._lock_path.read_text(encoding="utf-8").strip()
                if pid and _pid_alive(int(pid)):
                    return False
            self._lock_path.write_text(str(os.getpid()), encoding="utf-8")
            return True
        except Exception:
            return False

    def release_lock(self):
        try:
            self._lock_path.unlink()
        except Exception:
            pass

    def recover(self) -> list:
        """Honest recovery of everything a dead daemon left behind."""
        notes = []
        for sess in self.sessions.unfinished():
            if sess["state"] in ("ARMING", "ACTIVE"):
                self.sessions.mark_interrupted(sess["id"])
                self.ledger.record(
                    "session_recovered_interrupted",
                    session_id=sess["id"],
                    observed_payload={"prior_state": sess["state"]},
                    action_taken="marked INTERRUPTED")
                notes.append(f"session {sess['id'][:8]} -> INTERRUPTED")
        recovered_days = self.days.recover_open_days()
        for day_id in recovered_days:
            self.ledger.record(
                "day_recovered", observed_payload={"day": day_id},
                action_taken="marked RECOVERED")
            notes.append(f"day {day_id[:8]} -> RECOVERED")
        return notes

    def run(self, max_ticks: Optional[int] = None):
        """Main loop. max_ticks exists for tests and the simulated demo."""
        if not self.acquire_lock():
            raise RuntimeError(
                "another daemon holds the lock (daemon.lock)")
        recovery = self.recover()
        if recovery:
            for note in recovery:
                print(f"[recovery] {note}")
        self.ledger.record("daemon_started", observed_payload={
            "pid": os.getpid(), "host": socket.gethostname(),
            "config_fingerprint": self._loaded_fingerprint})
        self.bridge.start()
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        self._publish()
        ticks = 0
        try:
            while not self._stop:
                self._tick()
                if max_ticks is not None:
                    ticks += 1
                    if ticks >= max_ticks:
                        break
                self.clock.sleep(self.tick_seconds)
        finally:
            self._shutdown()
        return ticks

    def _handle_signal(self, signum, frame):
        self._stop = True

    def _shutdown(self):
        self.ledger.record("daemon_stopping", observed_payload={
            "clean": True})
        day = self.days.get(self._local_today())
        if not (day and day["state"] == "OPEN"):
            for adapter in self.adapters:
                try:
                    adapter.disarm()
                except Exception:
                    pass
        self.bridge.stop()
        self.release_lock()
        self.db.close()

    # -- one tick -----------------------------------------------------------------
    def _tick(self):
        now = self.clock.now_utc()
        self.db.insert("heartbeat", {
            "at_utc": to_iso(now), "pid": os.getpid(),
            "host": socket.gethostname()})
        today = self._local_today()
        self.days.ensure_day(today)
        day = self.days.get(today)

        if day:
            # 1. open when the window starts (needs the sealed contract)
            if day["state"] in ("PLANNED", "NO_CONTRACT"):
                day = self.days.try_open(day)
            # 2. evaluate with targets; unconditional ceiling is inside
            targets_met = bool(day["state"] == "OPEN"
                               and self.days.targets_met(day))
            new_day = self.days.evaluate(day, targets_met)
            if new_day["state"] != day["state"]:
                self.ledger.record(
                    "day_state_changed",
                    observed_payload={"date": new_day["date"],
                                      "from": day["state"],
                                      "to": new_day["state"]})
                day = new_day
                if day["state"] not in ("OPEN", "PLANNED", "NO_CONTRACT"):
                    self._disarm_adapters()

        # 3. research pass expiry
        for pass_id in self.research.expire_overdue():
            self.ledger.record(
                "research_pass_expired",
                observed_payload={"pass": pass_id},
                action_taken="sources no longer allowed")

        # 3b. evening observation marker (D-048), once per day
        if self._evening_observation_active() \
                and self._evening_marker_date != today:
            self._evening_marker_date = today
            self.ledger.record(
                "evening_observation_active",
                observed_payload={
                    "date": today.isoformat(),
                    "until": to_iso(self._observation_end(today))},
                action_taken="observation continues past window_end; "
                            "counts only, no content (D-014)",
                telemetry_quality="OK")

        # 4. observation polling — armed sessions, plus the evening
        #    window when observation_evening is enabled (D-048)
        evening = self._evening_observation_active()
        for adapter in self.adapters:
            if adapter.role == "observation" \
                    and (adapter._armed or evening):
                try:
                    adapter.poll(self.ledger, self.clock)
                except Exception as exc:
                    self.ledger.record(
                        "observer_poll_failed",
                        source_adapter=adapter.name,
                        observed_payload={"error": str(exc)},
                        telemetry_quality="DEGRADED")

        self._publish()

    def _disarm_adapters(self):
        keep_observing = self._evening_observation_active()
        for adapter in self.adapters:
            try:
                if adapter.name != "extension_bridge" \
                        and not (keep_observing
                                 and adapter.role == "observation"):
                    adapter.disarm()
            except Exception:
                pass
        # bridge serves dormant policy (enforce=false) -> extension unlocks
        self.ledger.record("adapters_disarmed", observed_payload={
            "observation_continues": keep_observing})

    def _publish(self):
        today = self._local_today()
        day = self.days.get(today)
        active = self.sessions.active()
        bootcamp = self.bootcamp.active()
        self._bridge_state.publish_policy(self._current_extension_policy())
        self._bridge_state.publish_status({
            "daemon": "running",
            "now_utc": self.clock.iso(),
            "today": today.isoformat(),
            "day_state": day["state"] if day else "none",
            "active_session": (active["id"] if active else None),
            "evening": {
                "observation": self._evening_observation_active(),
                "earned_enforcement": bool(
                    day and self._earned_evening_policy_marker_free(day)),
            },
            "bootcamp": ({
                "started_at": bootcamp["started_at"],
                "planned_days": bootcamp["planned_days"],
                "state": bootcamp["state"],
                "taper_stage": bootcamp["taper_stage"],
            } if bootcamp else None),
            "adapters": [a.status() for a in self.adapters],
        })

    # -- session orchestration (used by CLI and demo) ----------------------------
    def _earned_evening_policy_marker_free(self, day: dict) -> bool:
        """Whether the earned-evening policy would be served for this day
        right now — WITHOUT the marker side effect (for status display)."""
        saved = self._earned_marker_date
        try:
            return self._earned_evening_policy(day) is not None
        finally:
            self._earned_marker_date = saved

    def start_session(self, task: str, evidence_spec: str = "",
                      profile_name: str = "coding",
                      work_mode: WorkMode = WorkMode.CLOSED_WORLD,
                      condition: str = None) -> dict:
        """Full DRAFT -> SEALED -> ARMING -> ACTIVE flow with the arming
        gate. Returns the session row (or raises StateError)."""
        self._check_config_drift()   # D-050: drift visible, never hot-loaded
        # Bug 5 (Phase 0): refuse a second concurrent session. The state
        # machine allows many ACTIVE rows; the daemon must not.
        if self.sessions.active() is not None:
            raise RuntimeError(
                "a session is already ACTIVE — end it (dhriti session end) "
                "before starting another")
        today = self._local_today()
        day = self.days.ensure_day(today)
        if day["state"] != "OPEN":
            raise RuntimeError(
                f"day is {day['state']}; the wall is only up while the "
                "day is OPEN")
        self.break_glass.check_session_start_allowed()
        session = self.sessions.start(
            day["id"], task, evidence_spec, condition)
        session = self.sessions.seal(session["id"])

        # policy snapshot: contract + profile + mode + research sources
        contract = self.days.contracts.require_sealed_daily(today)
        profile = self.profiles.get(profile_name, {})
        active_pass = self.research.active_for(session["id"])
        bootcamp = self.bootcamp.active()
        taper_stage = bootcamp["taper_stage"] if bootcamp else 1
        mode = (WorkMode.BOUNDED_RESEARCH
                if (work_mode == WorkMode.BOUNDED_RESEARCH or active_pass)
                else work_mode)
        # Builder clause (risk R-001 made mechanical): while the day's
        # targets are unmet, the configured builder domains are blocked.
        # Building the tool is a privilege earned by meeting the target.
        extra_blocked = []
        builder_cfg = self.config.get("builder_clause", {})
        if builder_cfg.get("enabled") and builder_cfg.get("blocked_domains"):
            if not self.days.targets_met(day):
                raw_blocked = list(builder_cfg["blocked_domains"])
                # Bug 7 (Phase 0): the profile allowlist wins over the
                # builder clause. If github.com is an allowed work domain
                # for the profile, blocking it because the day's targets
                # are unmet would block the work that meets the targets.
                # The override is recorded, never silent.
                allow = set(profile.get("allowed_domains", [])
                            + contract["payload"].get("allowed_tools", []))
                overridden = [d for d in raw_blocked if d in allow]
                extra_blocked = [d for d in raw_blocked if d not in allow]
                if overridden:
                    self.ledger.record(
                        "builder_clause_overridden_by_allowlist",
                        session_id=None,
                        observed_payload={
                            "domains": overridden,
                            "reason": "profile allowlist wins (L-6 note)"},
                        action_taken="builder block skipped for allowlisted "
                                    "domains",
                        telemetry_quality="OK")
                if extra_blocked:
                    self.ledger.record(
                        "builder_clause_applied",
                        session_id=session["id"],
                        observed_payload={
                            "domains": extra_blocked,
                            "reason": "day targets unmet"},
                        action_taken="builder domains blocked until targets met",
                        telemetry_quality="OK")
        suppress = bool(self.config.get("surface_suppression", {})
                        .get("enabled", True))
        policy = self.policy_engine.build_snapshot(
            profile, contract["payload"], mode,
            active_pass["sources"] if active_pass else None,
            active_pass["expires_at"] if active_pass else None,
            taper_stage=taper_stage,
            contract_id=contract["id"], day_id=day["id"],
            suppress_surfaces=suppress,
            extra_blocked_domains=extra_blocked)
        self.ledger.record(
            "policy_sealed", session_id=session["id"],
            policy_version=str(policy["version"]),
            observed_payload={"mode": mode.value,
                              "taper_stage": taper_stage},
            action_taken="snapshot frozen for session")

        # arming gate
        session = self.sessions.arming(session["id"])
        required = self.config.get("enforcement", {}).get(
            "required_adapters", ["extension_bridge"])
        report = self.gate.arm_all(self.adapters, policy, required)
        if report.failed:
            session = self.sessions.arming_failed(
                session["id"], report.disclosure())
            self.ledger.record(
                "session_arming_failed", session_id=session["id"],
                observed_payload={"failed": report.failed},
                action_taken="disclosed")
            raise RuntimeError(
                f"arming failed — session NOT active. {report.disclosure()}")
        session = self.sessions.activate(session["id"])
        self.ledger.record(
            "session_active", session_id=session["id"],
            observed_payload={"task": task},
            action_taken="wall up; disclosure: " + report.disclosure())
        return session

    def end_session_success(self, session_id: str, note: str = "") -> dict:
        sess = self.sessions.get(session_id)
        if not sess or sess["state"] != SessionState.ACTIVE.value:
            raise RuntimeError("session is not ACTIVE")
        accepted = self.sessions.accepted_evidence_count(session_id)
        if accepted < 1:
            raise RuntimeError(
                "no accepted evidence for this session — submit proof "
                "first (dhriti proof ...) or end it INCOMPLETE")
        result = self.sessions.end_success(session_id, note)
        self.ledger.record(
            "session_success", session_id=session_id,
            observed_payload={"accepted_evidence": accepted},
            action_taken="wall stays up until day release")
        return result

    def end_session_incomplete(self, session_id: str, note: str = "") -> dict:
        result = self.sessions.end_incomplete(session_id, note)
        self.ledger.record("session_incomplete", session_id=session_id)
        return result

    def run_aftermath(self, day_date_iso: str) -> dict:
        day = self.db.query_one(
            "SELECT * FROM day WHERE date=?", (day_date_iso,))
        if not day:
            raise RuntimeError("no such day")
        report = self.aftermath.day_report(day)
        out_dir = self.home / self.config.get("report", {}).get(
            "dir", "reports")
        paths = self.aftermath.write(report, out_dir, f"aftermath-{day_date_iso}")
        self.ledger.record(
            "aftermath_generated", observed_payload={
                "day": day_date_iso, "paths": paths})
        return paths


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
