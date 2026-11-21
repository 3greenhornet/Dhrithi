"""The life mirror (v0.7.0 Part 3 §3.2): declared alternatives.

The wall shows what the device got. The life mirror shows what the
declared alternatives got — the book on the corner, the walk, the
interview practice — in the same cold numbers. The system does not
tell the operator what to do with this. It shows the two numbers.

Declaring/removing an alternative is a cold-state act (UNIQUE label);
logging an occurrence is one command.
"""

import json
import uuid
from datetime import timedelta
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso

KINDS = ("reading", "movement", "hobby", "social", "speaking",
         "creative", "other")


class LifeMirrorService:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("life_mirror", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", True))

    def declare(self, label: str, kind: str,
                minimum_version: str = "") -> dict:
        label = (label or "").strip()
        if not label:
            raise ValueError("a label is required — your own words")
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        if self.db.query_one(
                "SELECT 1 AS one FROM life_alternative WHERE label=?",
                (label,)):
            raise ValueError(f"'{label}' is already declared")
        alt_id = str(uuid.uuid4())
        self.db.insert("life_alternative", {
            "id": alt_id,
            "created_at": to_iso(self.clock.now_utc()),
            "label": label[:200],
            "kind": kind,
            "minimum_version": (minimum_version or "")[:200],
            "occurrence_log": "[]",
            "last_logged_at": None,
        })
        if self.ledger is not None:
            self.ledger.record(
                "life_alternative_declared",
                observed={"label": label[:100], "kind": kind,
                          "minimum_version":
                              (minimum_version or "")[:100]},
                action_taken="declared cold; the record will show "
                             "what it got")
        return self.get(alt_id)

    def get(self, alt_id: str) -> Optional[dict]:
        row = self.db.query_one(
            "SELECT * FROM life_alternative WHERE id=?", (alt_id,))
        if row:
            row["occurrences"] = json.loads(row["occurrence_log"]
                                            or "[]")
        return row

    def list(self) -> list:
        rows = self.db.query(
            "SELECT * FROM life_alternative ORDER BY created_at")
        for row in rows:
            row["occurrences"] = json.loads(row["occurrence_log"]
                                            or "[]")
        return rows

    def remove(self, alt_id: str) -> dict:
        row = self.get(alt_id)
        if row is None:
            raise ValueError(f"no such alternative {alt_id}")
        self.db.execute("DELETE FROM life_alternative WHERE id=?",
                        (alt_id,))
        if self.ledger is not None:
            self.ledger.record(
                "life_alternative_removed",
                observed={"label": row["label"]},
                action_taken="removed cold")
        return row

    def log(self, alt_id: str, date: Optional[str] = None) -> dict:
        row = self.get(alt_id)
        if row is None:
            raise ValueError(f"no such alternative {alt_id}")
        date = date or self.clock.now_utc().strftime("%Y-%m-%d")
        occurrences = row["occurrences"]
        if date in occurrences:
            return row  # idempotent per day
        occurrences.append(date)
        self.db.execute(
            "UPDATE life_alternative SET occurrence_log=?, "
            "last_logged_at=? WHERE id=?",
            (json.dumps(occurrences), to_iso(self.clock.now_utc()),
             alt_id))
        if self.ledger is not None:
            self.ledger.record(
                "life_alternative_logged",
                observed={"label": row["label"], "date": date},
                action_taken="occurrence logged")
        return self.get(alt_id)

    # -- the week view (§3.2 aftermath block) -------------------------------
    def week_facts(self, week_start_iso: str) -> dict:
        """For each alternative: occurrences in the last 7 days; and
        the total device use (observed navigation minutes via the
        declared-bounds weight) for the same week."""
        start = week_start_iso
        end = (parse_iso(week_start_iso + "T00:00:00Z")
               + timedelta(days=7)).strftime("%Y-%m-%d")
        facts = []
        for alt in self.list():
            in_week = [d for d in alt["occurrences"]
                       if start <= d < end]
            facts.append({
                "kind": alt["kind"],
                "label": alt["label"],
                "minimum_version": alt["minimum_version"],
                "occurrences": len(in_week),
                "days": in_week,
            })
        total_occurrences = sum(f["occurrences"] for f in facts)
        return {"alternatives": facts,
                "total_occurrences": total_occurrences,
                "declared_count": len(facts)}

    def untouched_this_week(self, week_start_iso: str) -> list:
        facts = self.week_facts(week_start_iso)
        return [f["label"] for f in facts["alternatives"]
                if f["occurrences"] == 0]

    def sync_instruments_from_vidura(self, vidura_corpus) -> list:
        """Route interactive practice instruments from Vidura into Life Mirror (D-097)."""
        from .vidura_facets import FacetEngine
        engine = FacetEngine(vidura_corpus)
        instruments = engine.get_instruments()
        added = []
        for inst in instruments:
            label = (inst.get("title") or "Practice Instrument").strip()[:100]
            existing = self.db.query_one("SELECT id FROM life_alternative WHERE label=?", (label,))
            if not existing:
                try:
                    alt = self.declare(label=label, kind="hobby", minimum_version=inst.get("url", "")[:200])
                    added.append(alt)
                except Exception:
                    pass
        return added
