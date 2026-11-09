"""`dhriti health` — operational state in one screen (toolkit #1).

One screen, facts only: daemon, lock, chain, sqlite, day, session,
adapters, config drift, overall. The last line is OK / DEGRADED /
BROKEN and the exit code is 0 only when everything required is
healthy. The operator's answer to "is the system working?" — without
it, honesty is a guess.

Exit codes: 0 = OK, 1 = DEGRADED or BROKEN.
"""

import json
import os
from pathlib import Path
from typing import Optional

from .adapters.registry import build_adapters
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


class HealthReport:
    def __init__(self):
        self.lines: list = []
        self.overall = "OK"

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
        # An adapter disabled in config is a cold-state choice, not a
        # fault ([ok], disclosed). An adapter ENABLED but missing on the
        # machine is DEGRADED. A required adapter that cannot run is
        # BROKEN (handled by the arming gate at session time).
        adapters = build_adapters(config, home, None)
        daemon_running_flag = daemon_running
        for adapter in adapters:
            probe = adapter.probe()
            enabled = bool(adapter.config.get("enabled", True))
            if adapter.name == "extension_bridge" \
                    and not daemon_running_flag:
                report.check(
                    f"adapter.{adapter.name}", True,
                    "daemon not running (bridge dormant, not a fault)")
                continue
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

        # -- config drift (v0.4.0 form) -------------------------------------
        # Compares the freshly loaded config against itself; this only
        # detects load failure, not live drift. See v0.6.0 (Part 1 §9.2):
        # the check is replaced by a comparison against the daemon's
        # recorded fingerprint.
        try:
            disk_config = load_config(home)
            report.check(
                "config.drift", True,
                f"config loads (fingerprint {config_fingerprint(disk_config)[:12]}...)")
        except Exception as exc:
            report.check("config.drift", False,
                         f"config on disk does not load: {exc}")
    finally:
        if own_db:
            db.close()
    return report


def config_fingerprint(config: dict) -> str:
    """A stable hash of the config (D-050)."""
    import hashlib
    payload = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
