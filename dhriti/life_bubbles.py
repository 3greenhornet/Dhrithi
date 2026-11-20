"""Dhriti Life Mirror Thought-Bubbles Scheduler (D-092 / L-11).

Surfaces cold-declared offline alternatives as non-coercive thought bubbles
during Art Mode and Decompression time.
Uniform-random selection, silent expiry, zero optimization.
"""

from __future__ import annotations

import datetime as _dt
import random
import uuid
from typing import Optional, Dict, Any, List


class BubbleScheduler:
    """Uniform-random recall of cold-declared alternatives.
    The selection is NOT optimized or ranked -- that is the design law (L-8 / D-092).
    """

    def __init__(self, db, clock, ledger, cfg: Optional[Dict[str, Any]] = None):
        self.db = db
        self.clock = clock
        self.ledger = ledger
        cfg = cfg or {}
        self.max_per_day = int(cfg.get("max_shown_per_day", 8))
        self.min_gap_s = max(10, int(cfg.get("min_gap_seconds", 10)))
        self.ttl_s = int(cfg.get("bubble_seconds", 8))
        self.cooldown_days = int(cfg.get("per_item_cooldown_days", 1))

    def _shown_today(self) -> List[Dict[str, Any]]:
        d = self.clock.now_utc().strftime("%Y-%m-%d")
        try:
            return self.db.query(
                "SELECT alt_id, at_utc FROM bubble_log WHERE at_utc LIKE ?",
                (d + "%",)
            )
        except Exception:
            # Fallback if table doesn't exist yet
            return []

    def next(self) -> Optional[Dict[str, Any]]:
        """Return the next random alternative to surface, or None if capped/throttled."""
        now = self.clock.now_utc()
        shown = self._shown_today()
        if len(shown) >= self.max_per_day:
            return None

        # Enforce minimum gap between bubbles
        if shown:
            timestamps = []
            for r in shown:
                try:
                    timestamps.append(_dt.datetime.fromisoformat(r["at_utc"].replace("Z", "+00:00")))
                except Exception:
                    pass
            if timestamps:
                last_time = max(timestamps)
                # Ensure now is timezone-aware for comparison if last_time is
                if last_time.tzinfo and not now.tzinfo:
                    now = now.replace(tzinfo=_dt.timezone.utc)
                if (now - last_time).total_seconds() < self.min_gap_s:
                    return None

        # Filter out alternatives on cooldown
        cooldown_alts = set()
        for r in shown:
            try:
                t = _dt.datetime.fromisoformat(r["at_utc"].replace("Z", "+00:00"))
                if (now - t).days < self.cooldown_days:
                    cooldown_alts.add(r["alt_id"])
            except Exception:
                pass

        try:
            pool = [
                r for r in self.db.query("SELECT id, label, kind, minimum_version FROM life_alternative")
                if r["id"] not in cooldown_alts
            ]
        except Exception:
            pool = []

        if not pool:
            return None

        # UNIFORM random selection -- strictly unranked and non-optimized (L-8)
        pick = random.choice(pool)

        try:
            self.db.insert("bubble_log", {
                "id": str(uuid.uuid4()),
                "alt_id": pick["id"],
                "at_utc": self.clock.iso(),
                "outcome": None
            })
        except Exception:
            pass

        if self.ledger:
            self.ledger.record(
                "life_bubble_shown",
                observed={"alt": pick["id"], "shown_today": len(shown) + 1},
                action_taken="cold-declared recall; not a nudge (D-092)",
                telemetry_quality="OK"
            )

        return {
            "id": pick["id"],
            "label": pick["label"],
            "kind": pick["kind"],
            "minimum_version": pick.get("minimum_version", ""),
            "ttl_seconds": self.ttl_s
        }

    def resolve(self, alt_id: str, outcome: str):
        """Record outcome ('done' or 'not_now'). A missed bubble is never counted against the user (L-2)."""
        if outcome == "done":
            try:
                from .life_mirror import LifeMirrorService
                LifeMirrorService(self.db, {}, self.clock, self.ledger).log(alt_id)
            except Exception:
                pass
