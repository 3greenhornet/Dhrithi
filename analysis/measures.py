#!/usr/bin/env python3
"""N-of-1 experiment measures (dossier 10.3) — pure Python.

Primary: meaningful task progress (accepted milestones).
Secondary: time to first action, branch counts, return rate, proof
rate, break-glass frequency, offline time, and — since v0.3 — the
stage ratio (D-046): the subject's own metric, audience share of
observed navigation. Never screen-time reduction alone.

Usage:
  python analysis/measures.py --db ~/.dhriti/dhriti.sqlite3
"""

import argparse
import json
import sqlite3
from collections import defaultdict
from urllib.parse import urlparse

OFFLINE_EVENTS = {"afk_heartbeat"}

# D-046: the consumption side. The canonical implementation lives in
# dhriti/stage_ratio.py; this standalone copy keeps the analysis layer
# dependency-free (analysis/ must run without the package installed).
CONSUMPTION_CATEGORIES = (
    "video", "social", "ai_chat", "games", "news", "shopping",
    "entertainment",
)
CATEGORY_DOMAINS = {
    "video": ["youtube.com", "youtu.be", "netflix.com", "primevideo.com",
              "hotstar.com", "twitch.tv", "vimeo.com", "primevideo.co.in"],
    "social": ["instagram.com", "x.com", "twitter.com", "facebook.com",
               "reddit.com", "threads.net", "linkedin.com", "snapchat.com",
               "whatsapp.com", "web.whatsapp.com", "discord.com"],
    "ai_chat": ["chat.openai.com", "chatgpt.com", "claude.ai",
                "gemini.google.com", "copilot.microsoft.com",
                "chat.deepseek.com", "poe.com", "character.ai", "grok.com",
                "x.com/i/grok"],
    "games": ["steampowered.com", "store.steampowered.com", "epicgames.com",
              "roblox.com", "chess.com", "lichess.org", "miniclip.com",
              "poki.com", "crazygames.com"],
    "news": ["news.ycombinator.com", "bbc.com", "cnn.com", "theverge.com",
             "timesofindia.indiatimes.com", "indianexpress.com",
             "thehindu.com", "reuters.com", "apnews.com", "arstechnica.com"],
    "shopping": ["amazon.in", "amazon.com", "flipkart.com", "myntra.com",
                 "ajio.com", "ebay.com", "aliexpress.com"],
    "entertainment": ["9gag.com", "knowyourmeme.com", "quora.com",
                      "pinterest.com", "tiktok.com", "imasdk.googleapis.com"],
}


def consumption_category(url):
    """Deterministic domain match (D-014): counts only, never content."""
    host = (urlparse(url or "").netloc or "").lower().split(":")[0]
    if not host:
        return None
    for category in CONSUMPTION_CATEGORIES:
        for domain in CATEGORY_DOMAINS[category]:
            if host == domain or host.endswith("." + domain):
                return category
    return None


def stage_ratio_by_day(events):
    """D-046: per local day, audience share of observed navigation.
    Counts, not minutes — duration-grade ratios need ActivityWatch."""
    per_day = defaultdict(lambda: {"total": 0, "consumption": 0,
                                   "categories": {}})
    for event in events:
        if event["event_type"] != "browser_navigation":
            continue
        try:
            payload = json.loads(event.get("observed_payload") or "{}")
        except Exception:
            continue
        day = event["occurred_at_utc"][:10]
        per_day[day]["total"] += 1
        category = consumption_category(payload.get("url"))
        if category:
            per_day[day]["consumption"] += 1
            per_day[day]["categories"][category] = \
                per_day[day]["categories"].get(category, 0) + 1
    rows = []
    for day in sorted(per_day):
        data = per_day[day]
        share = (data["consumption"] / data["total"]
                 if data["total"] else None)
        rows.append({"date": day, "navigations": data["total"],
                     "consumption": data["consumption"],
                     "audience_share": (round(share, 3)
                                        if share is not None else None)})
    return rows


def fetch(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    sessions = [dict(r) for r in conn.execute(
        "SELECT * FROM session ORDER BY started_at")]
    events = [dict(r) for r in conn.execute(
        "SELECT * FROM event ORDER BY occurred_at_utc, seq")]
    evidence = [dict(r) for r in conn.execute("SELECT * FROM evidence")]
    breaks = [dict(r) for r in conn.execute(
        "SELECT * FROM break_glass WHERE confirmed_at IS NOT NULL")]
    conn.close()
    return sessions, events, evidence, breaks


def session_measures(sessions, events, evidence, breaks):
    events_by_session = defaultdict(list)
    for event in events:
        if event["session_id"]:
            events_by_session[event["session_id"]].append(event)
    evidence_by_session = defaultdict(list)
    for ev in evidence:
        evidence_by_session[ev["session_id"]].append(ev)

    rows = []
    for session in sessions:
        sid = session["id"]
        sess_events = events_by_session.get(sid, [])
        navigations = [e for e in sess_events
                       if e["event_type"] == "browser_navigation"]
        ev_rows = evidence_by_session.get(sid, [])
        accepted = [e for e in ev_rows if e["verdict"] == "ACCEPTED"]
        # time to first accepted evidence, in minutes
        first_action = None
        if accepted:
            started = session["started_at"]
            first = min(e["submitted_at"] for e in accepted)
            from datetime import datetime
            fmt = "%Y-%m-%dT%H:%M:%SZ"
            delta = (datetime.strptime(first, fmt)
                     - datetime.strptime(started, fmt)).total_seconds()
            first_action = round(delta / 60, 1)
        rows.append({
            "session": sid[:8],
            "state": session["state"],
            "condition": session["experiment_condition"],
            "events": len(sess_events),
            "navigations": len(navigations),
            "evidence_accepted": len(accepted),
            "time_to_first_accepted_min": first_action,
        })
    return rows


def overall(sessions, evidence, breaks, events):
    finished = [s for s in sessions if s["state"] in
                ("SUCCESS", "INCOMPLETE", "BREAK_GLASS", "INTERRUPTED")]
    successes = [s for s in sessions if s["state"] == "SUCCESS"]
    accepted = [e for e in evidence if e["verdict"] == "ACCEPTED"]
    # D-046: the subject's own metric — his self-assessment was 90%
    # audience; the band he endorsed is 20-30% audience.
    ratio_rows = stage_ratio_by_day(events)
    observed_days = [r for r in ratio_rows if r["audience_share"] is not None]
    mean_share = (round(sum(r["audience_share"] for r in observed_days)
                        / len(observed_days), 3)
                  if observed_days else None)
    return {
        "sessions_total": len(sessions),
        "sessions_finished": len(finished),
        "proof_rate": round(len(successes) / len(finished), 3)
        if finished else None,
        "evidence_accepted": len(accepted),
        "break_glass_total": len(breaks),
        "offline_events": sum(
            1 for e in events if e["event_type"] in OFFLINE_EVENTS),
        "stage_ratio_days": len(observed_days),
        "stage_ratio_mean_audience_share": mean_share,
        "stage_ratio_endorsed_band": [0.2, 0.3],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    sessions, events, evidence, breaks = fetch(args.db)
    rows = session_measures(sessions, events, evidence, breaks)
    summary = overall(sessions, evidence, breaks, events)
    if args.json:
        print(json.dumps({"summary": summary,
                          "stage_ratio_by_day": stage_ratio_by_day(events),
                          "sessions": rows},
                         indent=2, default=str))
    else:
        print(json.dumps(summary, indent=2))
        print(f"\n{'date':<12}{'navs':>6}{'consumption':>13}"
              f"{'audience share':>16}")
        for row in stage_ratio_by_day(events):
            print(f"{row['date']:<12}{row['navigations']:>6}"
                  f"{row['consumption']:>13}"
                  f"{str(row['audience_share'] if row['audience_share'] is None else round(row['audience_share']*100)):>16}")
        print(f"\n{'session':<10}{'state':<14}{'cond':<6}{'ev':>5}"
              f"{'nav':>5}{'proof':>6}{'first(min)':>11}")
        for row in rows:
            print(f"{row['session']:<10}{row['state']:<14}"
                  f"{str(row['condition'] or '-'):<6}{row['events']:>5}"
                  f"{row['navigations']:>5}"
                  f"{row['evidence_accepted']:>6}"
                  f"{str(row['time_to_first_accepted_min'] or '-'):>11}")


if __name__ == "__main__":
    import sys as _sys
    try:
        main()
    except BrokenPipeError:
        _sys.exit(0)
