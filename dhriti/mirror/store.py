"""The mirror store (Part 3 §3.1): sources, items, dedupe, re-save
detection, progress, re-entry, labels, search escapes.

Everything the mirror knows lives in tables (schema v6); every fact
the user acts on lands in the ledger as a content_item_* event. The
store is deliberately dumb — no ranking here (surface.py), no
ingestion here (ingest.py).
"""

import json
import uuid
from datetime import timedelta
from typing import Optional

from ..db import Database
from ..timeutil import Clock, RealClock, parse_iso, to_iso
from . import events as ev
from .classify_rule import classify


class MirrorStore:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("mirror", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    # -- sources ---------------------------------------------------------------
    def add_source(self, source_type: str, identifier: str,
                   display_name: str,
                   intent_class: str = "intent") -> dict:
        if source_type not in ("youtube_liked", "youtube_playlist",
                               "csv_import"):
            raise ValueError(
                f"source_type must be youtube_liked | youtube_playlist "
                f"| csv_import, got {source_type!r}")
        if intent_class not in ("intent", "reference", "mixed"):
            raise ValueError("intent_class must be intent|reference|"
                             "mixed")
        source_id = str(uuid.uuid4())
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.insert("content_source", {
            "id": source_id,
            "source_type": source_type,
            "source_identifier": identifier,
            "display_name": display_name,
            "enabled": 1,
            "intent_class": intent_class,
            "created_at": now,
            "last_ingested_at": None,
        })
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM content_source WHERE id=?", (source_id,))

    def sources(self) -> list:
        return self.db.query(
            "SELECT * FROM content_source ORDER BY created_at")

    def mark_ingested(self, source_id: str):
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute(
            "UPDATE content_source SET last_ingested_at=? WHERE id=?",
            (now, source_id))

    # -- items -----------------------------------------------------------------
    def get_item(self, item_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM content_item WHERE id=?", (item_id,))

    def find_item(self, source_id: str, external_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM content_item WHERE source_id=? AND "
            "external_id=?", (source_id, external_id))

    def upsert_item(self, source_id: str, external_id: str, title: str,
                    description: str = "",
                    duration_seconds: Optional[int] = None,
                    thumbnail_url: str = "",
                    published_at: str = "") -> dict:
        """Save (new) or re-save (seen >24h after the original save).
        A re-save increments times_resaved and fires content_item_resaved
        — the pile telling you it is still interesting to Future You."""
        existing = self.find_item(source_id, external_id)
        now = self.clock.now_utc()
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        privacy = self.config.get("privacy", {})
        store_description = description or "" \
            if privacy.get("store_descriptions", True) else ""
        if existing is not None:
            gap = (now - parse_iso(existing["saved_at_utc"])
                   ).total_seconds()
            resaved = int(existing["times_resaved"])
            if gap > 24 * 3600:
                resaved += 1
                if self.ledger is not None:
                    self.ledger.record(
                        ev.CONTENT_ITEM_RESAVED,
                        observed={"item": existing["id"][:8],
                                  "external_id": external_id,
                                  "title": (title or "")[:100],
                                  "times_resaved": resaved},
                        action_taken="saved again by Future You")
                self.db.execute(
                    "UPDATE content_item SET times_resaved=?, title=? "
                    "WHERE id=?",
                    (resaved, title or existing["title"],
                     existing["id"]))
            return self.get_item(existing["id"])
        item_id = str(uuid.uuid4())
        verdict = classify(title, store_description)
        self.db.insert("content_item", {
            "id": item_id,
            "source_id": source_id,
            "external_id": external_id,
            "title": title or "(untitled)",
            "description": store_description,
            "duration_seconds": duration_seconds,
            "thumbnail_url": thumbnail_url,
            "published_at": published_at or None,
            "saved_at_utc": now_iso,
            "last_surfaced_at": None,
            "surface_count": 0,
            "dismiss_count": 0,
            "consecutive_dismissals": 0,
            "times_resaved": 0,
            "opened_at": None,
            "completed_at": None,
            "abandoned_at": None,
            "abandoned_reason": None,
            "aged_out_at": None,
            "metadata_completeness": 1.0 if title else 0.5,
            "category": verdict["category"],
            "category_confidence": verdict["confidence"],
            "category_classified_at": now_iso,
            "category_classified_by": verdict["classifier_version"],
            "intent_class": self.get_source(source_id)["intent_class"]
            if self.get_source(source_id) else "intent",
            "effort_tier": None,
            "recall_attempts": 0,
            "recall_successes": 0,
            "current_stability_days": self._initial_stability(
                self.get_source(source_id)),
            "last_surface_intensity": "full",
        })
        if self.ledger is not None:
            self.ledger.record(
                ev.CONTENT_ITEM_SAVED,
                observed={"item": item_id[:8],
                          "external_id": external_id,
                          "title": (title or "")[:100],
                          "category": verdict["category"]},
                action_taken="saved; the pile is the record")
            self.ledger.record(
                ev.CONTENT_ITEM_CATEGORIZED,
                observed={"item": item_id[:8],
                          "category": verdict["category"],
                          "confidence": verdict["confidence"],
                          "classifier": verdict["classifier"],
                          "classifier_version":
                              verdict["classifier_version"],
                          "fallback": True},
                action_taken="rule classifier verdict")
        return self.get_item(item_id)

    def _initial_stability(self, source: Optional[dict]) -> float:
        """Type-aware decay (PDF Part 3 §3): initial stability from the
        source's intent class half-lives."""
        decay = self.config.get("decay", {})
        half_lives = decay.get("type_half_life_days",
                               {"intent": 30, "reference": 180,
                                "mixed": 60})
        intent = (source or {}).get("intent_class", "intent")
        return float(half_lives.get(intent, 30))

    # -- lifecycle updates --------------------------------------------------------
    def mark_surfaced(self, item_id: str, trigger: str = "auto_evening"):
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute(
            "UPDATE content_item SET last_surfaced_at=?, "
            "surface_count=surface_count+1 WHERE id=?",
            (now, item_id))
        item = self.get_item(item_id)
        if self.ledger is not None:
            self.ledger.record(
                ev.CONTENT_ITEM_SURFACED,
                observed={"item": item_id[:8],
                          "title": item["title"][:100],
                          "trigger": trigger,
                          "saved_days_ago": self._age_days(item)},
                action_taken="one item surfaced (the pile, not a feed)")

    def record_recall(self, item_id: str, recalled: bool,
                      recall_text: str = ""):
        penalty = float(self.config.get("decay", {}).get(
            "recall_failure_penalty", 0.4))
        boost = float(self.config.get("decay", {}).get(
            "recall_success_boost", 0.15))
        item = self.get_item(item_id)
        stability = float(item["current_stability_days"])
        if recalled:
            stability *= (1 + boost)
            self.db.execute(
                "UPDATE content_item SET recall_attempts="
                "recall_attempts+1, recall_successes=recall_successes+1,"
                " current_stability_days=? WHERE id=?",
                (round(stability, 2), item_id))
        else:
            stability *= (1 - penalty)
            self.db.execute(
                "UPDATE content_item SET recall_attempts="
                "recall_attempts+1, current_stability_days=? "
                "WHERE id=?",
                (round(max(0.5, stability), 2), item_id))
        if self.ledger is not None:
            self.ledger.record(
                ev.CONTENT_ITEM_RECALLED,
                observed={"item": item_id[:8], "recalled": recalled,
                          "recall_text": recall_text[:200]},
                action_taken="recall recorded before reveal")

    def record_choice(self, item_id: str, choice: str,
                      reason: str = "") -> dict:
        """Open | Dismiss | Abandon. Abandon requires a typed reason —
        the abandonment ritual (§3.6)."""
        choice = (choice or "").strip().lower()
        if choice not in ("open", "dismiss", "abandon"):
            raise ValueError("choice must be open|dismiss|abandon")
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        item = self.get_item(item_id)
        decay = self.config.get("decay", {})
        if choice == "open":
            self.db.execute(
                "UPDATE content_item SET opened_at=?, "
                "consecutive_dismissals=0, current_stability_days=? "
                "WHERE id=?",
                (now, round(float(item["current_stability_days"])
                            * (1 + float(decay.get("open_boost", 0.3))),
                            2), item_id))
            if self.ledger is not None:
                self.ledger.record(
                    ev.CONTENT_ITEM_OPENED,
                    observed={"item": item_id[:8],
                              "title": item["title"][:100]},
                    action_taken="opened")
            if item["last_surface_intensity"] != "full":
                self.db.execute(
                    "UPDATE content_item SET "
                    "last_surface_intensity='full' WHERE id=?",
                    (item_id,))
                if self.ledger is not None:
                    self.ledger.record(
                        ev.SURFACE_INTENSITY_RESTORED,
                        observed={"item": item_id[:8]},
                        action_taken="an open restores full intensity")
        elif choice == "dismiss":
            new_dismiss = int(item["dismiss_count"]) + 1
            consecutive = int(item["consecutive_dismissals"]) + 1
            stability = float(item["current_stability_days"]) \
                * (1 - float(decay.get("dismiss_penalty", 0.2)))
            self.db.execute(
                "UPDATE content_item SET dismiss_count=?, "
                "consecutive_dismissals=?, current_stability_days=? "
                "WHERE id=?",
                (new_dismiss, consecutive,
                 round(max(0.5, stability), 2), item_id))
            if self.ledger is not None:
                self.ledger.record(
                    ev.CONTENT_ITEM_DISMISSED,
                    observed={"item": item_id[:8],
                              "title": item["title"][:100],
                              "consecutive": consecutive},
                    action_taken="dismissed; not a verdict")
            self._maybe_degrade(item_id)
        else:  # abandon
            reason = (reason or "").strip()
            if len(reason) < 10:
                raise ValueError(
                    "abandoning requires a typed reason (min 10 chars) "
                    "— the reason is contract-design feedback, not "
                    "shame")
            self.db.execute(
                "UPDATE content_item SET abandoned_at=?, "
                "abandoned_reason=? WHERE id=?",
                (now, reason[:500], item_id))
            if self.ledger is not None:
                self.ledger.record(
                    ev.CONTENT_ITEM_ABANDONED,
                    observed={"item": item_id[:8],
                              "title": item["title"][:100],
                              "reason": reason[:200]},
                    action_taken="abandoned with a reason")
        return self.get_item(item_id)

    def _maybe_degrade(self, item_id: str):
        """Surface intensity degradation (§3.1 config): after N
        consecutive dismissals, the surface drops to title-only. The
        fact is recorded, and the intensity restores on an open."""
        surfacing = self.config.get("surfacing", {})
        threshold = int(surfacing.get("degrade_after_consecutive_"
                                      "dismissals", 5))
        degrade_to = surfacing.get("degrade_to", "title_only")
        item = self.get_item(item_id)
        if item["last_surface_intensity"] == "full" \
                and int(item["consecutive_dismissals"]) >= threshold:
            self.db.execute(
                "UPDATE content_item SET last_surface_intensity=? "
                "WHERE id=?", (degrade_to, item_id))
            if self.ledger is not None:
                self.ledger.record(
                    ev.SURFACE_INTENSITY_DEGRADED,
                    observed={"item": item_id[:8], "to": degrade_to,
                              "consecutive_dismissals":
                                  item["consecutive_dismissals"]},
                    action_taken="surface degraded to title-only")

    def record_progress(self, item_id: str, fraction: float,
                        source: str = "extension") -> dict:
        """Playback progress (§3.8): recorded per post from the
        extension (throttled at the bridge); fraction >= 0.9 completes
        the item."""
        fraction = max(0.0, min(1.0, float(fraction)))
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.insert("content_item_progress", {
            "item_id": item_id, "recorded_at": now,
            "fraction": round(fraction, 3), "source": source[:50]})
        if self.ledger is not None:
            self.ledger.record(
                ev.CONTENT_ITEM_PROGRESS,
                observed={"item": item_id[:8],
                          "fraction": round(fraction, 2)},
                action_taken="progress recorded")
        if fraction >= 0.9:
            item = self.get_item(item_id)
            if item and not item["completed_at"]:
                self.db.execute(
                    "UPDATE content_item SET completed_at=? WHERE id=?",
                    (now, item_id))
                stability = float(item["current_stability_days"]) \
                    * (1 + float(self.config.get("decay", {}).get(
                        "completion_boost", 0.5)))
                self.db.execute(
                    "UPDATE content_item SET current_stability_days=? "
                    "WHERE id=?", (round(stability, 2), item_id))
                if self.ledger is not None:
                    self.ledger.record(
                        ev.CONTENT_ITEM_COMPLETED,
                        observed={"item": item_id[:8],
                                  "title": item["title"][:100]},
                        action_taken="completed (>=90% watched)")
        return self.get_item(item_id)

    def latest_progress(self, item_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM content_item_progress WHERE item_id=? "
            "ORDER BY recorded_at DESC LIMIT 1", (item_id,))

    # -- re-entry (§3.7) -------------------------------------------------------
    def declare_reentry(self, item_id: str, context: str,
                        session_id: Optional[str] = None,
                        day_date: Optional[str] = None) -> dict:
        """Opening an item requires a one-sentence declaration of
        context. Recorded; the outcome is set cold, later."""
        context = (context or "").strip()
        if len(context) < 10:
            raise ValueError(
                "a one-sentence context is required (min 10 chars) — "
                "why are you opening this?")
        reentry_id = str(uuid.uuid4())
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.insert("content_item_reentry", {
            "id": reentry_id,
            "item_id": item_id,
            "declared_at": now,
            "context": context[:500],
            "session_id": session_id,
            "day_date": day_date or now[:10],
            "outcome": None,
            "outcome_recorded_at": None,
        })
        if self.ledger is not None:
            self.ledger.record(
                ev.CONTENT_ITEM_REENTRY,
                observed={"reentry": reentry_id[:8], "item": item_id[:8],
                          "context": context[:200]},
                action_taken="re-entry declared before opening")
        return self.db.query_one(
            "SELECT * FROM content_item_reentry WHERE id=?",
            (reentry_id,))

    def record_reentry_outcome(self, reentry_id: str,
                               outcome: str) -> dict:
        if outcome not in ("completed", "partial", "abandoned"):
            raise ValueError("outcome must be completed|partial|"
                             "abandoned")
        row = self.db.query_one(
            "SELECT * FROM content_item_reentry WHERE id=?",
            (reentry_id,))
        if row is None:
            raise ValueError(f"no re-entry {reentry_id}")
        if row["outcome"]:
            raise ValueError(
                f"outcome already recorded: {row['outcome']}")
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.execute(
            "UPDATE content_item_reentry SET outcome=?, "
            "outcome_recorded_at=? WHERE id=?",
            (outcome, now, reentry_id))
        if self.ledger is not None:
            self.ledger.record(
                ev.CONTENT_ITEM_REENTRY_OUTCOME,
                observed={"reentry": reentry_id[:8],
                          "item": row["item_id"][:8],
                          "outcome": outcome},
                action_taken="outcome recorded in cold state")
        return self.db.query_one(
            "SELECT * FROM content_item_reentry WHERE id=?",
            (reentry_id,))

    # -- aging (§3.1 surfacing config) ---------------------------------------
    def age_out_old_items(self) -> int:
        """Items older than aged_out_after_days (default 180) and never
        opened are aged out of the ranking — a fact recorded, not a
        deletion."""
        days = int(self.config.get("surfacing", {}).get(
            "aged_out_after_days", 180))
        cutoff = (self.clock.now_utc()
                  - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self.db.query(
            "SELECT id FROM content_item WHERE opened_at IS NULL "
            "AND abandoned_at IS NULL AND aged_out_at IS NULL "
            "AND saved_at_utc <= ?", (cutoff,))
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        for row in rows:
            self.db.execute(
                "UPDATE content_item SET aged_out_at=? WHERE id=?",
                (now, row["id"]))
        return len(rows)

    def _age_days(self, item: dict) -> int:
        return (self.clock.now_utc()
                - parse_iso(item["saved_at_utc"])).days

    # -- labels (active learning §5 of the PDF; the store side) --------------
    def record_label(self, item_id: str, label: str,
                     source: str = "review") -> dict:
        item = self.get_item(item_id)
        if item is None:
            raise ValueError(f"no item {item_id}")
        label_id = str(uuid.uuid4())
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.insert("content_item_label", {
            "id": label_id,
            "item_id": item_id,
            "labeled_at": now,
            "label": label[:100],
            "previous_classifier_category": item["category"],
            "previous_classifier_confidence":
                item["category_confidence"],
            "classifier_version": item["category_classified_by"],
            "source": source[:50],
        })
        # the label IS the new category (a human correction wins)
        self.db.execute(
            "UPDATE content_item SET category=? WHERE id=?",
            (label, item_id))
        if self.ledger is not None:
            self.ledger.record(
                ev.CONTENT_ITEM_LABELED,
                observed={"item": item_id[:8], "label": label,
                          "previous": item["category"],
                          "source": source},
                action_taken="label recorded; correction wins")
        return self.db.query_one(
            "SELECT * FROM content_item_label WHERE id=?", (label_id,))

    # -- counts / facts (the aftermath's "record" block) ---------------------
    def unopened_count(self) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) AS n FROM content_item WHERE opened_at "
            "IS NULL AND abandoned_at IS NULL AND aged_out_at IS NULL")
        return row["n"]

    def oldest_unopened(self) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM content_item WHERE opened_at IS NULL AND "
            "abandoned_at IS NULL AND aged_out_at IS NULL "
            "ORDER BY saved_at_utc ASC LIMIT 1")

    def week_facts(self, week_start_iso: str) -> dict:
        end = (parse_iso(week_start_iso + "T00:00:00Z")
               + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        start = week_start_iso + "T00:00:00Z"

        def count(sql, params=()):
            return self.db.query_one(sql, params)["n"]

        saved = count(
            "SELECT COUNT(*) AS n FROM content_item WHERE "
            "saved_at_utc>=? AND saved_at_utc<?", (start, end))
        resaved = count(
            "SELECT COUNT(*) AS n FROM content_item WHERE "
            "times_resaved>0 AND saved_at_utc<?", (end,))
        surfaced = count(
            "SELECT COUNT(*) AS n FROM event WHERE "
            "event_type='content_item_surfaced' AND occurred_at_utc>=? "
            "AND occurred_at_utc<?", (start, end))
        opened = count(
            "SELECT COUNT(*) AS n FROM event WHERE "
            "event_type='content_item_opened' AND occurred_at_utc>=? "
            "AND occurred_at_utc<?", (start, end))
        completed = count(
            "SELECT COUNT(*) AS n FROM event WHERE "
            "event_type='content_item_completed' AND occurred_at_utc>=? "
            "AND occurred_at_utc<?", (start, end))
        dismissed = count(
            "SELECT COUNT(*) AS n FROM event WHERE "
            "event_type='content_item_dismissed' AND "
            "occurred_at_utc>=? AND occurred_at_utc<?", (start, end))
        abandoned = count(
            "SELECT COUNT(*) AS n FROM event WHERE "
            "event_type='content_item_abandoned' AND "
            "occurred_at_utc>=? AND occurred_at_utc<?", (start, end))
        avoided = count(
            "SELECT COUNT(*) AS n FROM event e WHERE "
            "e.event_type='content_item_dismissed' AND "
            "e.occurred_at_utc>=?", (start,))
        oldest = self.oldest_unopened()
        by_category = self.db.query(
            "SELECT category, COUNT(*) AS saved FROM content_item "
            "WHERE saved_at_utc>=? AND saved_at_utc<? "
            "GROUP BY category ORDER BY saved DESC", (start, end))
        return {"saved": saved, "resaved_total": resaved,
                "surfaced": surfaced, "opened": opened,
                "completed": completed, "dismissed": dismissed,
                "abandoned": abandoned, "avoided_total": avoided,
                "oldest_unopened": oldest, "by_category": by_category}
