"""Adapter base + arming gate (dossier 3.1, 3.4, 11.2).

Every replaceable provider implements Adapter:

  probe()  -> INSTALLED / NOT_INSTALLED / ERROR (+ setup hint)
  arm(policy)   verify + activate; returns honest success
  disarm()      release restrictions
  status()      what it is actually doing right now

Arming gate rule: a session may only become ACTIVE when every REQUIRED
adapter reports armed. If an adapter is missing, that fact is disclosed
in the experiment record — the system never pretends a capability exists
(dossier 2.7: tamper-evident, not unbreakable; and 3.4: ARMING gate).

Placeholders follow one pattern everywhere: config-driven, probed, and
honest about NOT_INSTALLED, with a hint pointing at the setup guide.
"""

import subprocess
from pathlib import Path

from ..errors import AdapterError
from ..models import ArmingReport, ProbeResult


class Adapter:
    name = "abstract"
    role = "abstract"           # enforcement | observation
    capabilities = []
    requirements: dict = {}

    def __init__(self, config: dict, home: Path):
        self.config = config or {}
        self.home = Path(home)
        self._armed = False
        self._last_error = ""

    # -- interface -------------------------------------------------------------
    def probe(self) -> ProbeResult:  # pragma: no cover - overridden
        return ProbeResult("NOT_INSTALLED", "not implemented",
                           hint="docs/ARCHITECTURE.md")

    def arm(self, policy: dict) -> bool:  # pragma: no cover
        return False

    def disarm(self) -> bool:  # pragma: no cover
        return False

    def status(self) -> dict:
        return {"name": self.name, "role": self.role,
                "armed": self._armed,
                "probe": self.probe().status}

    def manifest(self) -> dict:
        """Dossier 11.2 capability manifest."""
        return {
            "provider": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "requirements": self.requirements,
        }


class ExternalCommandAdapter(Adapter):
    """The well-made placeholder for external enforcement tools
    (FocusMe, Cold Turkey, Plucky, Focuser).

    Config (dhriti.config.json -> adapters.<name>):
      enabled      false until you finish the manual audit
      executable   absolute path or command name; presence = probe
      arm_cmd      argv list run to activate a block
      disarm_cmd   argv list run to release
      probe_cmd    optional argv list; exit 0 = healthy

    Until `enabled: true` AND the executable exists, probe() reports
    NOT_INSTALLED and arm() refuses — with a pointer to the audit queue.
    """

    def __init__(self, config: dict, home: Path, setup_hint: str,
                 name: str):
        super().__init__(config, home)
        self.name = name
        self.setup_hint = setup_hint

    def probe(self) -> ProbeResult:
        if not self.config.get("enabled"):
            return ProbeResult(
                "NOT_INSTALLED",
                "disabled in config (deliberate: audit pending)",
                hint=self.setup_hint)
        exe = self.config.get("executable") or ""
        if not exe:
            return ProbeResult("NOT_INSTALLED", "no executable configured",
                               hint=self.setup_hint)
        try:
            subprocess.run([exe], capture_output=True, timeout=10)
            return ProbeResult("INSTALLED", f"executable found: {exe}")
        except FileNotFoundError:
            return ProbeResult("NOT_INSTALLED",
                               f"executable not found: {exe}",
                               hint=self.setup_hint)
        except subprocess.TimeoutExpired:
            return ProbeResult("INSTALLED",
                               f"executable found (long-running): {exe}")
        except Exception as exc:
            return ProbeResult("ERROR", str(exc), hint=self.setup_hint)

    def _run(self, cmd, label) -> bool:
        if not cmd:
            return False
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, shell=False)
            ok = proc.returncode == 0
            if not ok:
                self._last_error = (f"{label} exit={proc.returncode}: "
                                    f"{proc.stderr[-500:]}")
            return ok
        except Exception as exc:
            self._last_error = f"{label}: {exc}"
            return False

    def arm(self, policy: dict) -> bool:
        if self.probe().status != "INSTALLED":
            raise AdapterError(
                f"{self.name}: refusing to arm — probe is not INSTALLED "
                f"({self.setup_hint})")
        ok = self._run(self.config.get("arm_cmd") or [], "arm")
        self._armed = ok
        return ok

    def disarm(self) -> bool:
        ok = self._run(self.config.get("disarm_cmd") or [], "disarm")
        self._armed = False
        return ok


class ArmingGate:
    """Sessions go ACTIVE only through this gate."""

    def __init__(self, ledger=None):
        self.ledger = ledger

    def arm_all(self, adapters: list, policy: dict,
                required: list) -> ArmingReport:
        report = ArmingReport()
        for adapter in adapters:
            is_required = adapter.name in required
            if not adapter.config.get("enabled", True):
                report.skipped.append(adapter.name)
                continue
            try:
                armed = adapter.arm(policy)
            except AdapterError as exc:
                armed = False
                if self.ledger:
                    self.ledger.record(
                        "adapter_arm_failed", source_adapter=adapter.name,
                        observed={"error": str(exc)},
                        action_taken="disclosed")
            if armed:
                report.armed.append(adapter.name)
            elif is_required:
                report.failed.append(adapter.name)
            else:
                report.skipped.append(adapter.name)
        if self.ledger:
            self.ledger.record(
                "adapters_armed",
                observed={"armed": report.armed,
                                  "failed": report.failed,
                                  "skipped": report.skipped},
                action_taken="disclosed")
        return report
