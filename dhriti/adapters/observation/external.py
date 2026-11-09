"""Sysmon + Screenpipe observation adapters (audit-queue placeholders).

Neither is live in the Lite tier. Both follow the placeholder pattern:
config-driven, probed, honest, with setup guides.

  Sysmon (dossier 5.2 / audit item 6): the adapter ships a narrow
  config (integrations/sysmon/dhriti-sysmon-config.xml — process
  create/terminate + parent + DNS only) and parses exported event CSV/
  JSON from a directory you configure. Installing Sysmon itself is a
  manual admin step; never run verbose research profiles continuously.

  Screenpipe (audit item 7): opt-in rich capture; probe only checks the
  local HTTP API. Run a controlled 60–90 minute trial and measure
  CPU/RAM/disk before considering it (dossier D-011).
"""

import csv
import json
from pathlib import Path

import urllib.request

from ...models import ProbeResult
from ..base import Adapter


class SysmonAdapter(Adapter):
    name = "sysmon"
    role = "observation"
    capabilities = ["process_creation", "process_termination",
                    "parent_process", "dns_queries"]
    requirements = {"sysmon": "manual install (admin)",
                    "export": "events exported to CSV/JSON dir"}

    def __init__(self, config: dict, home: Path):
        super().__init__(config, home)
        self.export_dir = Path(config.get("export_dir") or "")

    def probe(self) -> ProbeResult:
        if not self.config.get("enabled"):
            return ProbeResult(
                "NOT_INSTALLED", "disabled in config",
                hint="integrations/sysmon/SETUP.md")
        if not self.export_dir.is_dir():
            return ProbeResult(
                "NOT_INSTALLED",
                f"export dir not found: {self.export_dir}",
                hint="integrations/sysmon/SETUP.md")
        return ProbeResult("INSTALLED",
                           f"watching export dir {self.export_dir}")

    def arm(self, policy: dict) -> bool:
        self._armed = self.probe().status == "INSTALLED"
        return self._armed

    def disarm(self) -> bool:
        self._armed = False
        return True

    def poll(self, ledger, clock) -> int:
        """Parse new exports into the ledger (process provenance with
        GUIDs, never PIDs alone — dossier 7.2)."""
        if not self._armed:
            return 0
        ingested = 0
        for path in sorted(self.export_dir.glob("*.csv")):
            try:
                with path.open(newline="", encoding="utf-8",
                               errors="replace") as fh:
                    for row in csv.DictReader(fh):
                        ledger.record(
                            "process_event",
                            source_adapter="sysmon",
                            process_instance_id=row.get("ProcessGuid"),
                            observed_payload={
                                "event_id": row.get("EventID"),
                                "image": row.get("Image"),
                                "parent": row.get("ParentImage"),
                                "command_line": (row.get("CommandLine")
                                                 or "")[:500],
                                "utc_time": row.get("UtcTime"),
                            })
                        ingested += 1
            except Exception:
                continue
            # archive the parsed file so each export is ingested once
            archive = self.export_dir / "parsed"
            archive.mkdir(exist_ok=True)
            path.rename(archive / path.name)
        return ingested


class ScreenpipeAdapter(Adapter):
    name = "screenpipe"
    role = "observation"
    capabilities = ["screen_capture", "ocr", "app_switch_events"]
    requirements = {"screenpipe": "local install; licence review first"}

    def __init__(self, config: dict, home: Path):
        super().__init__(config, home)
        self.url = (config.get("url") or
                    "http://127.0.0.1:3030").rstrip("/")

    def probe(self) -> ProbeResult:
        if not self.config.get("enabled"):
            return ProbeResult(
                "NOT_INSTALLED", "disabled in config (deliberate)",
                hint="integrations/README.md — run the 60–90 min "
                     "controlled trial first (audit item 7)")
        try:
            request = urllib.request.Request(self.url + "/health")
            with urllib.request.urlopen(request, timeout=3) as resp:
                json.loads(resp.read().decode("utf-8"))
            return ProbeResult("INSTALLED", f"reachable at {self.url}")
        except Exception as exc:
            return ProbeResult("ERROR", str(exc))

    def arm(self, policy: dict) -> bool:
        self._armed = self.probe().status == "INSTALLED"
        return self._armed

    def disarm(self) -> bool:
        self._armed = False
        return True
