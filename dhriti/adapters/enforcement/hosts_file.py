"""E2 enforcement: hosts-file DNS blocking (manual apply/remove).

What the adapter does (safe, automatic):
  * renders <home>/hosts/dhriti-block.txt with every blocked domain from
    the active policy, plus meta + restore markers.

What stays manual on purpose (needs an elevated shell on Windows):
  * applying the block (integrations/windows/hosts-block.ps1 -Apply)
  * removing the block (hosts-block.ps1 -Restore)
  * marking it applied (the ps1 writes the APPLIED marker)

probe() checks the marker; status() compares expected vs applied so the
experiment record can never mistake "rules generated" for "rules live".
"""

import json
import time
from pathlib import Path

from ...models import ProbeResult
from ..base import Adapter


class HostsFileAdapter(Adapter):
    name = "hosts_file"
    role = "enforcement"
    capabilities = ["dns_blocking_e2"]
    requirements = {"admin": "manual elevated PowerShell apply"}

    def __init__(self, config: dict, home: Path):
        super().__init__(config, home)
        self.hosts_dir = home / "hosts"
        self.marker = self.hosts_dir / "APPLIED"

    def probe(self) -> ProbeResult:
        if not self.config.get("enabled"):
            return ProbeResult("NOT_INSTALLED", "disabled in config",
                               hint="integrations/windows/hosts-block.ps1")
        if self.marker.exists():
            return ProbeResult("INSTALLED", "hosts block marked APPLIED")
        return ProbeResult(
            "NOT_INSTALLED",
            "block file generated but not applied (needs admin)",
            hint="run integrations/windows/hosts-block.ps1 -Apply")

    def render(self, blocked_domains: list) -> Path:
        self.hosts_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        lines = [
            f"# Dhriti E2 hosts block — generated {stamp}",
            "# Apply/remove via integrations/windows/hosts-block.ps1",
        ]
        entries = []
        for domain in sorted(set(blocked_domains)):
            domain = str(domain).strip().lower().lstrip(".")
            if domain:
                entries.append(f"0.0.0.0 {domain}")
                entries.append(f"0.0.0.0 www.{domain}")
        lines.extend(entries)
        out = self.hosts_dir / "dhriti-block.txt"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        meta = {"generated_at": stamp,
                "domains": sorted(set(str(d).strip().lower()
                                      for d in blocked_domains))}
        (self.hosts_dir / "meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8")
        return out

    def arm(self, policy: dict) -> bool:
        domains = []
        if isinstance(policy, dict):
            domains = (policy.get("blocked_domains")
                       or (policy.get("extension_rules") or {}).get(
                           "blocked_domains")
                       or [])
        self.render(domains)
        self._armed = self.marker.exists()
        return self._armed

    def disarm(self) -> bool:
        # Removing system hosts entries stays manual (admin). We only
        # regenerate an empty block file; the ps1 -Restore clears it.
        self.render([])
        self._armed = False
        return True

    def status(self) -> dict:
        base = super().status()
        meta_path = self.hosts_dir / "meta.json"
        expected = []
        if meta_path.exists():
            try:
                expected = json.loads(
                    meta_path.read_text(encoding="utf-8")).get("domains", [])
            except Exception:
                pass
        base["expected_domains"] = len(expected)
        base["applied"] = self.marker.exists()
        if expected and not self.marker.exists():
            base["disclosure"] = (
                "hosts rules generated but NOT applied at OS level — "
                "E2 is not active")
        return base
