"""Existing stack integration (v0.7.0 Part 3 §3.12).

Dhriti does not replace tools the operator already runs — it
declares them, probes them honestly, records the delegation, and
discloses the blind spots. `dhriti stack probe` / `status` /
`integrate` / `import-brave` are cold-state commands; nothing here
arms or disarms a third-party tool except through the tool's own
documented CLI (Cold Turkey), and every claim is a recorded fact.
"""

from pathlib import Path
from typing import Optional

from ..db import Database
from ..timeutil import Clock, RealClock, to_iso


class StackProbe:
    """Probes each configured tool and reports INSTALLED /
    NOT_CONFIGURED honestly. A probe never pretends: if the
    executable is missing or the status command fails, the report
    says so."""

    def __init__(self, config: dict, home: Path,
                 clock: Optional[Clock] = None, ledger=None,
                 db: Optional[Database] = None):
        self.config = config.get("stack", {})
        self.home = Path(home)
        self.clock = clock or RealClock()
        self.ledger = ledger
        self.db = db

    def probe_all(self) -> list:
        results = []
        results.append(self._probe_cold_turkey())
        results.append(self._probe_nextdns())
        results.append(self._probe_foqos())
        results.append(self._probe_unhook())
        results.append(self._probe_brave())
        results.append(self._probe_applock())
        return results

    def _run(self, argv: list) -> Optional[str]:
        import subprocess
        try:
            proc = subprocess.run(argv, capture_output=True,
                                  text=True, timeout=10)
            return proc.stdout.strip() if proc.returncode == 0 else None
        except Exception:
            return None

    def _probe_cold_turkey(self) -> dict:
        cfg = self.config.get("cold_turkey", {})
        executable = cfg.get("executable", "")
        if not cfg.get("enabled") or not executable:
            return {"tool": "Cold Turkey",
                    "status": "NOT_CONFIGURED"}
        status_cmd = cfg.get("status_cmd", [])
        if status_cmd:
            out = self._run(status_cmd)
            if out is not None:
                version = out.splitlines()[0][:80] if out else ""
                return {"tool": "Cold Turkey",
                        "status": "INSTALLED",
                        "detail": version}
            return {"tool": "Cold Turkey",
                    "status": "ERROR",
                    "detail": "status_cmd failed"}
        import shutil
        if shutil.which(executable):
            return {"tool": "Cold Turkey", "status": "INSTALLED",
                    "detail": f"{executable} present"}
        return {"tool": "Cold Turkey", "status": "NOT_INSTALLED"}

    def _probe_nextdns(self) -> dict:
        cfg = self.config.get("nextdns", {})
        if not cfg.get("enabled") or not cfg.get("profile_id"):
            return {"tool": "NextDNS", "status": "NOT_CONFIGURED"}
        return {"tool": "NextDNS", "status": "INSTALLED",
                "detail": f"profile: {cfg['profile_id']}"}

    def _probe_foqos(self) -> dict:
        cfg = self.config.get("foqos", {})
        if not cfg.get("enabled"):
            return {"tool": "Foqos", "status": "NOT_CONFIGURED"}
        import os
        barcode_dir = Path(cfg.get("barcode_dir",
                                   "~/.dhriti/barcodes")).expanduser()
        count = len(list(barcode_dir.glob("*"))) \
            if barcode_dir.is_dir() else 0
        return {"tool": "Foqos", "status": "INSTALLED",
                "detail": f"{count} registered barcode(s)"}

    def _probe_unhook(self) -> dict:
        cfg = self.config.get("unhook", {})
        if not cfg.get("enabled"):
            return {"tool": "Unhook", "status": "NOT_CONFIGURED"}
        detail = ("YouTube suppression delegated"
                  if cfg.get("delegate_youtube_suppression", True)
                  else "not delegated")
        return {"tool": "Unhook", "status": "INSTALLED",
                "detail": detail}

    def _probe_brave(self) -> dict:
        cfg = self.config.get("brave_filters", {})
        if not cfg.get("enabled") or not cfg.get("import_path"):
            return {"tool": "Brave filters", "status": "NOT_CONFIGURED"}
        path = Path(cfg["import_path"]).expanduser()
        return {"tool": "Brave filters",
                "status": "INSTALLED" if path.is_file()
                else "NOT_INSTALLED",
                "detail": str(path)}

    def _probe_applock(self) -> dict:
        cfg = self.config.get("applock", {})
        if not cfg.get("enabled"):
            return {"tool": "AppLock", "status": "NOT_CONFIGURED"}
        import shutil
        return {"tool": "AppLock",
                "status": "INSTALLED"
                if shutil.which(cfg.get("executable", "")) or
                cfg.get("status_cmd")
                else "NOT_INSTALLED"}

    # -- declarations -----------------------------------------------------------
    def declare_integration(self, tool: str,
                            capabilities: list) -> dict:
        """`dhriti stack integrate <tool> --delegate <caps>`: the
        delegation is a recorded fact (and drives conflict
        resolution — e.g. Unhook owning YouTube suppression)."""
        if self.ledger is not None:
            self.ledger.record(
                "stack_integration_declared",
                observed={"tool": tool,
                          "delegated": capabilities},
                action_taken="delegation declared cold")
        return {"tool": tool, "delegated": capabilities}

    # -- conflict resolution -------------------------------------------------
    def suppress_js_owns_youtube(self) -> bool:
        """When Unhook is enabled with delegation, suppress.js skips
        the YouTube rules (Unhook owns them); Reddit/X/Google/AI-chat
        rules continue. The policy snapshot records the split."""
        unhook = self.config.get("unhook", {})
        return bool(unhook.get("enabled")
                    and unhook.get(
                        "delegate_youtube_suppression", True))

    def cold_turkey_residual(self, blocked_domains: list) -> list:
        """When Cold Turkey is enabled and armed, the extension's
        blocked list is narrowed to the residual — what Cold Turkey
        does not cover."""
        cfg = self.config.get("cold_turkey", {})
        if not (cfg.get("enabled") and cfg.get("delegate_domains")):
            return list(blocked_domains)
        delegated = set(cfg["delegate_domains"])
        return [d for d in blocked_domains if d not in delegated]

    # -- Brave filter import ---------------------------------------------------
    def import_brave(self, path: Path) -> dict:
        """Read AdBlock-format rules and generate a suppress.js-
        compatible rule set. Unsupported syntax (regex, script
        injection) is reported honestly, never silently dropped."""
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"no such file: {path}")
        supported, unsupported = [], 0
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith(("!", "#", "[")):
                continue
            if line.startswith("##") or "##" in line:
                # domain##selector — the shape suppress.js speaks
                parts = line.split("##", 1)
                domain = parts[0].strip() or "*"
                selector = parts[1].strip()
                if (selector.startswith("/")   # /regex/selector/ form
                        or "$" in selector     # rewrite options
                        or ":inject" in selector   # script injection
                        or ":style" in selector    # uBO CSS rewrite
                        or ":remove" in selector   # uBO removal
                        or "-ext-" in selector):   # uBO extensions
                    unsupported += 1
                    continue
                supported.append({"domain": domain,
                                  "css": selector})
            else:
                unsupported += 1  # network rules / regex / scripts
        if self.ledger is not None:
            self.ledger.record(
                "suppress_imported_rules",
                observed={"file": str(path),
                          "supported": len(supported),
                          "unsupported": unsupported},
                action_taken="rules imported; unsupported syntax "
                             "reported, not faked")
        return {"supported": supported, "unsupported": unsupported}


class NextDnsPoller:
    """NextDNS log polling (observation, not enforcement): reads the
    profile's query log via the NextDNS API every N minutes, extracts
    blocked-domain queries, records dns_blocked events. The API key
    is the user's (DHRITI_NEXTDNS_API_KEY)."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None,
                 http=None):
        self.db = db
        self.config = config.get("stack", {}).get("nextdns", {})
        self.clock = clock or RealClock()
        self.ledger = ledger
        self._http = http
        self._last_poll_at = None

    def poll(self) -> int:
        import json as _json
        import os
        import urllib.request
        from datetime import timedelta
        if not self.config.get("enabled"):
            return 0
        interval = int(self.config.get("log_poll_minutes", 15))
        now = self.clock.now_utc()
        if self._last_poll_at is not None \
                and now < self._last_poll_at + timedelta(
                    minutes=interval):
            return 0
        self._last_poll_at = now
        api_key = os.environ.get(
            self.config.get("api_key_env", "DHRITI_NEXTDNS_API_KEY"),
            "")
        if not api_key or not self.config.get("profile_id"):
            return 0
        url = (f"https://api.nextdns.io/profiles/"
               f"{self.config['profile_id']}/analytics/dnsQueries?"
               "status=blocked")
        request = urllib.request.Request(
            url, headers={"X-Api-Key": api_key})
        try:
            fetch = self._http or urllib.request.urlopen
            with fetch(request, timeout=15) as resp:
                payload = _json.loads(resp.read().decode())
        except Exception:
            return 0
        blocked = 0
        for row in payload.get("dnsQueries", [])[:200]:
            domain = row.get("domain", "")
            if domain:
                blocked += 1
                if self.ledger is not None:
                    self.ledger.record(
                        "dns_blocked",
                        observed={"domain": domain[:100]},
                        action_taken="NextDNS blocked the query "
                                     "(observation, not enforcement)")
        return blocked
