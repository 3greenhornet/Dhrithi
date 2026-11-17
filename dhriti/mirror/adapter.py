"""The mirror adapter (Part 3 §3.1): the third adapter role.

The mirror is NOT in the arming gate (PDF Part 2 §2.2): it enforces
nothing. Its lifecycle is ingestion (poll), surfacing (suggest), and
honest status (token days remaining, quota, item counts).
"""

from datetime import timedelta
from pathlib import Path
from typing import Optional

from ..adapters.base import Adapter
from ..models import ProbeResult
from ..timeutil import parse_iso, to_iso
from . import events as ev


class ViduraMirrorAdapter(Adapter):
    name = "vidura_mirror"
    role = "mirror"
    capabilities = ["youtube_ingestion", "content_classification",
                    "avoidance_ranking", "recall_protocol",
                    "reentry_declaration", "confrontation_file"]

    def __init__(self, config: dict, home: Path,
                 policy_provider=None, db=None, clock=None,
                 ledger=None):
        super().__init__(config, home)
        self.db = db
        self.clock = clock
        self.ledger = ledger
        self._store = None
        self._ingest = None
        self._surface = None
        self._last_poll_at = None

    # -- lazy sub-services ------------------------------------------------------
    @property
    def store(self):
        if self._store is None:
            from .store import MirrorStore
            self._store = MirrorStore(self.db, self.config, self.clock,
                                      self.ledger)
        return self._store

    @property
    def ingest(self):
        if self._ingest is None:
            from .ingest import YouTubeIngest
            self._ingest = YouTubeIngest(self.db, self.config,
                                         self.home, self.clock,
                                         self.ledger)
        return self._ingest

    @property
    def surface(self):
        if self._surface is None:
            from .surface import SurfaceService
            self._surface = SurfaceService(self.db, self.config,
                                           self.clock, self.ledger,
                                           store=self.store)
        return self._surface

    # -- the adapter contract ------------------------------------------------------
    def probe(self) -> ProbeResult:
        if not self.config.get("enabled", False):
            return ProbeResult(
                "NOT_INSTALLED",
                "mirror disabled in config (cold-state choice; L-6)",
                hint="docs/MIRROR.md")
        if not self.ingest.has_refresh_token():
            return ProbeResult(
                "NOT_INSTALLED",
                "enabled but no OAuth refresh token",
                hint="run: dhriti mirror auth")
        return ProbeResult(
            "INSTALLED",
            f"{self.store.unopened_count()} unopened item(s)")

    def arm(self, policy: dict) -> bool:
        # arming = ingestion allowed; the mirror never enforces
        self._armed = bool(self.config.get("enabled", False))
        return self._armed

    def disarm(self) -> bool:
        self._armed = False
        return True

    def status(self) -> dict:
        probe = self.probe()
        info = {"name": self.name, "role": self.role,
                "armed": self._armed, "probe": probe.status}
        if self.config.get("enabled", False):
            info["unopened"] = self.store.unopened_count()
            info["quota_used_today"] = self.ingest.quota_used_today
            budget = int(self.config.get("youtube", {}).get(
                "quota_budget_per_day", 8000))
            info["quota_budget"] = budget
            info["token_valid"] = self.ingest.has_refresh_token()
        return info

    # -- the mirror contract (Part 3 §3.1) -----------------------------------
    def poll(self, ledger, clock) -> int:
        """Ingestion tick: each enabled source, once per interval."""
        if not self.config.get("enabled", False):
            return 0
        interval = int(self.config.get(
            "ingestion_interval_minutes", 15))
        now = clock.now_utc()
        if self._last_poll_at is not None:
            if now < self._last_poll_at + timedelta(
                    minutes=interval):
                return 0
        self._last_poll_at = now
        ingested = 0
        for source in self.store.sources():
            if not source["enabled"]:
                continue
            report = self.ingest.ingest(self.store, source)
            if report.get("ok"):
                ingested += report["ingested"]
            elif self.ledger is not None:
                self.ledger.record(
                    ev.MIRROR_INGESTION_RETRY,
                    observed={"source": source["display_name"],
                              "reason": report.get("reason", "")},
                    action_taken="ingestion pass failed; next tick")
        return ingested

    def suggest(self, minutes=None, category=None,
                state=None) -> Optional[dict]:
        return self.surface.suggest(minutes=minutes, category=category,
                                    state=state)

    def record_choice(self, item_id: str, choice: str,
                      reason: str = "") -> dict:
        return self.store.record_choice(item_id, choice, reason)

    def record_progress(self, item_id: str, fraction: float) -> dict:
        return self.store.record_progress(item_id, fraction)

    def explain(self, item_id: str) -> dict:
        """The `dhriti explain <item>` mirror view: the item's full
        event history from the chain, plus its state."""
        item = self.store.get_item(item_id)
        if item is None:
            return {"error": f"no item {item_id}"}
        history = []
        if self.ledger is not None:
            for row in self.ledger.events():
                if item_id[:8] not in (row["observed_payload"] or ""):
                    continue
                history.append({
                    "seq": row["seq"],
                    "at": row["occurred_at_utc"],
                    "type": row["event_type"],
                    "observed": row["observed_payload"][:200],
                })
        return {"item": {k: item[k] for k in (
            "title", "category", "saved_at_utc", "opened_at",
            "completed_at", "abandoned_at", "times_resaved",
            "dismiss_count", "current_stability_days")},
            "history": history}
