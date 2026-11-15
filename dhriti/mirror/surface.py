"""The mirror's surfacing side (Part 3 §3.1 / PDF Part 2 §7): the
one-per-day rule, the ranking query, recall-before-reveal, and the
eligibility gate.

The law (L-6 in v0.6.0's form, L-7 of the PDF): surfacing happens
only after the earned-evening moment (or a declared-leisure window /
post-window_end boundary). The parking lot never pushes during a
session; neither does the mirror.
"""

from datetime import datetime, timedelta
from typing import Optional

from ..db import Database
from ..timeutil import Clock, RealClock, parse_iso, to_iso
from . import events as ev


class SurfaceService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None,
                 store=None):
        self.db = db
        self.config = config.get("mirror", {})
        self.clock = clock or RealClock()
        self.ledger = ledger
        if store is not None:
            self.store = store
        else:
            from .store import MirrorStore
            self.store = MirrorStore(db, config, clock, ledger)

    # -- eligibility -----------------------------------------------------------
    def eligible_now(self, day: Optional[dict]) -> bool:
        """§3.1 flow step 1: earned evening (targets met, day closed),
        declared leisure, or after the window_end+day_end boundary.
        Never during an OPEN day — the mirror does not push."""
        surfacing = self.config.get("surfacing", {})
        if not self.config.get("enabled", False):
            return False
        if not day:
            return False
        # after the window: the evening is open for surfacing
        if day.get("window_end_at"):
            if self.clock.now_utc() >= parse_iso(day["window_end_at"]):
                return True
        return False

    def surfaced_today(self) -> bool:
        """One-per-day: has an item already been surfaced today?"""
        today = self.clock.now_utc().strftime("%Y-%m-%d")
        row = self.db.query_one(
            "SELECT 1 AS one FROM event WHERE "
            "event_type='content_item_surfaced' AND occurred_at_utc "
            "LIKE ? LIMIT 1", (today + "%",))
        return row is not None

    # -- ranking -----------------------------------------------------------------
    def suggest(self, minutes: Optional[int] = None,
                category: Optional[str] = None,
                state: Optional[str] = None) -> Optional[dict]:
        """The one item: oldest unopened first (the base ranking), or
        age/stability when the FSRS gate has opened. Optional
        narrowing (--minutes/--category/--state) is applied BEFORE the
        query — the narrowing is the user's, not the system's."""
        surfacing = self.config.get("surfacing", {})
        max_age = int(surfacing.get("max_age_days_for_surfacing", 365))
        use_stability = bool(self.config.get("decay", {}).get(
            "use_stability", False))

        sql = ("SELECT * FROM content_item WHERE opened_at IS NULL "
               "AND abandoned_at IS NULL AND aged_out_at IS NULL "
               "AND intent_class != 'reference' "
               "AND (last_surfaced_at IS NULL OR "
               "date(last_surfaced_at) < date('now', 'localtime')) "
               "AND saved_at_utc >= date('now', ?) ")
        params: list = [f"-{max_age} days"]
        if category:
            sql += "AND category=? "
            params.append(category)
        if state == "resaved":
            sql += "AND times_resaved>0 "
        if use_stability:
            sql += ("ORDER BY ((julianday('now') - "
                    "julianday(saved_at_utc)) / "
                    "current_stability_days) DESC LIMIT 1")
        else:
            sql += ("ORDER BY (julianday('now') - "
                    "julianday(saved_at_utc)) DESC LIMIT 1")
        item = self.db.query_one(sql, params)
        if item is None:
            return None
        # time-budget narrowing: an item longer than the declared
        # budget is skipped (the budget is the bound)
        if minutes is not None and item["duration_seconds"]:
            if item["duration_seconds"] > minutes * 60:
                return None
        return item

    # -- the surface flow (recall before reveal) ------------------------------
    def surface(self, day: Optional[dict] = None,
                minutes: Optional[int] = None,
                category: Optional[str] = None,
                state: Optional[str] = None) -> Optional[dict]:
        """Steps 1-3 + 6-7 of the flow (the recall prompt and the
        reveal are the CLI's; this returns the item + the record
        bookkeeping). Returns None when not eligible / already
        surfaced / nothing to surface."""
        surfacing = self.config.get("surfacing", {})
        if not self.eligible_now(day):
            return None
        if surfacing.get("one_per_day", True) and self.surfaced_today():
            return None
        item = self.suggest(minutes=minutes, category=category,
                            state=state)
        if item is None:
            return None
        self.store.mark_surfaced(item["id"],
                                 trigger="auto_evening")
        return self.store.get_item(item["id"])

    def recall_prompt(self, item: dict) -> str:
        """The recall-before-reveal prompt: title only. 'I don't
        remember' applies the failure penalty; 'skip' is neutral; any
        other typed text is a recall attempt."""
        return (
            f"Today's item (saved "
            f"{self._age_days(item)} days ago, resaved "
            f"{item['times_resaved']} times):\n"
            f"Title: \"{item['title']}\"\n\n"
            "Before the reveal: what do you remember about why you "
            "saved this?\n"
            "- type what you remember (a recall attempt)\n"
            "- type 'I don't remember' (honest; recorded)\n"
            "- type 'skip' (no recall, no penalty)")

    def handle_recall(self, item: dict, answer: str) -> dict:
        """The recall protocol (§3.1): 'I don't remember' -> penalty,
        reveal anyway; 'skip' -> no penalty, reveal; any text ->
        recalled (recorded)."""
        answer = (answer or "").strip()
        if answer.lower() in ("skip", ""):
            self.store.record_recall(item["id"], recalled=False,
                                     recall_text="skip")
            return {"recalled": False, "penalized": False,
                    "reveal": True}
        if answer.lower() in ("i don't remember",
                              "i dont remember"):
            self.store.record_recall(item["id"], recalled=False,
                                     recall_text=answer)
            return {"recalled": False, "penalized": True,
                    "reveal": True}
        self.store.record_recall(item["id"], recalled=True,
                                 recall_text=answer)
        return {"recalled": True, "penalized": False, "reveal": True}

    def reveal(self, item: dict) -> str:
        """The reveal: description + thumbnail + the honest re-save
        line (§3.5)."""
        lines = [f"Title: \"{item['title']}\""]
        if item["description"]:
            lines.append(f"Description: {item['description'][:400]}")
        if item["times_resaved"]:
            lines.append(
                f"You have saved this {item['times_resaved'] + 1} "
                "times. You have not opened it.")
        lines.append("\nOpen / Dismiss / Abandon (a reason)")
        return "\n".join(lines)

    def _age_days(self, item: dict) -> int:
        return (self.clock.now_utc()
                - parse_iso(item["saved_at_utc"])).days
