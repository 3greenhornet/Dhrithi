"""`dhriti health` — operational state in one screen (toolkit #1).

One screen, facts only: daemon, lock, chain, sqlite, day, session,
adapters, config drift, overall. The last line is OK / DEGRADED /
BROKEN and the exit code is 0 only when everything required is
healthy. The operator's answer to "is the system working?" — without
it, honesty is a guess.

v0.6.0 (Bug A): the extension bridge is probed over HTTP, not through
the adapter instance — a CLI process has no daemon, so the adapter
probe could only ever report NOT_INSTALLED and healthy systems showed
DEGRADED.

Exit codes: 0 = OK, 1 = DEGRADED or BROKEN.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .constants import load_config
from .db import Database
from .ledger import Ledger
from .timeutil import Clock, RealClock, parse_iso


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _probe_extension_bridge(report, home: Path,
                            config: dict, daemon_running: bool) -> str:
    """Bug A fix (v0.6.0): probe the bridge over HTTP with the token
    from <home>/bridge_token — never through the adapter instance
    (a CLI process has no daemon; the adapter probe could only lie).
    Returns the probe outcome for the health_check_run event:
    ok | bridge_down | token_rejected | daemon_not_running."""
    bridge_cfg = config.get("bridge", {})
    token_file = home / bridge_cfg.get("token_file", "bridge_token")
    port = int(bridge_cfg.get("port", 7311))
    if not token_file.exists():
        report.check(
            "adapter.extension_bridge", True,
            "daemon not running (bridge dormant, not a fault)")
        return "daemon_not_running"
    token = token_file.read_text(encoding="utf-8").strip()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/status",
        headers={"X-Dhriti-Token": token})
    try:
        with urllib.request.urlopen(request, timeout=2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if "day" in payload:
            report.check(
                "adapter.extension_bridge", True,
                f"bridge responded (day state: {payload['day']})")
            return "ok"
        report.check(
            "adapter.extension_bridge", False,
            "bridge responded without a day state — daemon older "
            "than the bridge contract")
        return "bridge_down"
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            report.check(
                "adapter.extension_bridge", False,
                "bridge up, token rejected — run 'dhriti token rotate' "
                "or re-paste in extension/config.js")
            return "token_rejected"
        report.check(
            "adapter.extension_bridge", False,
            f"bridge returned HTTP {exc.code}")
        return "bridge_down"
    except (urllib.error.URLError, OSError, TimeoutError):
        if daemon_running:
            report.check(
                "adapter.extension_bridge", False,
                "daemon lock present but bridge not responding")
            return "bridge_down"
        report.check(
            "adapter.extension_bridge", True,
            "daemon not running (bridge dormant, not a fault)")
        return "daemon_not_running"


class HealthReport:
    def __init__(self):
        self.lines: list = []
        self.overall = "OK"
        self.extension_bridge_probe = "daemon_not_running"

    def check(self, name: str, ok: bool, message: str,
              degraded_when_false: bool = True):
        """Record one line. ok=True -> [ok  ]; otherwise [warn] (or
        [FAIL] when the check is required — failures always escalate
        the overall verdict)."""
        if ok:
            self.lines.append(f"[ok  ] {name}: {message}")
        elif degraded_when_false:
            self.lines.append(f"[warn] {name}: {message}")
            if self.overall == "OK":
                self.overall = "DEGRADED"
        else:
            self.lines.append(f"[FAIL] {name}: {message}")
            self.overall = "BROKEN"
        return ok


def build_health(home: Path, config: Optional[dict] = None,
                 clock: Optional[Clock] = None,
                 db: Optional[Database] = None,
                 ledger: Optional[Ledger] = None) -> HealthReport:
    home = Path(home)
    config = config or load_config(home)
    clock = clock or RealClock()
    own_db = db is None
    db = db or Database(home / "dhriti.sqlite3")
    ledger = ledger or Ledger(db, clock)
    report = HealthReport()

    try:
        # -- daemon / lock ------------------------------------------------
        lock_path = home / "daemon.lock"
        daemon_running = False
        if lock_path.exists():
            pid = lock_path.read_text(encoding="utf-8").strip()
            daemon_running = bool(pid and _pid_alive(int(pid)))
            report.check(
                "daemon.lock", daemon_running,
                f"held (pid {pid})" if daemon_running
                else f"stale lock (pid {pid} not alive)")
        else:
            report.check("daemon.lock", True, "free (daemon not running)")

        # -- chain ---------------------------------------------------------
        chain = ledger.verify_chain()
        report.check("chain", chain["ok"],
                     f"OK ({chain['checked']} events, head "
                     f"{ledger.head()['row_hash'][:12]}...)"
                     if chain["ok"] else
                     f"BROKEN at seq {chain['first_bad_seq']} "
                     f"({chain['reason']})", degraded_when_false=False)

        # -- sqlite ----------------------------------------------------------
        report.check("sqlite", db.integrity_check(),
                     "OK (integrity_check passed)",
                     degraded_when_false=False)

        # -- today / session --------------------------------------------------
        tz_day = None
        day_row = db.query_one(
            "SELECT * FROM day ORDER BY date DESC LIMIT 1")
        if day_row:
            report.check(
                "day", True,
                f"{day_row['date']} — {day_row['state']} "
                f"(window {day_row['window_start_at'][11:16]}–"
                f"{day_row['window_end_at'][11:16]} UTC)")
        active = db.query_one(
            "SELECT * FROM session WHERE state='ACTIVE' "
            "ORDER BY started_at DESC LIMIT 1")
        report.check("session", True,
                     f"ACTIVE ({active['id'][:8]}) — {active['task']}"
                     if active else "none active")

        # -- adapters -------------------------------------------------------
        # Bug A (v0.6.0): the extension bridge is probed over HTTP with
        # the real token; the other adapters keep the config-aware probe
        # (disabled in config = a cold-state choice, not a fault;
        # enabled but missing = DEGRADED).
        report.extension_bridge_probe = _probe_extension_bridge(
            report, home, config, daemon_running)
        from .adapters.registry import build_adapters
        for adapter in build_adapters(config, home, None):
            if adapter.name == "extension_bridge":
                continue  # probed above
            probe = adapter.probe()
            enabled = bool(adapter.config.get("enabled", True))
            if not enabled:
                report.check(
                    f"adapter.{adapter.name}", True,
                    "disabled in config (cold-state choice)")
                continue
            report.check(
                f"adapter.{adapter.name}",
                probe.status == "INSTALLED",
                f"{probe.status}"
                + (f" ({probe.detail})" if probe.detail else "")
                + (f" — {probe.hint}" if probe.status != "INSTALLED"
                   and probe.hint else ""))

        # -- config drift (v0.6.0, Part 1 §9.2) -----------------------------
        # Compares the config on disk against the fingerprint the daemon
        # recorded at its start (daemon_config_fingerprint in meta). The
        # v0.5.0 form compared the freshly loaded config against itself
        # and could never fail — a dead check.
        try:
            disk_fp = config_fingerprint(load_config(home))
        except Exception as exc:
            report.check("config.drift", False,
                         f"config on disk does not load: {exc}")
        else:
            running_fp = db.get_meta("daemon_config_fingerprint")
            if running_fp is None:
                report.check(
                    "config.drift", True,
                    "no daemon fingerprint recorded (daemon has not run)")
            elif disk_fp == running_fp:
                report.check(
                    "config.drift", True,
                    "config on disk matches the running daemon")
            else:
                report.check(
                    "config.drift", False,
                    "config edited on disk since the daemon started "
                    "(restart to apply)")
    finally:
        if own_db:
            db.close()
    return report


def config_fingerprint(config: dict) -> str:
    """A stable hash of the config (D-050)."""
    import hashlib
    payload = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
