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
        return {
            "scope": f"day:{date_iso}", "date": date_iso, "day": day,
            "sessions": sessions, "evidence": evidence, "breaks": breaks,
            "review": review, "leisure_rows": leisure_rows,
            "contract": self._contract_for(day),
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
        return {
            "scope": f"week:{week_start_iso}",
            "date": week_start_iso, "day": days[-1] if days else None,
            "days": days, "sessions": sessions, "evidence": evidence,
            "breaks": breaks, "review": review,
            "leisure_rows": leisure_rows, "contract": contract,
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
        return self._render(
            f"week {week_start_iso}", data["scope"], data)

    # -- the shared blocks --------------------------------------------------------
    def _common_blocks(self, data: dict) -> list:
        """The section builders, in report order. v0.5.0 order keeps
        the identity line at the bottom (v0.3.0 heritage)."""
        lines = []
        self._contract_block(lines, data)
        self._reality_block(lines, data)
        self._consumption_block(lines, data)
        self._ratio_block(lines, data)
        self._leisure_block(lines, data)
        self._proof_block(lines, data)
        self._breaks_block(lines, data)
        self._loop_block(lines, data)
        self._parking_block(lines, data)
        self._review_block(lines, data)
        self._facts_block(lines, data)
        return lines

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
            return
        for item in open_items:
            spark = (f" (sparked by: {item['source']})"
                     if item.get("source") else "")
            lines.append(f"- {item['question']}{spark}")
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

        md = [f"# Dhriti aftermath — {title}", ""]
        md.append(f"Scope: {scope}")
        md.append(f"Generated: {self.clock.iso()}")
        md.append("")
        md.extend(blocks)
        if identity:
            md.append("## Identity (your own words, from your contract)")
            md.append("")
            md.append(f"> {identity}")
            md.append("")
        md.append("---")
        md.append(f"Ledger head at generation: `{head['row_hash']}`")
        md.append(f"Chain verified: {chain['ok']} "
                  f"({chain['checked']} events)")
        markdown = "\n".join(md)

        html = ["<h1>Dhriti aftermath</h1>"]
        html.append(f"<p>Scope: {_html.escape(scope)}</p>")
        for line in blocks:
            if line.startswith("## "):
                html.append(f"<h2>{_html.escape(line[3:])}</h2>")
            elif line.startswith("- "):
                html.append(f"<div>{_html.escape(line[2:])}</div>")
            elif line.strip():
                html.append(f"<p>{_html.escape(line)}</p>")
        if identity:
            html.append("<blockquote>"
                        + _html.escape(identity) + "</blockquote>")
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
