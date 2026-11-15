"""Kael mechanisms, part one (v0.7.0 Part 3 §3.13): the 30-question
reflection bank and the emergency contacts.

The bank is off by default — some of the questions are harsh; which
questions exist is a cold-state choice. The cold review draws one
per week when enabled.

Emergency contacts: three humans, declared cold, shown on the wall
page in small text when a break is initiated — a fact on the wall,
not a notification.
"""

import uuid
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, to_iso

REFLECTION_BANK = (
    "If you could see a timer counting down the productive hours of "
    "your life, would you spend this one swiping?",
    "What would tomorrow look like if the version of you that wrote "
    "this contract were watching?",
    "You said you wanted X. What is the smallest thing that moves "
    "toward X right now?",
    "What are you pretending not to know?",
    "Which conversation are you having instead of the work?",
    "What did the audience give you this week that the stage did not?",
    "If the tool disappeared tonight, what would you do at 10:00 "
    "tomorrow?",
    "What is the discomfort you are avoiding right now, specifically?",
    "Which saved item are you saving FROM yourself?",
    "What would you tell a friend who showed you this week's numbers?",
    "What is one thing you finished that you did not celebrate or "
    "dramatize?",
    "Where did you trade a real want for an available one?",
    "What belief of yours did today's evidence support?",
    "What belief of yours did today's evidence contradict?",
    "If you had to delete one app tonight, which one and why haven't "
    "you?",
    "What are you building instead of doing?",
    "Which door have you been standing outside of for a month?",
    "What did you almost start today?",
    "What is the cheapest comfort you reached for this week?",
    "What is the most expensive comfort you avoided?",
    "If the wall did not exist, would you still be here at this hour?",
    "What question are you tired of being asked by yourself?",
    "What would 'enough' look like today — concretely?",
    "Which skill did you use today that you want in five years?",
    "Which skill did you NOT use today that you want in five years?",
    "What did you say yes to that you should have parked?",
    "What did you park that you actually miss?",
    "Whose approval are you performing for right now?",
    "What is the one true thing about this week you would say out "
    "loud?",
    "What are you afraid the next 30 minutes will show you?",
)


class ReflectionBank:
    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("reflection_bank", {})
        self.clock = clock or RealClock()
        self.ledger = ledger

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    def questions(self) -> tuple:
        return REFLECTION_BANK

    def draw(self, week_start_iso: str) -> Optional[str]:
        """One question per week, deterministic from the week key —
        the draw is stable, not random (the same week shows the same
        question; the record is reproducible)."""
        if not self.enabled:
            return None
        row = self.db.query_one(
            "SELECT question_index FROM reflection_draw WHERE "
            "week_start=?", (week_start_iso,))
        if row:
            return REFLECTION_BANK[row["question_index"]]
        digest = int.from_bytes(
            week_start_iso.encode(), "big")
        index = digest % len(REFLECTION_BANK)
        self.db.insert("reflection_draw", {
            "week_start": week_start_iso,
            "question_index": index,
            "drawn_at": to_iso(self.clock.now_utc()),
        })
        if self.ledger is not None:
            self.ledger.record(
                "reflection_question_drawn",
                observed={"week": week_start_iso,
                          "index": index},
                action_taken="one question drawn for the cold review")
        return REFLECTION_BANK[index]


class EmergencyContacts:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def add(self, label: str, contact: str) -> dict:
        label = (label or "").strip()
        contact = (contact or "").strip()
        if not label or not contact:
            raise ValueError(
                "a label and a contact are required (e.g. "
                "'mom' '+91-...'')")
        count = self.db.query_one(
            "SELECT COUNT(*) AS n FROM emergency_contact")["n"]
        if count >= 3:
            raise ValueError(
                "three contacts are enough — this is not a directory")
        row = {"id": str(uuid.uuid4()),
               "created_at": to_iso(self.clock.now_utc()),
               "label": label[:100], "contact": contact[:200]}
        self.db.insert("emergency_contact", row)
        if self.ledger is not None:
            self.ledger.record(
                "emergency_contact_added",
                observed={"label": label},
                action_taken="contact declared cold; shown on the "
                             "wall when a break starts")
        return row

    def list(self) -> list:
        return self.db.query(
            "SELECT * FROM emergency_contact ORDER BY created_at")

    def remove(self, contact_id: str) -> None:
        self.db.execute("DELETE FROM emergency_contact WHERE id=?",
                        (contact_id,))
