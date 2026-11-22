"""Aftermath reports and cold-review packs (PDF section 8).

Contract vs reality, in facts. Two hard rules:

  1. Facts and interpretations never mix in one sentence. "No code
     execution event was recorded for 35 minutes" is a fact; "the user
     was avoiding work" is an interpretation the system cannot establish
     — interpretations appear only in a clearly separated block, if at
     all.
  2. The identity line is the user's own sentence from their contract —
     never generated praise, never shame (dossier 2.2: identity
     reinforcement as reminder, not weapon).

The wall never speaks during a session; the aftermath speaks only in a
cold state (next morning / weekly review).

v0.5.0: rebuilt around `_common_blocks` — one section builder shared by
the day and week reports, so a block added once appears in both.
"""

import html as _html
import json
from datetime import timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .profiles import CATEGORY_DOMAINS
from .stage_ratio import (drift_split, profile_navigation)
from .timeutil import Clock, RealClock, parse_iso, to_iso
import datetime as _dt


class AftermathService:
    def __init__(self, db, config: dict, clock: Optional[Clock] = None,
                 ledger=None, parking_service=None):
        self.db = db
        self.config = config or {}
        self.clock = clock or RealClock()
        self.ledger = ledger
        if parking_service is not None:
            self.parking = parking_service
        else:
            from .review import ParkingLotService
            self.parking = ParkingLotService(self.db, self.clock, ledger)

    # -- data -----------------------------------------------------------------
    def _day_data(self, date_iso: str) -> dict:
        day = self.db.query_one(
            "SELECT * FROM day WHERE date=?", (date_iso,))
        sessions = self.db.query(
            "SELECT * FROM session WHERE day_id=? ORDER BY started_at",
            (day["id"],)) if day else []
        for s in sessions:
            s["day_date"] = date_iso
        evidence = self.db.query(
            "SELECT e.* FROM evidence e JOIN session s "
            "ON e.session_id=s.id WHERE s.day_id=? "
            "ORDER BY e.submitted_at", (day["id"],)) if day else []
        breaks = self.db.query(
            "SELECT * FROM break_glass WHERE confirmed_at LIKE ? "
            "ORDER BY pressed_at", (date_iso + "%",))
        review = self.db.query(
            "SELECT * FROM cold_review WHERE scope=? ORDER BY created_at",
            (f"day:{date_iso}",))
        leisure_rows = self.db.query(
            "SELECT * FROM leisure_declaration WHERE day_date=? "
            "ORDER BY created_at", (date_iso,))
        contract = self._contract_for(day)
        if contract is None:
            # the day row may not exist yet (a report can be requested
            # cold, straight after the seal); the sealed contract is
            # still the record
            from .contract import ContractService
            contract = ContractService(self.db, self.clock).for_day(
                date_iso)
        parks = self.db.query(
            "SELECT * FROM parking_lot WHERE date(created_at)=? "
            "ORDER BY created_at", (date_iso,))
        events = self.db.query(
            "SELECT * FROM event WHERE date(occurred_at_utc)=? "
            "ORDER BY seq", (date_iso,))
        return {
            "scope": f"day:{date_iso}", "date": date_iso, "day": day,
            "sessions": sessions, "evidence": evidence, "breaks": breaks,
            "review": review, "leisure_rows": leisure_rows,
            "contract": contract, "parks": parks, "events": events,
        }

    def _week_data(self, week_start_iso: str) -> dict:
        start = parse_iso(week_start_iso + "T00:00:00Z")
        end = to_iso(start + timedelta(days=7))
        days = self.db.query(
            "SELECT * FROM day WHERE date>=? AND date<? ORDER BY date",
            (week_start_iso, end[:10]))
        sessions = self.db.query(
            "SELECT * FROM session WHERE started_at>=? AND started_at<? "
            "ORDER BY started_at", (week_start_iso, end))
        evidence_rows = self.db.query(
            "SELECT e.class AS class, e.kind AS kind, e.verdict AS verdict "
            "FROM evidence e JOIN session s ON e.session_id=s.id "
            "WHERE s.started_at>=? AND s.started_at<?",
            (week_start_iso, end))
        grouped = {}
        for row in evidence_rows:
            key = (row["verdict"], row["class"], row["kind"])
            grouped[key] = grouped.get(key, 0) + 1
        evidence = [{"verdict": v, "class": c, "kind": k, "n": n}
                    for (v, c, k), n in sorted(grouped.items())]
        breaks = self.db.query(
            "SELECT * FROM break_glass WHERE confirmed_at>=? AND "
            "confirmed_at<?", (week_start_iso, end))
        review = self.db.query(
            "SELECT * FROM cold_review WHERE scope=? ORDER BY created_at",
            (f"week:{week_start_iso}",))
        leisure_rows = self.db.query(
            "SELECT * FROM leisure_declaration WHERE day_date>=? AND "
            "day_date<? ORDER BY created_at",
            (week_start_iso, end[:10]))
        contract = None
        if days:
            contract = self._contract_for(days[-1])
        parks = self.db.query(
            "SELECT * FROM parking_lot WHERE created_at>=? AND created_at<? "
            "ORDER BY created_at", (week_start_iso, end))
        events = self.db.query(
            "SELECT * FROM event WHERE occurred_at_utc>=? AND occurred_at_utc<? "
            "ORDER BY seq", (week_start_iso, end))
        return {
            "scope": f"week:{week_start_iso}",
            "date": week_start_iso, "day": days[-1] if days else None,
            "days": days, "sessions": sessions, "evidence": evidence,
            "breaks": breaks, "review": review,
            "leisure_rows": leisure_rows, "contract": contract,
            "parks": parks, "events": events,
        }

    def _contract_for(self, day: Optional[dict]) -> Optional[dict]:
        if not day or not day.get("contract_id"):
            return None
        row = self.db.query_one(
            "SELECT * FROM contract WHERE id=?", (day["contract_id"],))
        if row:
            row["payload"] = json.loads(row["payload_json"])
        return row

    # -- reports ----------------------------------------------------------------
    def day_report(self, date_iso: str) -> dict:
        data = self._day_data(date_iso)
        return self._render(f"day {date_iso}", data["scope"], data)

    def week_report(self, week_start_iso: str) -> dict:
        data = self._week_data(week_start_iso)
        report = self._render(
            f"week {week_start_iso}", data["scope"], data)
        # the week report carries the parking-lot week section on top
        # of the common blocks
        extra = []
        self._parking_week_block(extra, data)
        md = report["markdown"]
        marker = "## Proof"
        if marker in md:
            md = md.replace(marker, "\n".join(extra) + marker, 1)
        else:
            md += "\n" + "\n".join(extra)
        report["markdown"] = md
        report["md"] = md
        return report

    # -- the shared blocks --------------------------------------------------------
    def _common_blocks(self, data: dict) -> list:
        """The section builders, in report order. v0.7.0 (§4.15): the
        blocks are grouped into five views (Wall, Mirror, Conversation
        Boundary, Evidence Record, Experiment) with a
        'coverage missing' line per view; when aftermath_views.
        five_views is False the v0.6.0 flat order is kept."""
        lines = []
        if (self.config.get("aftermath_views", {})
                .get("five_views", True)):
            self._five_views(lines, data)
            return lines
        self._exchange_block(lines, data)
        self._contract_block(lines, data)
        self._reality_block(lines, data)
        self._consumption_block(lines, data)
        self._ratio_block(lines, data)
        self._leisure_block(lines, data)
        self._research_ratio_block(lines, data)
        self._proof_block(lines, data)
        self._breaks_block(lines, data)
        self._ladder_block(lines, data)
        self._loop_block(lines, data)
        self._parking_block(lines, data)
        self._evening_block(lines, data)
        self._review_block(lines, data)
        self._body_register_block(lines, data)
        self._absence_block(lines, data)
        self._facts_block(lines, data)
        return lines

    # -- the five views (v0.7.0 §4.15) --------------------------------------
    def _five_views(self, lines, data):
        """Wall / Mirror / Conversation Boundary / Evidence Record /
        Experiment — each view groups its blocks and names what it
        CANNOT see (coverage missing), because an honest gap beats a
        confident blank."""
        # View 1: the Wall (what was blocked and when)
        lines.append("## View: the Wall")
        self._reality_block(lines, data)
        self._consumption_block(lines, data)
        self._ratio_block(lines, data)
        self._breaks_block(lines, data)
        self._ladder_block(lines, data)
        wall_coverage = ["adapter coverage is E1 only unless "
                         "configured", "out-of-scope devices are "
                         "self-reported"]
        lines.append("Coverage missing: " + "; ".join(wall_coverage)
                     + ".")
        lines.append("")

        # View 2: the Mirror (saved content, the life mirror, bounds,
        # chosen rest vs drift)
        lines.append("## View: the Mirror")
        self._record_block(lines, data)
        self._life_block(lines, data)
        self._bounds_block(lines, data)
        self._leisure_block(lines, data)
        lines.append("Coverage missing: the mirror is off until "
                     "enabled cold; device minutes are a weighted "
                     "count, not a timer.")
        lines.append("")

        # View 3: the Conversation Boundary (passes, ratio, parking)
        lines.append("## View: the Conversation Boundary")
        self._research_ratio_block(lines, data)
        self._parking_block(lines, data)
        self._evening_block(lines, data)
        lines.append("Coverage missing: AI-chat prompt content is "
                     "never read unless the topic-lock (L-9) is "
                     "enabled cold.")
        lines.append("")

        # View 4: the Evidence Record
        lines.append("## View: the Evidence Record")
        self._proof_block(lines, data)
        self._loop_block(lines, data)
        self._facts_block(lines, data)
        lines.append("Coverage missing: observed-evidence adapters "
                     "are opt-in; manual claims are kept but never "
                     "accepted.")
        lines.append("")

        # View 5: the Experiment (the contract, the exchange over
        # time, the review)
        lines.append("## View: the Experiment")
        self._contract_block(lines, data)
        self._body_register_block(lines, data)
        self._exchange_block(lines, data)
        self._identity_revision_block(lines, data)
        self._complexity_budget_block(lines, data)
        self._guard_block(lines, data)
        self._review_block(lines, data)
        self._absence_block(lines, data)
        lines.append("Coverage missing: taper decisions need 30+ "
                     "days of data; correlations appear when the "
                     "weeks exist.")
        lines.append("")

    def _guard_block(self, lines, data):
        """Guard Kit telemetry: park:break ratio, active mode, and interruption stage (D-071..D-089)."""
        from .guard_metrics import park_break_ratio, render_guard_block, kill_chain_attribution
        from .content_store import ContentStore
        from .chat_guard import GuardState, snapshot_for_digest
        import time

        parks_count = len(data.get("parks") or [])
        breaks_count = len(data.get("breaks") or [])
        ratio = park_break_ratio([{"label": data.get("date", "today"), "parks": parks_count, "breaks": breaks_count}])
        chain = kill_chain_attribution(data.get("events") or [])

        guard_db_path = self.db.path.parent / "guard_content.sqlite3" if hasattr(self.db, "path") and self.db.path else None
        snap = {}
        if guard_db_path and guard_db_path.exists():
            try:
                store = ContentStore(str(guard_db_path))
                raw = store.kv_get("guard_state")
                if raw:
                    st = GuardState.from_snapshot(raw)
                    snap = snapshot_for_digest(st, time.time())
            except Exception:
                pass
        if not snap:
            snap = {"mode": "CHECKPOINT", "prompt_budget_used": 0, "prompt_budget_limit": 15,
                    "debt_value": 0.0, "debt_ceiling": 10.0, "open_threads": []}

        block_text = render_guard_block(snap, ratio, chain, [])
        lines.append(block_text)
        lines.append("")

    def _record_block(self, lines, data):
        """§3.1: the mirror's record — saved, surfaced, opened,
        completed, dismissed, abandoned, oldest, re-saves, search
        escapes, by category."""
        mirror_cfg = self.config.get("mirror", {})
        if not mirror_cfg.get("enabled", False):
            return
        from .mirror.store import MirrorStore
        store = MirrorStore(self.db, self.config, self.clock,
                            self.ledger)
        week = data.get("date")
        facts = store.week_facts(week) if week else None
        if not facts:
            return
        lines.append("### The record")
        lines.append(f"- Saved this week: {facts['saved']} item(s)")
        lines.append(
            f"- Surfaced: {facts['surfaced']}; Opened: "
            f"{facts['opened']}; Completed: {facts['completed']}; "
            f"Dismissed: {facts['dismissed']}; Abandoned: "
            f"{facts['abandoned']}")
        oldest = facts.get("oldest_unopened")
        if oldest:
            age = (self.clock.now_utc()
                   - parse_iso(oldest["saved_at_utc"])).days
            lines.append(f"- Oldest unopened: {age} days "
                         f"({oldest['title'][:60]})")
        lines.append(f"- Re-saves this week: {facts['resaved_total']}")
        # search escapes (§3.4)
        from .search_escape import SearchEscapeDetector
        detector = SearchEscapeDetector(self.db, self.config,
                                        self.clock, self.ledger)
        escapes = detector.week_summary(week)
        if escapes:
            lines.append(f"- Search escapes this week: {len(escapes)}")
            for row in escapes[:5]:
                lines.append(
                    f"  - '{row['search_query']}' -> "
                    f"{row['searches']} search(es), "
                    f"{row['unopened']} unopened "
                    f"{row['matched_category']} item(s)")
        if facts["by_category"]:
            lines.append("")
            lines.append("### By category")
            lines.append("| Category | Saved |")
            lines.append("|---|---|")
            for row in facts["by_category"]:
                lines.append(f"| {row['category']} | {row['saved']} |")
        self._abandonment_rate_fact(lines)

    def _abandonment_rate_fact(self, lines):
        """§3.6: the abandonment-rate comparison — 'You abandon X
        items at 3x the rate of Y items. Is X still an interest?'
        A fact, not a verdict; fires only when the top category has
        enough history for the ratio to mean something (3+ items,
        2+ abandoned) and a comparison category exists."""
        rows = self.db.query(
            "SELECT category, COUNT(*) AS total, "
            "SUM(CASE WHEN abandoned_at IS NOT NULL THEN 1 ELSE 0 "
            "END) AS abandoned FROM content_item WHERE category != "
            "'unknown' GROUP BY category HAVING total >= 3")
        rates = [(r["category"], r["abandoned"] / r["total"],
                  r["abandoned"]) for r in rows]
        if len(rates) < 2:
            return
        rates.sort(key=lambda kv: -kv[1])
        (top_cat, top_rate, top_n) = rates[0]
        (low_cat, low_rate, _) = rates[-1]
        if top_n < 2 or top_rate <= low_rate:
            return
        if top_rate >= 2 * max(low_rate, 0.01):
            if low_rate > 0:
                ratio = max(2, round(top_rate / low_rate))
                ratio_str = f"{ratio}x the rate of"
            else:
                ratio_str = "a far higher rate than"
            lines.append("")
            lines.append(
                f"You abandon '{top_cat}' items at {ratio_str} "
                f"'{low_cat}' items. Is '{top_cat}' still an "
                "interest? (a fact, not a verdict)")

    def _life_block(self, lines, data):
        """§3.2: the life mirror — declared alternatives vs device
        use, the two numbers."""
        from .life_mirror import LifeMirrorService
        life = LifeMirrorService(self.db, self.config, self.clock,
                                 self.ledger)
        if not life.enabled:
            return
        week = data.get("date")
        if not week:
            return
        facts = life.week_facts(week)
        if not facts["declared_count"]:
            return
        lines.append("### The life (declared alternatives)")
        lines.append("")
        lines.append("You declared these, cold. This is what the "
                     "record says about the last 7 days:")
        lines.append("")
        for alt in facts["alternatives"]:
            minimum = (f" (minimum: '{alt['minimum_version']}')"
                       if alt["minimum_version"] else "")
            lines.append(
                f"- {alt['kind']}: '{alt['label']}' — logged "
                f"{alt['occurrences']} of 7 days{minimum}")
        device_minutes = self._device_use_minutes(week)
        lines.append("")
        lines.append(f"Device use this week: "
                     f"{self._format_minutes(device_minutes)}.")
        lines.append(f"Life logged: {facts['total_occurrences']} "
                     "occurrence(s).")
        lines.append("")
        lines.append("The system does not tell you what to do with "
                     "this. It shows the two numbers.")

    def _device_use_minutes(self, week_start_iso: str) -> int:
        """Evening device use (§3.3): consumption navigations after
        window_end, weighted (config minutes_per_navigation — the
        honest number is unknown; the weight states the assumption)."""
        weight = float(self.config.get("declared_bounds", {}).get(
            "minutes_per_navigation", 3))
        from .stage_ratio import consumption_category
        count = 0
        for row in self.db.query(
                "SELECT occurred_at_utc, observed_payload FROM event "
                "WHERE event_type='browser_navigation' AND "
                "occurred_at_utc >= ? AND occurred_at_utc < ?",
                (week_start_iso + "T00:00:00Z",
                 (parse_iso(week_start_iso + "T00:00:00Z")
                  + timedelta(days=7)).strftime(
                      "%Y-%m-%dT%H:%M:%SZ"))):
            try:
                payload = json.loads(row["observed_payload"] or "{}")
            except Exception:
                continue
            if not consumption_category(payload.get("url", "")):
                continue
            # after window_end on that day (the day row when it
            # exists; the config-resolved window otherwise — a report
            # can be requested for a day that never opened)
            date = row["occurred_at_utc"][:10]
            day = self.db.query_one(
                "SELECT window_end_at FROM day WHERE date=?", (date,))
            window_end = day["window_end_at"] if day else None
            if not window_end:
                from .day_window import resolve_window
                try:
                    window_end = to_iso(resolve_window(
                        _dt.date.fromisoformat(date),
                        self.config).window_end)
                except Exception:
                    window_end = None
            if window_end and row["occurred_at_utc"] > window_end:
                count += 1
        return int(count * weight)

    @staticmethod
    def _format_minutes(minutes: int) -> str:
        hours, mins = divmod(int(minutes), 60)
        if hours:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def _bounds_block(self, lines, data):
        """§3.3: declared device-use bounds — measurement, not
        verdict."""
        bounds = self.config.get("declared_bounds", {})
        week = data.get("date")
        if not week:
            return
        declared = int(bounds.get("evening_minutes", 60))
        used = self._device_use_minutes(week)
        gap = used - declared
        lines.append("### Declared device bounds")
        lines.append(f"Evening device time: "
                     f"{self._format_minutes(used)} this week. "
                     f"Declared bound: {declared} minutes.")
        if gap > 0:
            lines.append(f"The gap is: {self._format_minutes(gap)} "
                         "over.")
        else:
            lines.append("Inside the declared bound.")
        lines.append("(This is a measurement, not a verdict. The "
                     "bound is yours.)")

    def _absence_block(self, lines, data):
        """§4.3: the day after an absence test — one question, no
        telemetry behind it (the system was off; that was the
        point)."""
        day = data.get("date")
        if not day:
            return
        row = self.db.query_one(
            "SELECT 1 AS one FROM absence_day WHERE date=?", (day,))
        if row is None:
            return
        lines.append("The absence test: you ran the day without the "
                     "system. Did you miss it?")
        lines.append("")

    def _body_register_block(self, lines, data):
        """§4.4: the physical register — one sentence about the body,
    asked at the ritual, stored in the contract, shown here. No
    correlation yet (needs weeks of data); the field is stored, and
    correlations appear in analysis/measures.py once the weeks
    exist."""
        contract = data.get("contract") or {}
        payload = contract.get("payload") or {}
        body = payload.get("body_register")
        if not body:
            return
        lines.append(f"Body this week: '{body}'")
        lines.append("")

    def _ladder_block(self, lines, data):
        """§4.19: the earned break-glass ladder — breaks this month
        and the current friction tier, as a fact."""
        from .break_glass_friction import FrictionLadder
        ladder = FrictionLadder(self.db, self.config, self.clock,
                                self.ledger)
        summary = ladder.month_summary()
        if not summary["breaks_30d"] \
                and summary["current_tier"] == "baseline":
            return
        tier = summary["current_tier"]
        if tier != "baseline":
            lines.append(
                f"Break-glass this month: {summary['breaks_30d']}. "
                f"Current tier: '{tier}' (escalated from 'baseline').")
        else:
            lines.append(
                f"Break-glass this month: {summary['breaks_30d']}. "
                "Current tier: 'baseline'.")
        lines.append("")

    def _identity_revision_block(self, lines, data):
        """§4.18: preservation as identity revision — the sequence of
        main_belief_current_state values. Not a verdict. A record."""
        from .contract import ContractService
        contracts = ContractService(self.db, self.clock, self.ledger)
        history = contracts.get_history_of_field(
            "main_belief_current_state")
        if len(history) < 1:
            return
        lines.append("### Your current state, over time")
        for row in history:
            lines.append(f"- {row['date']}: "
                         f"'{str(row['value'])[:120]}'")
        lines.append("")

    def _complexity_budget_block(self, lines, data):
        """§4.17: complexity budget vs actual time-on-system."""
        contract = data.get("contract") or {}
        payload = contract.get("payload") or {}
        budget = payload.get("complexity_budget_minutes")
        if not budget:
            return
        # actual: dhriti-specific events this week as a proxy (each
        # operator action ~30s; the proxy is stated as a proxy)
        week = data.get("date")
        if week:
            rows = self.db.query(
                "SELECT COUNT(*) AS n FROM event WHERE "
                "occurred_at_utc >= ? AND occurred_at_utc < ? AND "
                "source_adapter='core'",
                (week + "T00:00:00Z",
                 (parse_iso(week + "T00:00:00Z")
                  + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")))
            actual = int((rows[0]["n"] if rows else 0) * 0.5)
            lines.append(f"Complexity budget: {budget} minutes/week. "
                         f"Actual this week: ~{actual} minutes "
                         "(event-count proxy).")

    def _exchange_block(self, lines, data):
        """The D-030 exchange: the main belief and its exchange rate
        with substitutes, restored in v0.6.0 (Part 1 §5.2)."""
        contract = data.get("contract")
        if not contract:
            return
        payload = contract.get("payload") or {}
        belief = payload.get("main_belief") or {}
        if not payload.get("main_belief_metric"):
            return
        lines.append("## The exchange")
        lines.append(f"- Main belief: {belief.get('label', '')}")
        lines.append(f"- Metric that would prove it: "
                     f"{payload['main_belief_metric']}")
        lines.append(f"- Current state (your words, cold): "
                     f"{payload.get('main_belief_current_state', '')}")
        substitutes = payload.get("substitute_activities") or []
        lines.append(f"- Declared substitutes: "
                     f"{', '.join(substitutes)}")
        lines.append(f"- Substitute budget: "
                     f"{payload.get('substitute_budget', '')}")
        if payload.get("declared_unknowns"):
            lines.append("- Declared unknowns:")
            for unknown in payload["declared_unknowns"]:
                if isinstance(unknown, dict):
                    lines.append(f"  - {unknown.get('topic', '')} "
                                 f"({unknown.get('current_state', '')})")
        sessions = data.get("sessions") or []
        success = sum(1 for s in sessions
                      if s.get("state") == "SUCCESS")
        lines.append(f"- Observed this scope: {len(sessions)} session(s), "
                     f"{success} with accepted evidence.")
        lines.append("(The system does not judge the exchange. "
                     "It shows the two sides.)")
        lines.append("")

    def _research_ratio_block(self, lines, data):
        """Mechanism 10 (v0.6.0 Part 2 §2.4): research minutes vs
        application minutes per session, computed from the research
        passes' opened/returned timestamps."""
        ratio_data = self._research_to_application_ratio(
            data.get("date"))
        if not ratio_data:
            return
        lines.append("## Research-to-application ratio")
        for sid, m in ratio_data.items():
            ratio_str = (f"{m['ratio']}:1" if m["ratio"] is not None
                         else "no application time")
            lines.append(
                f"- session {sid[:8]}: {m['research_minutes']} min "
                f"research / {m['application_minutes']} min application "
                f"({ratio_str})")
        for sid, m in ratio_data.items():
            if m["ratio"] is not None and m["ratio"] > 2.0:
                lines.append(
                    f"- NOTE (session {sid[:8]}): research exceeds "
                    "application 2:1. The metrics show the exchange; "
                    "you read it.")
        lines.append("")

    def _research_to_application_ratio(self, date: str) -> dict:
        """Minutes in-pass vs out-of-pass per session (mechanism 10)."""
        if not date:
            return {}
        sessions = self.db.query(
            "SELECT id, started_at, ended_at FROM session "
            "WHERE day_id = (SELECT id FROM day WHERE date=?)",
            (date,))
        result = {}
        for s in sessions:
            if not s["ended_at"]:
                continue
            try:
                session_minutes = (
                    parse_iso(s["ended_at"])
                    - parse_iso(s["started_at"])).total_seconds() / 60
            except Exception:
                continue
            passes = self.db.query(
                "SELECT opened_at, returned_at FROM research_pass "
                "WHERE session_id=? AND returned_at IS NOT NULL",
                (s["id"],))
            research_minutes = 0.0
            for p in passes:
                try:
                    research_minutes += (
                        parse_iso(p["returned_at"])
                        - parse_iso(p["opened_at"])
                    ).total_seconds() / 60
                except Exception:
                    continue
            application_minutes = max(0.0, session_minutes
                                      - research_minutes)
            result[s["id"]] = {
                "research_minutes": round(research_minutes, 1),
                "application_minutes": round(application_minutes, 1),
                "ratio": (round(research_minutes / application_minutes, 2)
                          if application_minutes > 0 else None),
            }
        return result

    def _evening_block(self, lines, data):
        """v0.6.0 Part 2 §1.3: the earned-evening surfacing of parked
        items — the parking lot handed back at the moment it can be
        followed, only after the day's targets were met."""
        day = data.get("day")
        if not (day and day.get("targets_met")):
            return
        evening_items = self.parking.evening_all(day["date"])
        if not evening_items:
            return
        lines.append("## The evening is yours")
        lines.append("You earned it. You parked these today:")
        for item in evening_items:
            spark = ""
            if item.get("sparked_by_url"):
                spark = f" (sparked by: {item['sparked_by_url']})"
            lines.append(f"- [{item['kind']}] {item['question']}{spark}")
        lines.append("")
        lines.append("Pick one, or don't. The list is yours — it does not "
                     "come back until you ask for it in the cold review.")
        lines.append("")

    def _contract_block(self, lines, data):
        contract = data.get("contract")
        lines.append("## Contract (written cold)")
        if not contract:
            lines.append("_(no sealed contract for this scope)_")
            lines.append("")
            return
        payload = contract["payload"]
        lines.append(f"- Contract line: {payload.get('contract_line', '')}")
        lines.append(f"- Profile: {payload.get('profile', '')}")
        for target in payload.get("targets", []):
            ev = target.get("evidence", {})
            spec = ev.get("command") or ev.get("path") or ev.get("class")
            lines.append(f"- Target: {target.get('label')} "
                         f"(evidence: {spec})")
        if payload.get("research_fallback"):
            fb = payload["research_fallback"]
            lines.append(f"- Research fallback: {fb.get('scope')} "
                         f"(max {fb.get('max_minutes')} min)")
        lines.append("")

    def _reality_block(self, lines, data):
        lines.append("## Reality (what was observed)")
        sessions = data.get("sessions") or []
        if not sessions:
            lines.append("_(no sessions recorded)_")
        for s in sessions:
            task = s.get("task") or "(no task line)"
            ended = f" -> {s['state']}" if s.get("ended_at") else ""
            lines.append(f"- Session `{s['id'][:8]}`{ended}: {task}")
        days = data.get("days")
        if days:
            for d in days:
                lines.append(f"- {d['date']}: {d['state']} "
                             f"(targets "
                             f"{'met' if d['targets_met'] else 'unmet'})")
        elif data.get("day"):
            d = data["day"]
            lines.append(f"- Day {d['date']}: {d['state']} "
                         f"(targets "
                         f"{'met' if d['targets_met'] else 'unmet'})")
        lines.append("")

    def _consumption_block(self, lines, data):
        lines.append("## Consumption facts (categories, observed)")
        counts, total = self._navigation_counts(data)
        if not total:
            lines.append("_(no navigation observed)_")
            lines.append("")
            return
        lines.append(f"{total} navigation(s) observed, by category:")
        for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {cat}: {n}")
        # D-048: evening navigations (after window_end) are named as
        # such — the measured hole, not a verdict.
        evening = self._evening_count(data)
        if evening:
            lines.append(f"{evening} after window_end (evening)")
        lines.append("")

    def _evening_count(self, data) -> int:
        dates = []
        if data.get("days"):
            dates = [d["date"] for d in data["days"]]
        elif data.get("day"):
            dates = [data["day"]["date"]]
        elif data.get("date"):
            dates = [data["date"]]
        from .day_window import resolve_window
        evening = 0
        for row in self.db.query(
                "SELECT occurred_at_utc, observed_payload FROM event "
                "WHERE event_type='browser_navigation'"):
            when = row["occurred_at_utc"][:10]
            if when not in dates:
                continue
            try:
                payload = json.loads(row["observed_payload"] or "{}")
            except Exception:
                continue
            url = payload.get("url", "")
            from .stage_ratio import consumption_category
            cat = consumption_category(url) or ""
            if not cat or cat not in CATEGORY_DOMAINS:
                continue
            date_obj = _dt.date.fromisoformat(when)
            win = resolve_window(date_obj, self.config)
            if parse_iso(row["occurred_at_utc"]) > win.window_end:
                evening += 1
        return evening

    def _ratio_block(self, lines, data):
        lines.append("## Stage ratio (audience share, observed)")
        counts, total = self._navigation_counts(data)
        if not total:
            lines.append("_(no navigation observed)_")
            lines.append("")
            return
        consumption = sum(n for cat, n in counts.items()
                          if cat in CATEGORY_DOMAINS)
        share = consumption / total if total else 0
        lines.append(f"Audience share of observed navigation: "
                     f"{round(share * 100)}% "
                     f"({consumption} of {total} navigations)")
        lines.append("endorsed band: 20-30% audience (Specimen 001); "
                     "counts, not minutes")
        lines.append("")

    def _leisure_block(self, lines, data):
        lines.append("## Declared rest vs drift")
        leisure_rows = data.get("leisure_rows") or []
        if leisure_rows:
            minutes = sum(r["planned_minutes"] for r in leisure_rows)
            lines.append(f"Declared rest: {len(leisure_rows)} "
                         f"window(s), {minutes} minutes total")
            for row in leisure_rows:
                lines.append(f"- {row['activity']} "
                             f"({row['planned_minutes']} min, "
                             f"ends {row['ends_at']})")
        else:
            lines.append("_(no leisure declared)_")
        drift = self._drift_count(data)
        lines.append(f"Drift: {drift} consumption navigation(s) "
                     "outside declared windows")
        lines.append("")

    def _proof_block(self, lines, data):
        lines.append("## Proof")
        rows = data.get("evidence") or []
        if not rows:
            lines.append("_(no evidence submitted)_")
            lines.append("")
            return
        for e in rows:
            count = f" ×{e['n']}" if "n" in e else ""
            lines.append(f"- [{e['verdict']}] {e['class']}/{e['kind']}"
                         f"{count}: "
                         f"{e.get('verdict_reason') or ''}")
        lines.append("")

    def _breaks_block(self, lines, data):
        lines.append("## Breaks")
        rows = data.get("breaks") or []
        if not rows:
            lines.append("_(none)_")
            lines.append("")
            return
        for b in rows:
            when = (b.get("confirmed_at") or b.get("pressed_at", ""))[:16]
            lines.append(f"- {when}: {b.get('reason') or '(unconfirmed)'}")
        lines.append("")

    def _loop_block(self, lines, data):
        lines.append("## Loop log (event summary)")
        scope = data.get("scope", "")
        if self.ledger is None:
            lines.append("_(ledger unavailable)_")
            lines.append("")
            return
        date = data.get("date")
        rows = self.ledger.events(since_utc=date + "T00:00:00Z")
        shown = 0
        for row in rows:
            if date and not row["occurred_at_utc"].startswith(date) \
                    and scope.startswith("day:"):
                continue
            if shown >= 40:
                lines.append(f"... ({len(rows)} events total)")
                break
            lines.append(f"- {row['occurred_at_utc'][11:16]} "
                         f"{row['event_type']}")
            shown += 1
        if not rows:
            lines.append("_(no events)_")
        lines.append("")

    def _parking_block(self, lines, data):
        lines.append("## Parking lot (open)")
        open_items = self.parking.open_items()
        if not open_items:
            lines.append("_(empty)_")
            lines.append("")
        else:
            for item in open_items:
                spark = ""
                if item.get("sparked_by_url"):
                    spark = (f" (sparked by: "
                             f"{item['sparked_by_url']})")
                lines.append(f"- [{item['kind']}] "
                             f"{item['question']}{spark}")
            lines.append("")
        # §3.6: the week's drop reasons, on the day report too (the
        # day report is the surface the operator actually reads)
        day = data.get("date")
        if day:
            monday = (_dt.date.fromisoformat(day)
                      - _dt.timedelta(
                          days=_dt.date.fromisoformat(day)
                          .weekday())).isoformat()
            self._dropped_this_week(lines, monday)

    def _dropped_this_week(self, lines, week_start_iso: str):
        """§3.6: the week's parking-lot drops with their typed
        reasons (dropping requires one)."""
        if not week_start_iso:
            return
        week_end = (parse_iso(week_start_iso + "T00:00:00Z")
                    + timedelta(days=7)).strftime("%Y-%m-%d")
        dropped = self.db.query(
            "SELECT question, note FROM parking_lot WHERE "
            "disposition='dropped' AND disposed_at >= ? AND "
            "disposed_at < ?",
            (week_start_iso + "T00:00:00Z",
             week_end + "T00:00:00Z"))
        if dropped:
            lines.append("Dropped this week, with the reasons:")
            for item in dropped:
                lines.append(f"- {item['question'][:60]} — "
                             f"{item['note'][:120]}")
            lines.append("")

    def _parking_week_block(self, lines, data):
        """Part 2 §1.3: the week's parked items, the older ones still
        open with their ages, and the anti-drift flags — the parking
        lot read cold, as facts."""
        lines.append("## Parking lot (the week)")
        dates = [d["date"] for d in (data.get("days") or [])]
        start = dates[0] if dates else data.get("date")
        end = dates[-1] if dates else data.get("date")
        open_items = self.db.query(
            "SELECT * FROM parking_lot WHERE disposition IS NULL "
            "AND created_at >= ? AND created_at < ?",
            (start + "T00:00:00Z", end + "T23:59:59Z")) \
            if start and end else []
        older = self.parking.older_than(3, limit=10)
        if open_items:
            lines.append("Parked this week:")
            for item in open_items:
                spark = (f" (sparked by: {item['sparked_by_url']})"
                         if item.get("sparked_by_url") else "")
                lines.append(f"- [{item['kind']}] "
                             f"{item['question']}{spark}")
        else:
            lines.append("Nothing parked this week.")
        if older:
            lines.append("")
            lines.append("Older items still open:")
            for item in older:
                age_days = (self.clock.now_utc()
                            - parse_iso(item["created_at"])).days
                lines.append(f"- [{item['kind']}] {item['question']} "
                             f"({age_days} days)")
        anti = self.parking.anti_drift()
        if anti["flood"]:
            lines.append("")
            lines.append(
                f"Parking flood: {anti['parked_week']} parked, "
                f"{anti['disposed_week']} disposed this week. "
                "The lot is growing faster than you are reading it.")
        if anti["graveyard"]:
            lines.append("")
            lines.append(
                f"Parking graveyard: {anti['graveyard_count']} items "
                "are 30+ days old and undisposed. Let them go or "
                "face them.")
        # §3.6: the week's drop reasons — dropping requires a reason;
        # the reason is contract-design feedback, shown cold
        dropped = self.db.query(
            "SELECT question, note FROM parking_lot WHERE "
            "disposition='dropped' AND disposed_at >= ? AND "
            "disposed_at < ?",
            (start + "T00:00:00Z", end + "T23:59:59Z")) \
            if start and end else []
        if dropped:
            lines.append("")
            lines.append("Dropped this week, with the reasons:")
            for item in dropped:
                lines.append(f"- {item['question'][:60]} — "
                             f"{item['note'][:120]}")
        lines.append("")

    def _review_block(self, lines, data):
        lines.append("## Cold review answers (submitted, not verified)")
        rows = data.get("review") or []
        if not rows:
            lines.append("_(none this scope)_")
            lines.append("")
            return
        for r in rows:
            lines.append(f"- {r['question_key']}: {r['answer'][:200]}")
        lines.append("")

    def _facts_block(self, lines, data):
        lines.append("## Facts vs interpretation")
        sessions = data.get("sessions") or []
        accepted = [e for e in (data.get("evidence") or [])
                    if e.get("verdict") == "ACCEPTED"]
        lines.append(f"- Fact: {len(sessions)} session(s), "
                     f"{len(accepted)} accepted evidence row(s), "
                     f"{len(data.get('breaks') or [])} break(s).")
        lines.append("- Interpretation: none offered. The reader "
                     "supplies it; the record does not.")
        lines.append("")

    def _identity_line(self, data) -> str:
        contract = data.get("contract")
        if not contract:
            return ""
        return contract["payload"].get("identity_statement", "")

    # -- navigation helpers ------------------------------------------------------
    def _navigation_counts(self, data) -> tuple:
        dates = []
        if data.get("days"):
            dates = [d["date"] for d in data["days"]]
        elif data.get("day"):
            dates = [data["day"]["date"]]
        elif data.get("date"):
            dates = [data["date"]]
        counts, total = {}, 0
        for date in dates:
            prof = profile_navigation(
                self.db, self.config,
                _dt.date.fromisoformat(date))
            total += prof["total"]
            for cat, n in prof["counts"].items():
                counts[cat] = counts.get(cat, 0) + n
        return counts, total

    def _drift_count(self, data) -> int:
        dates = []
        if data.get("days"):
            dates = [d["date"] for d in data["days"]]
        elif data.get("day"):
            dates = [data["day"]["date"]]
        elif data.get("date"):
            dates = [data["date"]]
        drift = 0
        for date in dates:
            prof = profile_navigation(
                self.db, self.config, _dt.date.fromisoformat(date))
            drift += drift_split(
                prof["consumption_events"],
                data.get("leisure_rows") or [])["drift"]
        return drift

    # -- render ----------------------------------------------------------------
    def _render(self, title: str, scope: str, data: dict) -> dict:
        blocks = self._common_blocks(data)
        identity = self._identity_line(data)
        head = self.ledger.head() if self.ledger else {
            "row_hash": "(no ledger)"}
        chain = self.ledger.verify_chain() if self.ledger else {
            "ok": None, "checked": 0}

        # Bug B (v0.6.0): the identity line is the first thing in the
        # report — before "Contract (written cold)" — not the footer.
        # The identity statement is shown, not spaced.
        md = [f"# Dhriti aftermath — {title}", ""]
        md.append(f"Scope: {scope}")
        md.append(f"Generated: {self.clock.iso()}")
        md.append("")
        if identity:
            md.append(f"""{identity}""")
            md.append("")
        md.extend(blocks)
        md.append("---")
        md.append(f"Ledger head at generation: `{head['row_hash']}`")
        md.append(f"Chain verified: {chain['ok']} "
                  f"({chain['checked']} events)")
        markdown = "\n".join(md)

        html = ["<h1>Dhriti aftermath</h1>"]
        html.append(f"<p>Scope: {_html.escape(scope)}</p>")
        if identity:
            html.append("<blockquote>"
                        + _html.escape(identity) + "</blockquote>")
        for line in blocks:
            if line.startswith("## "):
                html.append(f"<h2>{_html.escape(line[3:])}</h2>")
            elif line.startswith("- "):
                html.append(f"<div>{_html.escape(line[2:])}</div>")
            elif line.strip():
                html.append(f"<p>{_html.escape(line)}</p>")
        return {"markdown": markdown, "html": "\n".join(html),
                "md": markdown}

    def write(self, report: dict, out_dir: Path, stem: str) -> dict:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"{stem}.md"
        md_path.write_text(report["markdown"], encoding="utf-8")
        html_path = out_dir / f"{stem}.html"
        html_path.write_text(report["html"], encoding="utf-8")
        return {"markdown": md_path, "html": html_path}
