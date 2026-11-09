"""Adapter registry: instantiates every provider from config.

Enabled-by-default: extension_bridge (E1, the implemented live layer).
Everything else is a deliberate opt-in with a setup guide (see
integrations/). The registry never silently fakes a provider.
"""

from pathlib import Path

from .base import Adapter, ArmingGate, ExternalCommandAdapter
from .enforcement.extension_bridge import ExtensionBridgeAdapter
from .enforcement.hosts_file import HostsFileAdapter
from .observation.activitywatch import ActivityWatchAdapter
from .observation.external import ScreenpipeAdapter, SysmonAdapter

_AUDIT_HINT = ("integrations/enforcement-audit/ — finish the manual audit, "
               "then set adapters.<name>.enabled=true and fill "
               "executable/commands")


def build_adapters(config: dict, home: Path,
                   bridge_policy_provider=None) -> list:
    adapters_cfg = config.get("adapters", {})
    adapters = []

    # E1 — the live, implemented layer
    adapters.append(ExtensionBridgeAdapter(
        config.get("bridge", {}), home, bridge_policy_provider))

    # E2 — hosts file (generates rules; apply/remove is a manual admin step)
    adapters.append(HostsFileAdapter(
        adapters_cfg.get("hosts_file", {}), home))

    # E2/E3 external enforcement tools — audited placeholders
    for tool in ("focusme", "cold_turkey", "plucky", "focuser"):
        adapters.append(ExternalCommandAdapter(
            adapters_cfg.get(tool, {}), home, _AUDIT_HINT, tool))

    # observation
    adapters.append(ActivityWatchAdapter(
        adapters_cfg.get("activitywatch", {}), home))
    adapters.append(SysmonAdapter(
        adapters_cfg.get("sysmon", {}), home))
    adapters.append(ScreenpipeAdapter(
        adapters_cfg.get("screenpipe", {}), home))
    return adapters


def build_gate(ledger=None) -> ArmingGate:
    return ArmingGate(ledger)
