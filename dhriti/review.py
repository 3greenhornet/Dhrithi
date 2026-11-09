"""Cold-state surfaces: the parking lot, the review protocol, the digest.

Three mechanisms (v0.5.0 shape):

  ParkingLotService — the wall's mail slot. A curiosity branch that
    fires mid-session is captured in ONE line and deferred. Not
    blocked-and-resented, not followed into the loop: parked.
    Dispositions happen in cold state only.

  ColdReviewService — the fixed question protocol. Answers are
    SUBMITTED evidence: recorded, never judged. Answer text stays in
    the cold_review table; only the question key touches the ledger.

  build_digest — the minimal E4 "dead man's switch": a weekly one-page
    summary (facts + chain head) meant to be sent to the one human who
    cares whether the subject actually grows.
"""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso


# -- parking lot ------------------------------------------------------------

class ParkingLotService:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def park(self, question: str, source: str = "cli",
             session_id: Optional[str] = None,
             day_id: Optional[str] = None) -> dict:
        """One line, one glance, back to work. The wall takes mail; it
        does not discuss it."""
        question = (question or "").strip()
        if not question:
            raise ValueError("park a question, not an empty line")
        if len(question) > 200:
            question = question[:197] + "..."
        row_id = str(uuid.uuid4())
        self.db.insert("parking_lot", {
            "id": row_id,
            "created_at": self.clock.iso(),
            "session_id": session_id,
            "day_id": day_id,
            "question": question,
            "source": (source or "cli")[:200],
            "disposition": "parked",
            "disposed_at": None,
            "note": None,
        })
        if self.ledger is not None:
            self.ledger.record(
                "curiosity_topic_parked",
                session_id=session_id,
                observed={"question": question,
                          "source": (source or "cli")[:100]},
                action_taken="curiosity captured; not followed "
                             "in-session")
        return self.get(row_id)

    def get(self, row_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM parking_lot WHERE id=?", (row_id,))

    def open_items(self) -> list:
        return self.db.query(
            "SELECT * FROM parking_lot WHERE disposition='parked' "
            "ORDER BY created_at")

    def list(self, disposition: Optional[str] = None) -> list:
        if disposition:
            return self.db.query(
                "SELECT * FROM parking_lot WHERE disposition=? "
                "ORDER BY created_at", (disposition,))
        return self.db.query(
            "SELECT * FROM parking_lot ORDER BY created_at")

    def pending(self) -> list:
        return self.list("parked")

    def dispose(self, row_id: str, disposition: str,
                note: str = "") -> dict:
        if disposition not in ("approved", "dropped", "explored"):
            raise ValueError(
                "disposition must be approved | dropped | explored "
                "(cold-state decisions, not in-session)")
        row = self.get(row_id)
        if not row:
            raise ValueError("no such parked topic")
        if row["disposition"] != "parked":
            raise ValueError(
                f"already dispositioned as {row['disposition']}")
        self.db.update("parking_lot", row_id, {
            "disposition": disposition,
            "disposed_at": self.clock.iso(),
            "note": (note or "")[:500],
        })
        if self.ledger is not None:
            self.ledger.record(
                "parking_lot_disposition",
                observed={"disposition": disposition,
                          "question": row["question"][:100]},
                action_taken="cold-state decision recorded")
        return self.get(row_id)

    def for_day_id(self, day_id: str) -> list:
        return self.db.query(
            "SELECT * FROM parking_lot WHERE day_id=? ORDER BY created_at",
            (day_id,))

    def stats(self) -> dict:
        rows = self.db.query(
            "SELECT disposition, COUNT(*) AS n FROM parking_lot "
            "GROUP BY disposition")
        return {r["disposition"]: r["n"] for r in rows}


# -- cold review ------------------------------------------------------------

# v0.5.0 questions. The rebuild replaced five of the base's six with
# its own; only competence_source survived. (v0.6.0 Part 1 §6 restores
# the base six — that correction is deliberate and recorded.)
REVIEW_QUESTIONS = [
    ("competence_source",
     "Where did the feeling of competence come from — the task, "
     "or talk about the task?"),
    ("targets_honest",
     "Were the targets honest — could they be met on a normal day?"),
    ("toll_worth_it",
     "If the toll was paid: was it worth the declared penalty?"),
    ("what_would_make_tomorrow_sealable",
     "What would make tomorrow's contract sealable by 10:00?"),
    ("substitute_time",
     "Where did the substitute budget actually go since the last "
     "review?"),
    ("window_held",
     "Did the window hold — did the work stay inside it?"),
]

CONDITIONAL_QUESTIONS = {
    "leisure_honored": (
        "Was the declared leisure honored as declared — same label, "
        "same length, no drift past it? (D-047)"),
}


class ColdReviewService:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def questions_for(self, leisure_declared: bool) -> list:
        qs = list(REVIEW_QUESTIONS)
        if leisure_declared:
            qs.append(("leisure_honored",
                       CONDITIONAL_QUESTIONS["leisure_honored"]))
        return qs

    def record(self, scope: str, question_key: str, answer: str,
               day_date: Optional[str] = None) -> dict:
        valid = {k for k, _ in REVIEW_QUESTIONS} \
            | set(CONDITIONAL_QUESTIONS)
        if question_key not in valid:
            raise ValueError(f"unknown question key: {question_key}")
        answer = (answer or "").strip()
        if not answer:
            raise ValueError("an empty answer is not an answer")
        row_id = str(uuid.uuid4())
        self.db.insert("cold_review", {
            "id": row_id,
            "created_at": self.clock.iso(),
            "scope": scope,
            "question_key": question_key,
            "answer": answer[:2000],
            "day_date": day_date,
        })
        if self.ledger is not None:
            self.ledger.record(
                "cold_review_answer",
                observed={"scope": scope,
                          "question_key": question_key},
                action_taken="submitted evidence recorded")
        return self.get(row_id)

    def get(self, row_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM cold_review WHERE id=?", (row_id,))

    def answers_for(self, scope: str) -> list:
        return self.db.query(
            "SELECT * FROM cold_review WHERE scope=? ORDER BY created_at",
            (scope,))

    def latest(self, question_key: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM cold_review WHERE question_key=? "
            "ORDER BY created_at DESC LIMIT 1", (question_key,))


# -- weekly digest (minimal E4) ----------------------------------------------

def build_digest(db: Database, ledger, week_start_iso: str,
                 config: Optional[dict] = None,
                 clock: Optional[Clock] = None) -> str:
    """A plain-text, one-page week summary anchored to the chain head.

    Intended use (config digest.recipient_label): the user sends this
    file to their accountability human every week. The human does not
    need to understand the system — they need to notice (a) the
    numbers and (b) whether the file stops arriving. Tamper-evident by
    absence.
    """
    import datetime as _dt
    from . import stage_ratio as _sr
    from .constants import DEFAULT_CONFIG
    config = config or DEFAULT_CONFIG
    clock = clock or RealClock()
    start = parse_iso(week_start_iso + "T00:00:00Z")
    end = to_iso(start + timedelta(days=7))
    days = db.query(
        "SELECT date, state, targets_met FROM day WHERE date>=? AND "
        "date<? ORDER BY date", (week_start_iso, end[:10]))
    sessions = db.query(
        "SELECT state, COUNT(*) AS n FROM session WHERE started_at>=? "
        "AND started_at<? GROUP BY state", (week_start_iso, end))
    breaks = db.query(
        "SELECT reason FROM break_glass WHERE confirmed_at>=? AND "
        "confirmed_at<? ORDER BY confirmed_at", (week_start_iso, end))
    emergency = db.query(
        "SELECT COUNT(*) AS n FROM event WHERE event_type="
        "'emergency_exception' AND occurred_at_utc>=? AND occurred_at_utc<?",
        (week_start_iso, end))
    parked = db.query(
        "SELECT disposition, COUNT(*) AS n FROM parking_lot "
        "WHERE created_at>=? AND created_at<? GROUP BY disposition",
        (week_start_iso, end))
    reviews = db.query(
        "SELECT question_key, answer FROM cold_review WHERE scope=? "
        "ORDER BY created_at", (f"week:{week_start_iso}",))

    consumption_counts = {}
    total_navs = 0
    consumption_navs = 0
    drift_total = 0
    leisure_rows = db.query(
        "SELECT * FROM leisure_declaration WHERE day_date>=? AND "
        "day_date<? ORDER BY created_at",
        (week_start_iso, end[:10]))
    for d in days:
        date_obj = _dt.date.fromisoformat(d["date"])
        prof = _sr.profile_navigation(db, config, date_obj)
        total_navs += prof["total"]
        consumption_navs += prof["consumption"]
        for cat, n in prof["counts"].items():
            consumption_counts[cat] = consumption_counts.get(cat, 0) + n
        split = _sr.drift_split(prof["consumption_events"], leisure_rows)
        drift_total += split["drift"]

    n_days = len(days)
    met = sum(1 for d in days if d["targets_met"])
    lines = []
    lines.append("DHRITI WEEKLY DIGEST")
    lines.append(f"week: {week_start_iso} .. {end[:10]}")
    lines.append(f"generated: {clock.iso()}")
    lines.append("")
    lines.append("== days ==")
    lines.append(f"days recorded: {n_days}; targets met on {met}")
    for d in days:
        lines.append(f"  {d['date']}  {d['state']}"
                     f"  targets={'met' if d['targets_met'] else 'unmet'}")
    lines.append("")
    lines.append("== sessions ==")
    for s in sessions:
        lines.append(f"  {s['state']}: {s['n']}")
    lines.append("")
    lines.append("== break-glass (reasons, verbatim) ==")
    if not breaks:
        lines.append("  none")
    for b in breaks:
        lines.append(f"  - {b['reason']}")
    emergency_count = emergency[0]["n"] if emergency else 0
    lines.append(f"emergency exceptions: {emergency_count}")
    lines.append("")
    lines.append("== parking lot ==")
    if not parked:
        lines.append("  no topics parked")
    for p in parked:
        lines.append(f"  {p['disposition']}: {p['n']}")
    lines.append("")
    lines.append("== stage ratio (the subject's own metric) ==")
    if total_navs:
        share = consumption_navs / total_navs
        lines.append(f"  audience share of observed navigation: "
                     f"{round(share * 100)}% of {total_navs} navigations")
        lines.append("  endorsed band: 20-30% audience "
                     "(Specimen 001)")
    else:
        lines.append("  no navigation observed this week")
    if consumption_counts:
        top = sorted(consumption_counts.items(),
                     key=lambda kv: -kv[1])[:5]
        lines.append("  top consumption categories: " + ", ".join(
            f"{cat} {n}" for cat, n in top))
    lines.append("")
    lines.append("== declared rest vs drift ==")
    if leisure_rows:
        minutes = sum(r["planned_minutes"] for r in leisure_rows)
        lines.append(f"  declared: {len(leisure_rows)} window(s), "
                     f"{minutes} minutes total")
    else:
        lines.append("  no leisure declared this week")
    lines.append(f"  drift: {drift_total} consumption navigation(s) "
                 "outside declared windows")
    lines.append("")
    lines.append("== cold review answers (submitted, not verified) ==")
    if not reviews:
        lines.append("  (no review completed this week — itself a fact)")
    for r in reviews:
        lines.append(f"  {r['question_key']}: {r['answer'][:200]}")
    lines.append("")
    head = ledger.head()
    chain = ledger.verify_chain()
    lines.append("== integrity ==")
    lines.append(f"chain head: {head['row_hash']}")
    lines.append(f"chain ok: {chain['ok']} ({chain['checked']} events)")
    lines.append("")
    lines.append(
        "This digest is the dead-man's switch: if a week's digest does "
        "not arrive, ask why. The system cannot make itself honest "
        "alone; the recipient of this file is the fourth enforcement "
        "level.")
    return "\n".join(lines)
