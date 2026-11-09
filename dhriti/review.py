"""Cold-state surfaces: the parking lot, the review protocol, the digest.

Three mechanisms the plan names but had not wired into the lifecycle
("under-utilized mechanisms", plan Part 4 appendix):

  ParkingLotService — the wall's mail slot. A curiosity branch that fires
    mid-session is captured in ONE line and deferred. Not blocked-and-
    resented, not followed into the loop: parked. Dispositions happen in
    cold state only (approved -> next contract's allowed resources,
    dropped, explored deliberately later).

  ColdReviewService — the fixed question protocol (D-031 competence
    source, D-029 faking-it check, the graduation meta-metric, evidence
    quality, surveillance comfort, out-of-scope devices). Answers are
    SUBMITTED evidence: recorded, never judged. Answer text stays in the
    cold_review table (bootcamp-scoped per the deletion model); only the
    question key touches the ledger.

  build_digest — the minimal E4 "dead man's switch": a weekly one-page
    summary (facts + chain head) meant to be sent to the one human who
    cares whether the subject actually grows. If the digest stops
    arriving, that human knows the experiment is off the rails —
    tamper-evident by absence, which is the strongest boundary available
    to a single-user system that defers real E4 enforcement.
"""

import json
import uuid
from pathlib import Path
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso
from datetime import timedelta


# -- parking lot ------------------------------------------------------------

class ParkingLotService:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def park(self, question: str, origin: str = "",
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
            "origin": (origin or "")[:200],
            "disposition": "parked",
            "disposition_at": None,
            "disposition_note": None,
        })
        if self.ledger is not None:
            self.ledger.record(
                "curiosity_topic_parked",
                session_id=session_id,
                observed_payload={"origin": (origin or "")[:100]},
                action_taken="deferred to cold review",
                telemetry_quality="OK")
        return self.get(row_id)

    def get(self, row_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM parking_lot WHERE id=?", (row_id,))

    def list(self, disposition: Optional[str] = None) -> list:
        if disposition:
            return self.db.query(
                "SELECT * FROM parking_lot WHERE disposition=? "
                "ORDER BY created_at", (disposition,))
        return self.db.query(
            "SELECT * FROM parking_lot ORDER BY created_at")

    def pending(self) -> list:
        return self.list("parked")

    def dispose(self, row_id: str, disposition: str, note: str = "") -> dict:
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
            "disposition_at": self.clock.iso(),
            "disposition_note": (note or "")[:500],
        })
        if self.ledger is not None:
            self.ledger.record(
                "parking_lot_disposition",
                observed_payload={"disposition": disposition},
                action_taken="cold-state decision recorded",
                telemetry_quality="OK")
        return self.get(row_id)

    def for_day(self, day_id: str) -> list:
        return self.db.query(
            "SELECT * FROM parking_lot WHERE day_id=? ORDER BY created_at",
            (day_id,))

    def stats(self) -> dict:
        rows = self.db.query(
            "SELECT disposition, COUNT(*) AS n FROM parking_lot "
            "GROUP BY disposition")
        return {r["disposition"]: r["n"] for r in rows}


# -- cold review ------------------------------------------------------------

REVIEW_QUESTIONS = {
    # key: (prompt, why it exists — the prompt is shown to the user)
    "competence_source": (
        "Where did your feeling of competence come from since the last "
        "review? (name the activity, not the feeling)",
        "D-031: the source is the signal. Guitar-competence while the "
        "main belief fails is the exchange the mirror must show."),
    "faking_it": (
        "You said you were managing. Were you?",
        "D-029: productive substitution check. The answer is submitted "
        "evidence; the pattern across sessions is the signal."),
    "wall_or_choice": (
        "Did you do the work because the wall was up, or because you "
        "chose to? (one honest sentence)",
        "Graduation meta-metric: a compliant-but-dependent user has not "
        "graduated. This answer decides taper direction as much as the "
        "compliance rate does."),
    "out_of_scope_device": (
        "Did you use an out-of-scope device (phone/tablet/other machine) "
        "to reach the audience during the window?",
        "Evasion matrix honest boundary: the laptop wall has a phone "
        "door. Only you can report it."),
    "evidence_quality": (
        "Was your accepted evidence substantive or superficial? Name the "
        "weakest one.",
        "Recognition mechanism 12: proof quality drift is reviewed in "
        "cold state, not judged in-session."),
    "surveillance_comfort": (
        "Is what the system captures still acceptable? What should be "
        "narrowed?",
        "Recognition mechanism 11: the observation stack runs on consent "
        "re-confirmed in cold state."),
    # D-047: conditional question — asked only for a day scope on which
    # at least one leisure declaration exists. Six fixed questions plus
    # this one when it applies; absent otherwise (never a nag).
    "leisure_honored": (
        "Did your declared leisure hold its declared shape (the "
        "activity and the length you typed)?",
        "D-047: chosen rest is honest; undeclared drift is avoidance. "
        "The declaration is a label — this answer checks the label "
        "against the evening's facts."),
}


class ColdReviewService:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def record(self, scope: str, question_key: str, answer: str,
               day_date: Optional[str] = None) -> dict:
        if question_key not in REVIEW_QUESTIONS:
            raise ValueError(f"unknown question key: {question_key}")
        answer = (answer or "").strip()
        if not answer:
            raise ValueError("an empty answer is not an answer")
        row_id = str(uuid.uuid4())
        # The answer text lives in cold_review (bootcamp-scoped, deleted
        # with the bootcamp per the deletion model). The ledger records
        # only THAT the question was answered — the chain must survive
        # the deletion model without carrying personal text forever.
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
                observed_payload={"scope": scope,
                                  "question_key": question_key},
                action_taken="submitted evidence recorded",
                telemetry_quality="OK")
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
                 clock: Optional[Clock] = None,
                 config: Optional[dict] = None) -> str:
    """A plain-text, one-page week summary anchored to the chain head.

    Intended use (config digest.recipient_label): the user sends this
    file to their accountability human every week. The human does not
    need to understand the system — they need to notice (a) the numbers
    and (b) whether the file stops arriving. Tamper-evident by absence.
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

    # D-046/D-051: the stage ratio and top consumption categories —
    # the exchange, in the subject's own vocabulary, for the E4 human.
    # Counts only; no verdicts (the digest tone stays factual, P-05).
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
        # D-047: consumption outside declared windows, week-wide
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
    lines.append(
        f"emergency exceptions: {emergency[0]['n'] if emergency else 0}")
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
