"""Aftermath reports and cold-review packs (PDF section 8).

Contract vs reality, in facts. Two hard rules:

  1. Facts and interpretations never mix in one sentence. "No code
     execution event was recorded for 35 minutes" is a fact; "the user
     was avoiding work" is an interpretation the system cannot establish
     — interpretations appear only in a clearly separated block, if at all.
  2. The identity line is the user's own sentence from their contract —
     never generated praise, never shame (dossier 2.2: identity
     reinforcement as reminder, not weapon).

The wall never speaks during a session; the aftermath speaks only in a
cold state (next morning / weekly review).
"""

import html as _html
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .profiles import CATEGORY_DOMAINS
from .stage_ratio import (audience_band, drift_split, profile_navigation,
                          render_share, stage_ratio)
from .timeutil import Clock, RealClock, parse_iso, to_iso
import datetime as _dt

_MD_TMPL = """# Dhriti aftermath — {title}

Scope: {scope}
Generated: {generated}

## Contract (what was written, cold)

{contract_block}

## The exchange (main belief vs substitutes)

{exchange_block}

## Reality (what was observed)

{reality_block}

## Consumption facts (categories, observed — whole day)

{consumption_block}

## Stage ratio (audience share, observed)

{ratio_block}

## Declared rest vs drift

{leisure_block}

## Proof

{proof_block}

## Breaks

{break_block}

## Loop log (event summary)

{loop_block}

## Parking lot

{parking_block}

## Cold review answers (submitted, not verified)

{review_block}

## Facts vs interpretation

{facts_block}

## Identity (your own words, from your contract)

> {identity_line}

---

Ledger head at generation: `{ledger_head}`
Chain verified: {chain_ok}
"""

_HTML_TMPL = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dhriti aftermath — {title}</title>
<style>
 body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
      max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1a1a1a;
      background:#fafaf8;line-height:1.55}}
 h1{{font-size:1.35rem}} h2{{font-size:1.05rem;margin-top:1.8rem;
    border-bottom:1px solid #ddd;padding-bottom:.25rem}}
 table{{border-collapse:collapse;width:100%;font-size:.85rem}}
 th,td{{border:1px solid #ddd;padding:.35rem .5rem;text-align:left;
       vertical-align:top}}
 code{{background:#eee;padding:.05rem .3rem;border-radius:3px;
      font-size:.8rem}}
 .muted{{color:#666}} .ok{{color:#1a7f37}} .bad{{color:#b42318}}
 blockquote{{border-left:3px solid #999;margin:1rem 0;padding:.2rem 1rem;
            color:#333;background:#f1f1ee}}
</style></head><body>
<h1>Dhriti aftermath — {title}</h1>
<p class="muted">Scope: {scope} &middot; Generated: {generated}</p>
<h2>Contract (what was written, cold)</h2>{contract_block}
<h2>The exchange (main belief vs substitutes)</h2>{exchange_block}
<h2>Reality (what was observed)</h2>{reality_block}
<h2>Consumption facts (categories, observed — whole day)</h2>{consumption_block}
<h2>Stage ratio (audience share, observed)</h2>{ratio_block}
<h2>Declared rest vs drift</h2>{leisure_block}
<h2>Proof</h2>{proof_block}
<h2>Breaks</h2>{break_block}
<h2>Loop log (event summary)</h2>{loop_block}
<h2>Parking lot</h2>{parking_block}
<h2>Cold review answers (submitted, not verified)</h2>{review_block}
<h2>Facts vs interpretation</h2>{facts_block}
<h2>Identity (your own words, from your contract)</h2>
<blockquote>{identity_line}</blockquote>
<p class="muted">Ledger head: <code>{ledger_head}</code> &middot;
Chain verified: {chain_ok}</p>
</body></html>
"""


class AftermathService:
    def __init__(self, db, config: dict, clock: Optional[Clock] = None,
                 ledger=None):
        self.db = db
        self.config = config
        self.clock = clock or RealClock()
        self.ledger = ledger

    # -- data assembly ---------------------------------------------------------
    def _day_data(self, day: dict) -> dict:
        sessions = self.db.query(
            "SELECT * FROM session WHERE day_id=? ORDER BY started_at",
            (day["id"],))
        evidence = self.db.query(
            "SELECT e.*, s.task FROM evidence e JOIN session s "
            "ON e.session_id=s.id WHERE s.day_id=? ORDER BY e.submitted_at",
            (day["id"],))
        breaks = self.db.query(
            "SELECT * FROM break_glass WHERE day_id=? "
            "ORDER BY pressed_at", (day["id"],))
        passes = self.db.query(
            "SELECT * FROM research_pass WHERE day_id=? "
            "ORDER BY started_at", (day["id"],))
        contract = None
        if day.get("contract_id"):
            row = self.db.query_one(
                "SELECT * FROM contract WHERE id=?", (day["contract_id"],))
            if row:
                contract = json.loads(row["payload_json"])
        events = self.db.query(
            "SELECT event_type, source_adapter, action_taken, "
            "COUNT(*) AS n FROM event WHERE session_id IN "
            "(SELECT id FROM session WHERE day_id=?) "
            "GROUP BY event_type, source_adapter, action_taken "
            "ORDER BY n DESC", (day["id"],))
        parked = self.db.query(
            "SELECT * FROM parking_lot WHERE day_id=? "
            "ORDER BY created_at", (day["id"],))
        review = self.db.query(
            "SELECT * FROM cold_review WHERE scope=? "
            "ORDER BY created_at", (f"day:{day['date']}",))
        # D-046/D-047/D-048: the whole day's navigation — evening
        # included — plus the ratio and the declared-rest split.
        local_date = _dt.date.fromisoformat(day["date"])
        nav_profile = profile_navigation(self.db, self.config,
                                         local_date, day=day)
        ratio = stage_ratio(nav_profile, audience_band(self.config))
        leisure_rows = self.db.query(
            "SELECT * FROM leisure_declaration WHERE day_date=? "
            "ORDER BY created_at", (day["date"],))
        drift = drift_split(nav_profile["consumption_events"],
                            leisure_rows)
        return {"day": day, "sessions": sessions, "evidence": evidence,
                "breaks": breaks, "passes": passes, "contract": contract,
                "events": events, "parked": parked, "review": review,
                "consumption": {"counts": nav_profile["counts"],
                                "top_hosts": nav_profile["top_hosts"]},
                "nav_profile": nav_profile, "ratio": ratio,
                "leisure": leisure_rows, "drift": drift}

    def _week_data(self, week_start_iso: str) -> dict:
        start = parse_iso(week_start_iso + "T00:00:00Z")
        end = to_iso(start + timedelta(days=7))
        days = self.db.query(
            "SELECT * FROM day WHERE date>=? AND date<? "
            "ORDER BY date", (start.date().isoformat(),
                              end[:10]))
        sessions = self.db.query(
            "SELECT * FROM session WHERE started_at>=? AND started_at<? "
            "ORDER BY started_at", (week_start_iso, end))
        # Bug 1 (Phase 0): the old grouped COUNT query lost class/kind and
        # crashed the renderers (KeyError 'class'). Group in Python so the
        # rows keep every field the renderers read.
        evidence_rows = self.db.query(
            "SELECT e.class AS class, e.kind AS kind, e.verdict AS verdict "
            "FROM evidence e JOIN session s ON e.session_id=s.id "
            "WHERE s.started_at>=? AND s.started_at<?", (week_start_iso, end))
        evidence = {}
        for row in evidence_rows:
            key = (row["verdict"], row["class"], row["kind"])
            evidence[key] = evidence.get(key, 0) + 1
        evidence = [{"verdict": v, "class": c, "kind": k, "n": n}
                    for (v, c, k), n in sorted(evidence.items())]
        breaks = self.db.query(
            "SELECT * FROM break_glass WHERE confirmed_at>=? AND "
            "confirmed_at<?", (week_start_iso, end))
        review = self.db.query(
            "SELECT * FROM cold_review WHERE scope=? ORDER BY created_at",
            (f"week:{week_start_iso}",))
        parked = self.db.query(
            "SELECT disposition, COUNT(*) AS n FROM parking_lot "
            "GROUP BY disposition")
        return {"days": days, "sessions": sessions, "evidence": evidence,
                "breaks": breaks, "review": review, "parked": parked}

    def _consumption_facts(self, day_id: str) -> dict:
        """Categorize observed browser navigation for the day's sessions.
        Deterministic domain matching (D-014): no model, no judgement —
        counts only, for the cold review. The ai_chat count next to a
        zero-evidence session is the Specimen-001 shape: conversation
        without artifacts."""
        rows = self.db.query(
            "SELECT observed_payload FROM event WHERE event_type="
            "'browser_navigation' AND session_id IN "
            "(SELECT id FROM session WHERE day_id=?)", (day_id,))
        counts = {}
        hosts = {}
        for row in rows:
            try:
                payload = json.loads(row["observed_payload"] or "{}")
            except Exception:
                continue
            host = urlparse(payload.get("url") or "").netloc.lower()
            host = host.split(":")[0]
            if not host:
                continue
            category = "other"
            for cat, domains in CATEGORY_DOMAINS.items():
                for domain in domains:
                    if host == domain or host.endswith("." + domain):
                        category = cat
                        break
                if category != "other":
                    break
            counts[category] = counts.get(category, 0) + 1
            hosts[host] = hosts.get(host, 0) + 1
        return {"counts": counts, "top_hosts": sorted(
            hosts.items(), key=lambda kv: -kv[1])[:10]}

    # -- renderers ----------------------------------------------------------------
    def day_report(self, day: dict) -> dict:
        data = self._day_data(day)
        return self._render(
            title=f"{day['date']}", scope=f"day {day['date']}",
            data=data, kind="day")

    def week_report(self, week_start_iso: str) -> dict:
        data = self._week_data(week_start_iso)
        return self._render(
            title=f"week of {week_start_iso}",
            scope=f"week {week_start_iso} .. +7d",
            data=data, kind="week")

    def _render(self, title: str, scope: str, data: dict, kind: str) -> dict:
        contract = data.get("contract") or {}
        contract_block = self._md_contract(contract)
        exchange_block = self._md_exchange(contract, data)
        reality_block = self._md_reality(data)
        consumption_block = self._md_consumption(data)
        ratio_block = self._md_ratio(data)
        leisure_block = self._md_leisure(data)
        proof_block = self._md_proof(data)
        break_block = self._md_breaks(data)
        loop_block = self._md_loop(data)
        parking_block = self._md_parking(data)
        review_block = self._md_review(data)
        facts_block = self._md_facts(data)
        identity_line = contract.get(
            "identity_statement") or "(no identity statement written)"
        chain_ok = "not checked"
        head = "n/a"
        if self.ledger is not None:
            head = self.ledger.head()["row_hash"]
            chain_ok = "yes" if self.ledger.verify_chain()["ok"] else "NO"

        md = _MD_TMPL.format(
            title=title, scope=scope, generated=self.clock.iso(),
            contract_block=contract_block, exchange_block=exchange_block,
            reality_block=reality_block, consumption_block=consumption_block,
            ratio_block=ratio_block, leisure_block=leisure_block,
            proof_block=proof_block, break_block=break_block,
            loop_block=loop_block, parking_block=parking_block,
            review_block=review_block, facts_block=facts_block,
            identity_line=identity_line, ledger_head=head, chain_ok=chain_ok)
        html = _HTML_TMPL.format(
            title=_html.escape(title), scope=_html.escape(scope),
            generated=self.clock.iso(),
            contract_block=self._html_contract(contract),
            exchange_block=_html.escape(exchange_block).replace("\n", "<br>"),
            reality_block=self._html_reality(data),
            consumption_block=_html.escape(consumption_block).replace("\n", "<br>"),
            ratio_block=_html.escape(ratio_block).replace("\n", "<br>"),
            leisure_block=_html.escape(leisure_block).replace("\n", "<br>"),
            proof_block=self._html_proof(data),
            break_block=self._html_breaks(data),
            loop_block=self._html_loop(data),
            parking_block=_html.escape(parking_block).replace("\n", "<br>"),
            review_block=_html.escape(review_block).replace("\n", "<br>"),
            facts_block=self._html_facts(data),
            identity_line=_html.escape(identity_line),
            ledger_head=_html.escape(head), chain_ok=chain_ok)
        return {"markdown": md, "html": html}

    # -- markdown fragments -----------------------------------------------------
    @staticmethod
    def _md_contract(contract: dict) -> str:
        if not contract:
            return "_(no sealed contract found for this scope)_"
        lines = [f"- Mandatory task: {contract.get('mandatory_task','')}",
                 f"- Smallest next action: "
                 f"{contract.get('smallest_next_action','')}"]
        for item in contract.get("evidence", []) or []:
            lines.append(f"- Evidence declared: {item}")
        lines.append(f"- Core belief: {contract.get('core_belief','')}")
        if contract.get("expected_obstacle"):
            lines.append(f"- Expected obstacle: "
                         f"{contract.get('expected_obstacle','')}")
            lines.append(f"- IF–THEN response: "
                         f"{contract.get('if_then_response','')}")
            lines.append(f"- Return condition: "
                         f"{contract.get('return_condition','')}")
        return "\n".join(lines)

    @staticmethod
    def _md_exchange(contract: dict, data: dict) -> str:
        """D-029/D-030: the mirror. Main belief state and substitutes,
        side by side, in the user's own cold-state words. No verdict."""
        if not contract or not contract.get("main_belief"):
            return "_(no main belief declared in this contract)_"
        lines = [
            f"- Main belief: {contract.get('main_belief','')}",
            f"- Metric that would prove it: "
            f"{contract.get('main_belief_metric','')}",
            f"- Current state (your words, cold): "
            f"{contract.get('main_belief_current_state','')}",
            f"- Declared substitutes: "
            f"{contract.get('substitute_activities','')}",
            f"- Substitute budget: {contract.get('substitute_budget','')}",
        ]
        sessions = data.get("sessions") or []
        if sessions:
            n_success = sum(1 for s in sessions
                            if s.get("state") == "SUCCESS")
            lines.append(
                f"- Observed this scope: {len(sessions)} session(s), "
                f"{n_success} with accepted evidence.")
        lines.append(
            "(The system does not judge the exchange. It shows the two "
            "sides; the cold review reads them.)")
        return "\n".join(lines)

    @staticmethod
    def _md_consumption(data: dict) -> str:
        """D-048: consumption facts cover the WHOLE local day — the
        evening included when observation is on — split by where the
        navigation happened. Deterministic domain matching (D-014);
        counts only, no content read."""
        profile = data.get("nav_profile")
        consumption = data.get("consumption")
        if not profile or not consumption or not consumption.get("counts"):
            if profile and profile.get("total"):
                return ("_(no consumption-category navigation observed "
                        "all day — " + str(profile["total"]) +
                        " work-side navigation(s))_")
            return ("_(no navigation observed — observation off or no "
                    "browser events)_")
        counts = consumption["counts"]
        lines = [f"- {category}: {n}"
                 for category, n in sorted(counts.items(),
                                           key=lambda kv: -kv[1])]
        lines.append(
            f"- where: {profile['in_window']} navigation(s) inside the "
            f"window, {profile['after_window']} after window_end "
            f"(evening), {profile['before_window']} before window_start")
        lines.append("_(deterministic domain matching, D-014; whole-day "
                     "coverage, evening included; counts only, no "
                     "content read)_")
        return "\n".join(lines)

    @staticmethod
    def _md_ratio(data: dict) -> str:
        """D-046: the subject's own metric. Facts next to his own band;
        the reader computes the distance — no verdict words (D-052)."""
        ratio = data.get("ratio")
        if not ratio:
            return ("_(day-scope measure — see the daily reports and the "
                    "weekly digest's stage-ratio line)_")
        if not ratio["observed"]:
            return ("_(no navigation observed — MISSING is not evidence "
                    "of being on stage)_")
        lines = [
            f"- Audience share of observed navigation: "
            f"{render_share(ratio['audience_share'])} "
            f"({ratio['consumption']} of {ratio['total']} navigations)",
            f"- Your endorsed band: "
            f"{round(ratio['band_low'] * 100)}-"
            f"{round(ratio['band_high'] * 100)}% audience "
            "(Specimen 001)",
            "- counts, not minutes — duration-grade ratios need "
            "ActivityWatch",
        ]
        return "\n".join(lines)

    @staticmethod
    def _md_leisure(data: dict) -> str:
        """D-047: declared rest next to drift, side by side, no verdict.
        The system never guesses which evening hour was rest — the user
        declares, the facts check."""
        rows = data.get("leisure") or []
        drift = data.get("drift") or {}
        if "leisure" not in data:
            return ("_(day-scope measure — the weekly digest carries the "
                    "week's declared-rest and drift totals)_")
        lines = []
        for r in rows:
            lines.append(f"- Declared: {r['created_at'][11:16]}UTC "
                         f"{r['activity']} ({r['planned_minutes']} min, "
                         f"ends {r['ends_at'][11:16]}UTC)")
        if not rows:
            lines.append("_(no leisure declared — undeclared consumption "
                         "reads as drift)_")
        lines.append(
            f"- Declared rest: {drift.get('declared_rest', 0)} "
            "consumption navigation(s) inside declared windows")
        lines.append(
            f"- Drift: {drift.get('drift', 0)} consumption navigation(s) "
            "outside declared windows")
        return "\n".join(lines)

    @staticmethod
    def _md_parking(data: dict) -> str:
        rows = data.get("parked")
        if rows is None:
            rows = [{"disposition": d, "n": n}
                    for d, n in (data.get("parked") or {}).items()] \
                if isinstance(data.get("parked"), dict) else []
        if not rows:
            return "_(nothing parked)_"
        lines = []
        for p in rows:
            if "question" in p:
                lines.append(f"- [{p['disposition']}] {p['question']}")
            else:
                lines.append(f"- {p['disposition']}: {p.get('n', '?')}")
        return "\n".join(lines)

    @staticmethod
    def _md_review(data: dict) -> str:
        rows = data.get("review") or []
        if not rows:
            return "_(no cold review recorded for this scope)_"
        lines = [f"- {r['question_key']}: {r['answer']}" for r in rows]
        return "\n".join(lines)

    @staticmethod
    def _md_reality(data: dict) -> str:
        if "day" in data:
            day = data["day"]
            lines = [f"- Day state: `{day['state']}`",
                     f"- Window: {day['window_start_at']} .. "
                     f"{day['window_end_at']} (day_close "
                     f"{day['day_close_at']})",
                     f"- Released at: {day.get('released_at') or '-'}",
                     f"- Targets met: {'yes' if day['targets_met'] else 'no'}"]
            for s in data["sessions"]:
                lines.append(f"- Session `{s['id'][:8]}` [{s['state']}]: "
                             f"{s['task']} ({s['started_at']} .. "
                             f"{s.get('ended_at') or 'open'})")
            for p in data["passes"]:
                lines.append(f"- Research pass `{p['id'][:8]}` [{p['state']}]:"
                             f" {p['dependency']} (expires {p['expires_at']})")
            return "\n".join(lines) if lines else "_(nothing observed)_"
        lines = []
        for d in data.get("days", []):
            lines.append(f"- {d['date']}: `{d['state']}`, "
                         f"targets {'met' if d['targets_met'] else 'unmet'}")
        for s in data.get("sessions", []):
            lines.append(f"- Session `{s['id'][:8]}` [{s['state']}]: "
                         f"{s['task']}")
        return "\n".join(lines) or "_(nothing observed)_"

    @staticmethod
    def _md_proof(data: dict) -> str:
        rows = data.get("evidence") or []
        if not rows:
            return "_(no evidence submitted)_"
        lines = []
        for e in rows:
            count = f" ×{e['n']}" if "n" in e else ""
            lines.append(f"- [{e['verdict']}] {e['class']}/{e['kind']}"
                         f"{count}: "
                         f"{e.get('verdict_reason') or ''}")
        return "\n".join(lines)

    @staticmethod
    def _md_breaks(data: dict) -> str:
        rows = data.get("breaks") or []
        if not rows:
            return "_(no break-glass events)_"
        lines = []
        for b in rows:
            penalty = b.get("penalty_declared") or ""
            is_emergency = '"type": "emergency"' in penalty or \
                           '"type":"emergency"' in penalty
            kind = "EMERGENCY" if is_emergency else "break-glass"
            lines.append(
                f"- {b['pressed_at']} [{kind}]: "
                f"{'confirmed' if b['confirmed_at'] else 'unconfirmed'}"
                f"{'' if b['honored_delay'] else ' (delay NOT honored)'}"
                f" — reason: {b.get('reason') or '-'}")
        return "\n".join(lines)

    @staticmethod
    def _md_loop(data: dict) -> str:
        rows = data.get("events") or []
        if not rows:
            return "_(no session-scoped events)_"
        lines = [f"- {r['event_type']} x{r['n']} "
                 f"({r['source_adapter']}, action={r['action_taken'] or '-'})"
                 for r in rows[:25]]
        return "\n".join(lines)

    @staticmethod
    def _md_facts(data: dict) -> str:
        sessions = data.get("sessions") or []
        facts, interpretations = [], []
        for s in sessions:
            if s["state"] == "SUCCESS":
                facts.append(f"Session `{s['id'][:8]}` ended SUCCESS with "
                             "accepted evidence.")
            elif s["state"] == "INCOMPLETE":
                facts.append(f"Session `{s['id'][:8]}` ended INCOMPLETE: no "
                             "accepted evidence was recorded.")
            elif s["state"] == "BREAK_GLASS":
                facts.append(f"Session `{s['id'][:8]}` ended via BREAK_GLASS.")
            elif s["state"] == "INTERRUPTED":
                facts.append(f"Session `{s['id'][:8]}` was INTERRUPTED; the "
                             "daemon was not running when it ended.")
        if not sessions:
            facts.append("No sessions were recorded for this scope.")
        interpretations.append(
            "(The system does not infer motive. What the gaps meant is a "
            "question for the cold review, not a claim for this report.)")
        return "\n".join(
            ["**Facts:**"] + [f"- {f}" for f in facts] +
            ["", "**Interpretation boundary:**"] + interpretations)

    # -- html fragments (tables; same data, honest separation) ------------------
    @staticmethod
    def _html_contract(contract):
        if not contract:
            return "<p class='muted'>(no sealed contract found)</p>"
        rows = [("Mandatory task", contract.get("mandatory_task", "")),
                ("Smallest next action",
                 contract.get("smallest_next_action", "")),
                ("Evidence declared", "; ".join(
                    json.dumps(e) for e in contract.get("evidence", []) or [])),
                ("Core belief", contract.get("core_belief", ""))]
        return ("<table>" + "".join(
            f"<tr><th>{_html.escape(str(k))}</th>"
            f"<td>{_html.escape(str(v))}</td></tr>" for k, v in rows) +
            "</table>")

    @staticmethod
    def _rows_table(headers, rows):
        head = "".join(f"<th>{_html.escape(h)}</th>" for h in headers)
        body = "".join(
            "<tr>" + "".join(
                f"<td>{_html.escape(str(c))}</td>" for c in row) + "</tr>"
            for row in rows)
        return f"<table><tr>{head}</tr>{body}</table>"

    def _html_reality(self, data):
        if "day" in data:
            day = data["day"]
            rows = [("day state", day["state"]),
                    ("window", f"{day['window_start_at']} .. "
                               f"{day['window_end_at']}"),
                    ("released at", day.get("released_at") or "-"),
                    ("targets met", "yes" if day["targets_met"] else "no")]
            srows = [(s["id"][:8], s["state"], s["task"],
                      f"{s['started_at']} .. {s.get('ended_at') or 'open'}")
                     for s in data["sessions"]]
            out = self._rows_table(("field", "value"), rows)
            if srows:
                out += self._rows_table(
                    ("session", "state", "task", "span"), srows)
            return out
        drows = [(d["date"], d["state"],
                  "met" if d["targets_met"] else "unmet")
                 for d in data.get("days", [])]
        return self._rows_table(("date", "state", "targets"), drows) \
            if drows else "<p class='muted'>(nothing observed)</p>"

    def _html_proof(self, data):
        rows = [(e["verdict"], f"{e['class']}/{e['kind']}"
                 + (f" ×{e['n']}" if "n" in e else ""),
                 e.get("verdict_reason") or "")
                for e in data.get("evidence") or []]
        return self._rows_table(("verdict", "class/kind", "reason"), rows) \
            if rows else "<p class='muted'>(no evidence submitted)</p>"

    def _html_breaks(self, data):
        rows = [(b["pressed_at"],
                 "confirmed" if b["confirmed_at"] else "unconfirmed",
                 "yes" if b["honored_delay"] else "NO",
                 b.get("reason") or "-")
                for b in data.get("breaks") or []]
        return self._rows_table(("pressed", "status", "delay honored",
                                 "reason"), rows) \
            if rows else "<p class='muted'>(no break-glass events)</p>"

    def _html_loop(self, data):
        rows = [(r["event_type"], r["n"], r["source_adapter"],
                 r["action_taken"] or "-")
                for r in (data.get("events") or [])[:25]]
        return self._rows_table(("event", "count", "source", "action"),
                                rows) if rows \
            else "<p class='muted'>(no session-scoped events)</p>"

    def _html_facts(self, data):
        md = self._md_facts(data)
        parts = md.split("**Interpretation boundary:**")
        facts_html = _html.escape(
            parts[0].replace("**Facts:**", "").strip()).replace(
            "\n- ", "<br>- ").replace("\n", "<br>")
        interp = _html.escape(parts[1].strip()) if len(parts) > 1 else ""
        return (f"<p><strong>Facts:</strong><br>- {facts_html}</p>"
                f"<p class='muted'><strong>Interpretation boundary:</strong>"
                f"<br>{interp}</p>")

    # -- writing files ------------------------------------------------------------
    def write(self, report: dict, out_dir: Path, stem: str) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"{stem}.md"
        html_path = out_dir / f"{stem}.html"
        md_path.write_text(report["markdown"], encoding="utf-8")
        html_path.write_text(report["html"], encoding="utf-8")
        return {"markdown": str(md_path), "html": str(html_path)}
