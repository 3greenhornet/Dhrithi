"""ActivityWatch observation adapter (dossier 5.2).

A real REST client for a local ActivityWatch instance (default
http://127.0.0.1:5600). It is a PLACEHOLDER-BY-CONFIG: disabled until
you install ActivityWatch (integrations/activitywatch/SETUP.md) and set
adapters.activitywatch.enabled=true. When enabled, the daemon pulls
window/afk events between ticks and folds them into the normalized
ledger — nothing leaves the machine.

Dossier D-009: do not run redundant trackers. This adapter is the
"one light observer" of the Lite tier; compare with a minimal native
observer before adding more.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

from ...models import ProbeResult
from ..base import Adapter


class ActivityWatchAdapter(Adapter):
    name = "activitywatch"
    role = "observation"
    capabilities = ["window_events", "afk_events", "browser_events"]
    requirements = {"activitywatch": ">=0.12 local install"}

    def __init__(self, config: dict, home: Path):
        super().__init__(config, home)
        self.url = (config.get("url") or
                    "http://127.0.0.1:5600").rstrip("/")
        self._last_poll = None

    def _get(self, path: str, timeout: float = 3.0):
        request = urllib.request.Request(
            self.url + path, headers={"User-Agent": "dhriti/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def probe(self) -> ProbeResult:
        if not self.config.get("enabled"):
            return ProbeResult(
                "NOT_INSTALLED", "disabled in config",
                hint="integrations/activitywatch/SETUP.md")
        try:
            info = self._get("/api/0/info")
            return ProbeResult("INSTALLED",
                               f"ActivityWatch {info.get('version', '?')}")
        except Exception as exc:
            return ProbeResult("ERROR", f"cannot reach {self.url}: {exc}",
                               hint="is ActivityWatch running?")

    def arm(self, policy: dict) -> bool:
        # Observation adapters do not enforce; "armed" = polling enabled.
        self._armed = self.probe().status == "INSTALLED"
        return self._armed

    def disarm(self) -> bool:
        self._armed = False
        return True

    def poll(self, ledger, clock) -> int:
        """Pull events since the last poll; write normalized ledger rows.
        Returns the number of events ingested."""
        if not self._armed:
            return 0
        try:
            buckets = self._get("/api/0/buckets/") or {}
        except Exception:
            return 0
        ingested = 0
        for bucket_id, meta in buckets.items():
            if not any(k in bucket_id for k in ("window", "afk", "web")):
                continue
            since = self._last_poll.iso() if self._last_poll else \
                clock.now_utc().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            try:
                events = self._get(
                    f"/api/0/buckets/{bucket_id}/events?start={since}")
            except Exception:
                continue
            for event in events or []:
                payload = event.get("data", {})
                event_type = ("afk_heartbeat" if "afk" in bucket_id
                              else "window_focus")
                ledger.record(
                    event_type,
                    source_adapter="activitywatch",
                    source_version=str(meta.get("created", ""))[:40],
                    observed_payload={
                        "bucket": bucket_id,
                        "app": payload.get("app"),
                        "title": payload.get("title"),
                        "duration_s": round(
                            float(event.get("duration", 0) or 0), 2),
                    },
                    telemetry_quality="OK")
                ingested += 1
        self._last_poll = clock.now_utc()
        return ingested
