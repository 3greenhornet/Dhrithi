"""Dhriti Decompression Transition Lock (D-018 / D-091).

When targets are met early, consumption doesn't immediately unlock.
Enters bounded Decompression Mode:
- Google Search and Google Images allowed with 3-4 springboard strike limits.
- Video and Social (YouTube, Reddit, Instagram) remain blocked.
- Crossing into off-topic rabbit-holes triggers springboard strikes and navigation revert.
- Life Mirror thought bubbles surface gently.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set


class DecompressionManager:
    def __init__(self, config: Optional[Dict[str, Any]] = None, ledger=None):
        self.config = config or {}
        self.ledger = ledger
        self.enabled = bool(self.config.get("enabled", True))
        self.window_minutes = int(self.config.get("window_minutes", 90))
        self.max_strikes = int(self.config.get("springboard_strikes_allowed", 4))
        self.allowed_domains: List[str] = self.config.get(
            "release", ["google.com", "images.google.com", "google.co.in"]
        )
        self.blocked_categories: List[str] = self.config.get(
            "still_blocked_categories", ["video", "social", "entertainment"]
        )

        # Runtime state
        self.active = False
        self.started_at: float = 0.0
        self.ends_at: float = 0.0
        self.strikes: int = 0
        self.categories_seen: Set[str] = set()

    def start(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Activate the decompression transition lock."""
        now = now or time.time()
        self.active = True
        self.started_at = now
        self.ends_at = now + (self.window_minutes * 60)
        self.strikes = 0
        self.categories_seen.clear()

        if self.ledger:
            self.ledger.record(
                "decompression_window_started",
                observed={"window_minutes": self.window_minutes, "max_strikes": self.max_strikes},
                action_taken="transition lock active; offline/search bounded release",
                telemetry_quality="OK"
            )

        return self.status(now)

    def is_active(self, now: Optional[float] = None) -> bool:
        now = now or time.time()
        if self.active and now >= self.ends_at:
            self.active = False
            if self.ledger:
                self.ledger.record(
                    "decompression_window_ended",
                    observed={"strikes_used": self.strikes},
                    action_taken="transition complete; evening earned",
                    telemetry_quality="OK"
                )
        return self.active

    def status(self, now: Optional[float] = None) -> Dict[str, Any]:
        now = now or time.time()
        active = self.is_active(now)
        remaining_s = max(0.0, self.ends_at - now) if active else 0.0
        return {
            "active": active,
            "window_minutes": self.window_minutes,
            "remaining_seconds": round(remaining_s),
            "remaining_minutes": round(remaining_s / 60, 1),
            "strikes": self.strikes,
            "max_strikes": self.max_strikes,
            "budget_exhausted": self.strikes >= self.max_strikes,
            "allowed_domains": self.allowed_domains,
            "blocked_categories": self.blocked_categories
        }

    def evaluate_navigation(self, url: str, category: Optional[str] = None, now: Optional[float] = None) -> Dict[str, Any]:
        """Evaluate a URL navigation during decompression window.

        Returns:
            {"allowed": bool, "action": "allow" | "revert" | "block", "strike_added": bool, "message": str}
        """
        now = now or time.time()
        if not self.is_active(now):
            return {"allowed": True, "action": "allow", "strike_added": False, "message": "Decompression inactive"}

        # 1. Hard blocked categories stay blocked
        if category in self.blocked_categories:
            return {
                "allowed": False,
                "action": "block",
                "strike_added": False,
                "message": f"Category '{category}' is blocked during decompression"
            }

        # 2. Check if host/domain is in allowed domains (exact or subdomain match)
        try:
            parsed = urlparse(url if "://" in url else f"http://{url}")
            host = (parsed.netloc or parsed.path).lower().split(":")[0]
            is_allowed_domain = any(
                host == d.lower() or host.endswith("." + d.lower())
                for d in self.allowed_domains
            )
        except Exception:
            is_allowed_domain = False

        if not is_allowed_domain:
            # If already exhausted, hard revert
            if self.strikes >= self.max_strikes:
                return {
                    "allowed": False,
                    "action": "revert",
                    "strike_added": False,
                    "message": "Springboard strike budget exhausted; navigation reverted"
                }

            # Increment strike for cross-topic / unlisted exploration
            self.strikes += 1
            if category:
                self.categories_seen.add(category)

            if self.ledger:
                self.ledger.record(
                    "decompression_leap_strike",
                    observed={"url": url[:100], "category": category or "unknown", "strike": self.strikes},
                    action_taken="leap strike recorded; warn or revert",
                    telemetry_quality="OK"
                )

            is_exhausted = self.strikes >= self.max_strikes
            return {
                "allowed": not is_exhausted,
                "action": "revert" if is_exhausted else "advise",
                "strike_added": True,
                "message": f"Strike {self.strikes} of {self.max_strikes} recorded."
            }

        return {"allowed": True, "action": "allow", "strike_added": False, "message": "Allowed search/reference"}
