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
    """v0.6.0 Part 2 §1: the parking lot as the inversion of the feed —
    capture, evening surfacing, age-based resurfacing, anti-drift. You
    park curiosity; the system hands it back at the moment you can
    follow it, not the moment you can't."""

    VALID_KINDS = ("question", "resource", "desire", "association")

    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def park(self, question: str, source: str = "cli",
             kind: str = "question",
             sparked_by_url: Optional[str] = None,
             sparked_by_event_id: Optional[str] = None,
             session_id: Optional[str] = None,
             day_id: Optional[str] = None) -> dict:
        """One line, one glance, back to work. The wall takes mail; it
        does not discuss it. Kinds: question | resource | desire |
        association (the four shapes curiosity takes)."""
        question = (question or "").strip()
        if not question:
            raise ValueError("park a question, not an empty line")
        if kind not in self.VALID_KINDS:
            raise ValueError(
                f"kind must be one of {self.VALID_KINDS}, got {kind!r}")
        if len(question) > 200:
            question = question[:197] + "..."
        row_id = str(uuid.uuid4())
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.db.insert("parking_lot", {
            "id": row_id,
            "created_at": now,
            "session_id": session_id,
            "day_id": day_id,
            "question": question,
            "source": (source or "cli")[:200],
            "kind": kind,
            "sparked_by_url": (sparked_by_url or "")[:500] or None,
            "sparked_by_event_id": sparked_by_event_id or None,
            "disposition": None,
            "disposed_at": None,
            "note": None,
            "evening_surfaced_at": None,
            "review_surfaced_at": None,
            "approved_to_contract_day": None,
        })
        if self.ledger is not None:
            self.ledger.record(
                "curiosity_topic_parked",
                session_id=session_id,
                observed={"question": question, "kind": kind,
                          "source": (source or "cli")[:100],
                          "sparked_by_url": sparked_by_url,
                          "sparked_by_event_id": sparked_by_event_id},
                action_taken="curiosity captured; not followed "
                             "in-session")
        return self.get(row_id)

    def get(self, row_id: str) -> Optional[dict]:
        return self.db.query_one(
            "SELECT * FROM parking_lot WHERE id=?", (row_id,))

    def open_items(self) -> list:
        return self.db.query(
            "SELECT * FROM parking_lot WHERE disposition IS NULL "
            "ORDER BY created_at")

    def list(self, disposition: Optional[str] = None) -> list:
        if disposition:
            return self.db.query(
                "SELECT * FROM parking_lot WHERE disposition=? "
                "ORDER BY created_at", (disposition,))
        return self.db.query(
            "SELECT * FROM parking_lot ORDER BY created_at")

    def pending(self) -> list:
        return self.open_items()

    def dispose(self, row_id: str, disposition: str,
                note: str = "") -> dict:
        if disposition not in ("approved", "dropped", "explored"):
            raise ValueError(
                "disposition must be approved | dropped | explored "
                "(cold-state decisions, not in-session)")
        row = self.get(row_id)
        if not row:
            raise ValueError("no such parked topic")
        if row["disposition"] is not None:
            raise ValueError(
                f"already dispositioned as {row['disposition']}")
        # Abandonment ritual (v0.7.0 §3.6 extends this): dropping
        # requires a one-line reason (min 10 chars) — the reason is
        # contract-design feedback, not shame.
        if disposition == "dropped":
            reason = (note or "").strip()
            if len(reason) < 10:
                raise ValueError(
                    "dropping requires a one-line reason (min 10 "
                    "chars) — cold-state feedback, not a silent "
                    "disappearance")
        self.db.update("parking_lot", row_id, {
            "disposition": disposition,
            "disposed_at": self.clock.iso(),
            "note": (note or "")[:500],
        })
        if self.ledger is not None:
            self.ledger.record(
                "parking_lot_disposition",
                observed={"disposition": disposition,
                          "question": row["question"][:100],
                          "note": (note or "")[:200]},
                action_taken="cold-state decision recorded")
        return self.get(row_id)

    # -- resurfacing (v0.6.0 Part 2 §1.2) --------------------------------

    def evening(self, day: str) -> list:
        """Items parked on `day`, not yet evening-surfaced."""
        return self.db.query(
            "SELECT * FROM parking_lot WHERE created_at LIKE ? "
            "AND disposition IS NULL "
            "AND evening_surfaced_at IS NULL "
            "ORDER BY created_at", (day + "%",))

    def evening_all(self, day: str) -> list:
        """Items parked on `day`, whether or not they were surfaced —
        the aftermath's record of what the evening offered (the
        surface marker dedupes the surfacing event, not the record)."""
        return self.db.query(
            "SELECT * FROM parking_lot WHERE created_at LIKE ? "
            "AND disposition IS NULL "
            "ORDER BY created_at", (day + "%",))

    def surface_evening(self, day: str) -> list:
        """Mark the day's un-surfaced items as evening-surfaced; return
        them. Called at the earned-evening moment."""
        items = self.evening(day)
        if not items:
            return []
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        for item in items:
            self.db.execute(
                "UPDATE parking_lot SET evening_surfaced_at=? WHERE id=?",
                (now, item["id"]))
        if self.ledger is not None:
            self.ledger.record(
                "parking_evening_surfaced",
                observed={"day": day, "count": len(items),
                          "ids": [i["id"] for i in items]},
                action_taken=f"{len(items)} parked item(s) surfaced "
                             "for the evening")
        return items

    def older_than(self, days: int, limit: int = 20) -> list:
        """Items parked `days`+ ago, still open, not yet
        review-surfaced."""
        cutoff = (self.clock.now_utc()
                  - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.db.query(
            "SELECT * FROM parking_lot WHERE created_at <= ? "
            "AND disposition IS NULL "
            "AND review_surfaced_at IS NULL "
            "ORDER BY created_at LIMIT ?",
            (cutoff, limit))

    def surface_review(self, min_age_days: int = 3,
                       limit: int = 20) -> list:
        """Mark old open items as review-surfaced; return them."""
        items = self.older_than(min_age_days, limit)
        if not items:
            return []
        now = self.clock.now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
        for item in items:
            self.db.execute(
                "UPDATE parking_lot SET review_surfaced_at=? WHERE id=?",
                (now, item["id"]))
        if self.ledger is not None:
            self.ledger.record(
                "parking_review_surfaced",
                observed={"count": len(items),
                          "ids": [i["id"] for i in items]},
                action_taken=f"{len(items)} older parked item(s) "
                             "surfaced for the cold review")
        return items

    def dispose_approved_to_contract(self, record_id: str,
                                     contract_day: str) -> dict:
        """Approved -> the contract for `contract_day` gains a research
        fallback with a time-box. The contract must not be sealed yet;
        the user adds the fallback to the draft (the system does not
        author the contract's fields — commitment precedes temptation)."""
        row = self.get(record_id)
        if row is None:
            raise ValueError(f"no parked item {record_id}")
        if row["disposition"] != "approved":
            raise ValueError(
                "dispose_approved_to_contract requires "
                "disposition='approved'")
        contract = self.db.query_one(
            "SELECT * FROM contract WHERE kind='daily' AND "
            "scope_date=? AND state='SEALED'", (contract_day,))
        if contract is not None:
            raise ValueError(
                f"contract for {contract_day} is already sealed; the "
                "research fallback cannot be added after seal "
                "(commitment precedes temptation)")
        self.db.execute(
            "UPDATE parking_lot SET approved_to_contract_day=? "
            "WHERE id=?", (contract_day, record_id))
        if self.ledger is not None:
            self.ledger.record(
                "parking_approved_to_contract",
                observed={"id": record_id,
                          "question": row["question"],
                          "kind": row["kind"],
                          "contract_day": contract_day},
                action_taken=f"approved for {contract_day} research "
                             "fallback")
        return self.get(record_id)

    def anti_drift(self) -> dict:
        """Detect the parking lot becoming a graveyard or a flood.
        Facts for the aftermath, not verdicts."""
        now = self.clock.now_utc()
        week_ago = (now - timedelta(days=7)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        month_ago = (now - timedelta(days=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")

        parked_week = self.db.query_one(
            "SELECT COUNT(*) AS n FROM parking_lot WHERE created_at >= ?",
            (week_ago,))["n"]
        disposed_week = self.db.query_one(
            "SELECT COUNT(*) AS n FROM parking_lot WHERE "
            "disposition IS NOT NULL AND disposed_at >= ?",
            (week_ago,))["n"]
        graveyard = self.db.query_one(
            "SELECT COUNT(*) AS n FROM parking_lot WHERE created_at <= ? "
            "AND disposition IS NULL", (month_ago,))["n"]

        flood = (parked_week >= 10 and disposed_week <= 2)
        if flood and self.ledger is not None:
            self.ledger.record(
                "parking_flood",
                observed={"parked_week": parked_week,
                          "disposed_week": disposed_week},
                action_taken="parking lot growing faster than "
                             "dispositions")
        if graveyard >= 5 and self.ledger is not None:
            self.ledger.record(
                "parking_graveyard",
                observed={"graveyard_count": graveyard},
                action_taken="30+ day old undisposed items accumulate")
        return {"flood": flood, "graveyard": graveyard >= 5,
                "parked_week": parked_week,
                "disposed_week": disposed_week,
                "graveyard_count": graveyard}

    def for_day_id(self, day_id: str) -> list:
        return self.db.query(
            "SELECT * FROM parking_lot WHERE day_id=? ORDER BY created_at",
            (day_id,))

    def stats(self) -> dict:
        rows = self.db.query(
            "SELECT disposition, COUNT(*) AS n FROM parking_lot "
            "GROUP BY disposition")
        stats = {"parked": 0}
        for r in rows:
            key = r["disposition"] or "parked"
            stats[key] = r["n"]
        return stats


# -- cold review ------------------------------------------------------------

# v0.6.0 (Part 1 §6): the base's six questions are authoritative (the
# v0.5.0 rebuild had silently replaced five of them); the v0.5.0
# additions that do not overlap are kept; mechanism 4 adds
# declared_thinking as the tenth.
REVIEW_QUESTIONS = [
    # From the base (Part 1 §3.11); do not rename or remove.
    ("competence_source",
     "Where did the feeling of competence come from — the task, "
     "or talk about the task?"),
    ("faking_it",
     "You said you were managing. Were you? (D-029 productive "
     "substitution check)"),
    ("wall_or_choice",
     "Did you do the work because the wall was up, or because you "
     "chose to? (graduation meta-metric)"),
    ("out_of_scope_device",
     "Did you use an out-of-scope device (phone/tablet/other machine) "
     "to reach the audience during the window?"),
    ("evidence_quality",
     "Was your accepted evidence substantive or superficial? Name the "
     "weakest one. (recognition mechanism 12)"),
    ("surveillance_comfort",
     "Is what the system captures still acceptable? What should be "
     "narrowed? (recognition mechanism 11)"),
    # From v0.5.0 (kept — genuinely additive, no overlap with above).
    ("targets_honest",
     "Were the targets honest — could they be met on a normal day?"),
    ("toll_worth_it",
     "If the toll was paid: was it worth the declared penalty?"),
    ("what_would_make_tomorrow_sealable",
     "What would make tomorrow's contract sealable by 10:00?"),
    # Mechanism 4 (v0.6.0 Part 2 §2.2): declared thinking.
    ("declared_thinking",
     "Were there questions this week you decided not to answer? "
     "Name one. (declared-thinking: what you decided NOT to research)"),
]

CONDITIONAL_QUESTIONS = {
    "leisure_honored": (
        "Was the declared leisure honored as declared — same label, "
        "same length, no drift past it? (D-047)"),
    "curation_choice": (
        "You surfaced N items this week and opened M. Which of the "
        "items you did not open did you choose not to open, and why? "
        "(asked only when items were surfaced)"),
}


class ColdReviewService:
    def __init__(self, db: Database, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.clock = clock or RealClock()
        self.ledger = ledger

    def questions_for(self, leisure_declared: bool,
                      curation_applicable: bool = False) -> list:
        """The fixed protocol plus the conditionals that apply. The
        caller computes applicability from the record (leisure
        declarations for the scope; surfaced items / reviews in the
        week), never from a guess."""
        qs = list(REVIEW_QUESTIONS)
        if leisure_declared:
            qs.append(("leisure_honored",
                       CONDITIONAL_QUESTIONS["leisure_honored"]))
        if curation_applicable:
            qs.append(("curation_choice",
                       CONDITIONAL_QUESTIONS["curation_choice"]))
        return qs

    def curation_applicable(self, week_start_iso: str) -> bool:
        """v0.7.0 (§3.1, now properly gated): the curation question
        fires only when mirror items were surfaced in the week."""
        row = self.db.query_one(
            "SELECT 1 AS one FROM event WHERE "
            "event_type='content_item_surfaced' AND occurred_at_utc "
            ">= ? LIMIT 1", (week_start_iso + "T00:00:00Z",))
        return row is not None

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
    if emergency_count >= 3:
        lines.append(
            f"emergency exits: {emergency_count} in 7 days. The "
            "pattern is yours to read.")
        lines.append("(threshold: 3 in 7 days; below threshold, this "
                     "line is absent.)")
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


# -- the confrontation file (v0.7.0 Part 3 §3.10) ----------------------------

def build_confrontation_file(db, ledger, week_start_iso, config,
                             clock=None) -> str:
    """A weekly artifact NOT sent anywhere. For the user, not the
    witness. Plain facts from the record: breaks with reasons,
    incomplete sessions, unanswered passes, drift vs declared rest,
    parking lot open items with ages, mirror surfaced-but-not-opened,
    declared alternatives with 0 occurrences, search escapes,
    anti-drift flags. Generated by `dhriti digest --confrontation`."""
    from datetime import timedelta as _td
    clock = clock or RealClock()
    start = week_start_iso + "T00:00:00Z"
    end = (parse_iso(start) + _td(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [f"CONFRONTATION FILE — week {week_start_iso}",
             f"generated: {clock.iso()}",
             "for: you. not sent. not shared.", ""]

    breaks = db.query(
        "SELECT reason, confirmed_at FROM break_glass WHERE "
        "confirmed_at>=? AND confirmed_at<? ORDER BY confirmed_at",
        (start, end))
    lines.append("== breaks (reasons, verbatim) ==")
    for b in breaks:
        lines.append(f"  - {b['reason']}")
    if not breaks:
        lines.append("  (none)")
    lines.append("")

    incomplete = db.query(
        "SELECT task, ended_at FROM session WHERE state='INCOMPLETE' "
        "AND ended_at>=? AND ended_at<?", (start, end))
    lines.append("== incomplete sessions ==")
    for s in incomplete:
        task = s["task"] or "(no task line)"
        lines.append(f"  - {s['ended_at'][:16]}: {task}")
    if not incomplete:
        lines.append("  (none)")
    lines.append("")

    unanswered = db.query(
        "SELECT question, opened_at FROM research_pass WHERE "
        "state='EXPIRED' AND opened_at>=? AND opened_at<?",
        (start, end))
    lines.append("== passes that expired unanswered ==")
    for p in unanswered:
        lines.append(f"  - {p['question'][:120]}")
    if not unanswered:
        lines.append("  (none)")
    lines.append("")

    parked = db.query(
        "SELECT question, created_at, kind FROM parking_lot WHERE "
        "disposition IS NULL ORDER BY created_at")
    lines.append("== parking lot (open, with ages) ==")
    for p in parked:
        age = (clock.now_utc() - parse_iso(p["created_at"])).days
        lines.append(f"  - [{p['kind']}] {p['question']} "
                     f"({age} days)")
    if not parked:
        lines.append("  (empty)")
    lines.append("")

    surfaced_not_opened = db.query(
        "SELECT COUNT(*) AS n FROM event WHERE "
        "event_type='content_item_surfaced' AND occurred_at_utc>=? "
        "AND occurred_at_utc<?", (start, end))
    opened = db.query(
        "SELECT COUNT(*) AS n FROM event WHERE "
        "event_type='content_item_opened' AND occurred_at_utc>=? "
        "AND occurred_at_utc<?", (start, end))
    lines.append("== mirror: surfaced but not opened ==")
    lines.append(f"  surfaced: {surfaced_not_opened[0]['n']}; "
                 f"opened: {opened[0]['n']}")
    lines.append("")

    try:
        from .life_mirror import LifeMirrorService
        life = LifeMirrorService(db, config, clock)
        untouched = life.untouched_this_week(week_start_iso)
        lines.append("== declared alternatives with 0 occurrences ==")
        for label in untouched:
            lines.append(f"  - {label}")
        if not untouched:
            lines.append("  (none)")
        lines.append("")
    except Exception:
        pass

    escapes = db.query(
        "SELECT search_query, searches, unopened, matched_category "
        "FROM (SELECT search_query, COUNT(*) AS searches, "
        "MAX(unopened_count) AS unopened, matched_category FROM "
        "search_escape WHERE search_at>=? AND search_at<? GROUP BY "
        "search_query)", (start, end))
    lines.append("== search escapes ==")
    for e in escapes:
        lines.append(f"  - '{e['search_query']}': {e['searches']} "
                     f"search(es), {e['unopened']} unopened "
                     f"{e['matched_category']}")
    if not escapes:
        lines.append("  (none)")
    lines.append("")
    lines.append("(Plain facts. The reader supplies the judgment.)")
    return "\n".join(lines)


def _week_high_signal_fact(db, week_start_iso) -> str:
    """§4.6: the One True Thing — a single fact selected by a
    deterministic rule (highest-signal metric: unanswered passes >
    breaks > incomplete sessions > mirror drift)."""
    from datetime import timedelta as _td
    start = week_start_iso + "T00:00:00Z"
    end = (parse_iso(start) + _td(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def n(sql, params):
        return db.query_one(sql, params)["n"]

    expired = n("SELECT COUNT(*) AS n FROM research_pass WHERE "
                "state='EXPIRED' AND opened_at>=? AND opened_at<?",
                (start, end))
    breaks = n("SELECT COUNT(*) AS n FROM break_glass WHERE "
               "confirmed_at>=? AND confirmed_at<?", (start, end))
    incomplete = n("SELECT COUNT(*) AS n FROM session WHERE "
                   "state='INCOMPLETE' AND ended_at>=? AND ended_at<?",
                   (start, end))
    dismissed = n("SELECT COUNT(*) AS n FROM event WHERE "
                  "event_type='content_item_dismissed' AND "
                  "occurred_at_utc>=? AND occurred_at_utc<?",
                  (start, end))
    if expired:
        return (f"{expired} research pass(es) expired unanswered "
                "this week.")
    if breaks:
        return f"{breaks} break(s) confirmed this week."
    if incomplete:
        return f"{incomplete} session(s) ended incomplete this week."
    if dismissed:
        return f"{dismissed} mirror item(s) surfaced and dismissed."
    return "a week with nothing to hide: no breaks, no losses."


def build_digest_v070(db, ledger, week_start_iso, config, clock=None):
    """§4.1 witness protocol + §4.6 one true thing + §3.1/§3.2 digest
    lines, applied to the digest text."""
    text = build_digest(db, ledger, week_start_iso, config, clock)
    lines = text.split("\n")
    extras = []
    digest_cfg = config.get("digest_extra", {})
    if digest_cfg.get("one_true_thing_enabled", True):
        fact = _week_high_signal_fact(db, week_start_iso)
        extras.append(f"The one true thing from this week: {fact}")
    # §3.1: the mirror digest line
    mirror_cfg = config.get("mirror", {})
    if mirror_cfg.get("enabled", False):
        from .mirror.store import MirrorStore
        store = MirrorStore(db, config, clock or RealClock())
        facts = store.week_facts(week_start_iso)
        if facts["surfaced"]:
            extras.append(
                f"Mirror: {facts['surfaced']} surfaced, "
                f"{facts['opened']} opened this week.")
        avoided = db.query_one(
            "SELECT COUNT(*) AS n FROM event WHERE "
            "event_type='content_item_dismissed' AND occurred_at_utc"
            ">=?", (week_start_iso + "T00:00:00Z",))["n"]
        if avoided:
            extras.append(f"Avoided: {avoided} item(s) surfaced and "
                          "not opened in the last 30 days.")
    # §3.2: the life digest line
    try:
        from .life_mirror import LifeMirrorService
        life = LifeMirrorService(db, config, clock or RealClock())
        if life.enabled:
            week = life.week_facts(week_start_iso)
            if week["declared_count"]:
                extras.append(
                    f"Life: {week['total_occurrences']} occurrence(s) "
                    f"logged this week against "
                    f"{week['declared_count']} declared "
                    "alternative(s).")
    except Exception:
        pass
    # §4.1: the witness header sentence
    if digest_cfg.get("witness_mode", True) and extras:
        fact = extras[0]
        insert_at = lines.index("== days ==") if "== days ==" in \
            lines else 4
        lines[insert_at:insert_at] = [
            f"This week, in one sentence: {fact}", ""]
    # the remaining extras append before the integrity block
    if len(extras) > 1 or (extras and not digest_cfg.get(
            "witness_mode", True)):
        extra_lines = extras[1:] if digest_cfg.get("witness_mode",
                                                   True) else extras
        insert_at = lines.index("== integrity ==") \
            if "== integrity ==" in lines else len(lines)
        lines[insert_at:insert_at] = ["== the additions =="] + \
            extra_lines + [""]
    return "\n".join(lines)
