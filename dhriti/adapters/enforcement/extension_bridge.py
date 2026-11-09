"""E1 enforcement: the extension bridge.

Arming = publishing the current policy snapshot where the Dhriti Wall
extension will fetch it (the daemon's HTTP bridge), plus an honest
liveness check: has the extension POSTed anything recently? If the
extension was removed or never installed, status() discloses
'extension not seen' so the experiment record shows the truth.

This is deliberately the ONLY enforcement adapter that is live by
default: it is fully local, needs no admin rights, and its removal is
recorded rather than prevented (tamper-evident, not tamper-proof).
"""

import time
from pathlib import Path

from ...models import ProbeResult
from ...timeutil import now_utc, to_iso
from ..base import Adapter


class ExtensionBridgeAdapter(Adapter):
    name = "extension_bridge"
    role = "enforcement"
    capabilities = ["website_blocking_e1", "event_ingest",
                    "policy_fetch", "fail_safe_cache"]
    requirements = {"chrome_extension": "extension/ (load unpacked)",
                    "local_bridge": "127.0.0.1 (daemon)"}

    def __init__(self, config: dict, home: Path, policy_provider=None):
        super().__init__(config, home)
        # policy_provider: callable -> current extension policy dict
        self.policy_provider = policy_provider
        self.last_extension_seen_file = home / "extension_last_seen"
        self.stale_after_seconds = 300  # 5 min without a POST = disclose
        self._last_seen_mono = None

    def probe(self) -> ProbeResult:
        if self.policy_provider is None:
            return ProbeResult(
                "NOT_INSTALLED",
                "bridge not running (start the daemon)",
                hint="extension/INSTALL.md")
        return ProbeResult("INSTALLED", "bridge policy provider attached")

    def arm(self, policy: dict) -> bool:
        # Publishing happens via the bridge thread; arming here means:
        # a provider exists and the policy snapshot carries enforcement.
        if self.policy_provider is None:
            return False
        published = self.policy_provider() or {}
        if not published.get("version"):
            return False
        self._armed = True
        return True

    def disarm(self) -> bool:
        # The bridge serves a dormant (enforce=false) policy when no
        # session/day is active; the extension's cached policy also
        # expires (TTL) so a dead daemon cannot lock the browser forever.
        self._armed = False
        return True

    def note_extension_seen(self):
        self._last_seen_mono = time.monotonic()
        try:
            self.last_extension_seen_file.parent.mkdir(
                parents=True, exist_ok=True)
            self.last_extension_seen_file.write_text(
                f"{to_iso(now_utc())}|{self._last_seen_mono}",
                encoding="utf-8")
        except Exception:
            pass

    def extension_seen_recently(self) -> bool:
        if self._last_seen_mono is not None:
            try:
                return (time.monotonic() - self._last_seen_mono) < \
                    self.stale_after_seconds
            except Exception:
                pass
        try:
            stamp = self.last_extension_seen_file.read_text(
                encoding="utf-8").strip().split("|")
            mono = float(stamp[1])
            return (time.monotonic() - mono) < self.stale_after_seconds
        except Exception:
            return False

    def status(self) -> dict:
        base = super().status()
        base["extension_seen_recently"] = self.extension_seen_recently()
        if not base["extension_seen_recently"]:
            base["disclosure"] = (
                "extension has not reported recently — if you removed it, "
                "that removal is recorded, not prevented")
        return base
