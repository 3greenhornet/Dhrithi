"""The stage ratio (D-046) — the subject's own metric, in his words.

Specimen 001, self-application phase: "i too am a audience for 90% of
time not even 50." The band he endorsed is 70–80% stage / 20–30%
audience. That is his metric and the project's natural primary
measure; before v0.3 the aftermath counted categories but never formed
the ratio.

What the measure IS, honestly:

  * audience share of OBSERVED NAVIGATION — of the pages the browser
    opened, the share that went to consumption categories (video,
    social, ai_chat, games, news, shopping, entertainment);
  * deterministic domain matching (D-014): counts only, never content,
    never a model, never a judgement;
  * counts, NOT minutes. A duration-grade ratio needs ActivityWatch;
    until then the caveat is printed next to the number, not buried.

What the measure is NOT: a verdict. The number is placed next to the
user's own endorsed band; the distance between them is read by the
cold review and the digest human, not scored by the software
(shame-safety law, D-052).
"""

import datetime as _dt
import json
from typing import Optional
from urllib.parse import urlparse

from .profiles import CATEGORY_DOMAINS
from .timeutil import local_tz, parse_iso, to_iso

# The consumption side of the world. Everything else (docs, search,
# allowed tools, unlisted domains) is stage-side or neutral work
# surface — the ratio's denominator is ALL observed navigation, the
# numerator is the consumption share of it.
CONSUMPTION_CATEGORIES = (
    "video", "social", "ai_chat", "games", "news", "shopping",
    "entertainment",
)

DEFAULT_AUDIENCE_BAND = (0.2, 0.3)   # the Specimen-001 endorsed band


def consumption_category(url: str) -> Optional[str]:
    """Deterministic: which consumption category (if any) a URL is in."""
    host = (urlparse(url or "").netloc or "").lower().split(":")[0]
    if not host:
        return None
    for category in CONSUMPTION_CATEGORIES:
        for domain in CATEGORY_DOMAINS.get(category, []):
            if host == domain or host.endswith("." + domain):
                return category
    return None


def audience_band(config: dict) -> tuple:
    band = (config or {}).get("stage_ratio", {}).get("audience_band",
                                                     DEFAULT_AUDIENCE_BAND)
    try:
        low, high = float(band[0]), float(band[1])
        if 0.0 <= low <= high <= 1.0:
            return (low, high)
    except Exception:
        pass
    return DEFAULT_AUDIENCE_BAND


def _local_day_bounds(local_date: _dt.date, config: dict):
    """UTC instants spanning the local calendar day [00:00, next 00:00)."""
    tz = local_tz((config or {}).get("timezone", "UTC"))
    start = _dt.datetime.combine(local_date, _dt.time.min, tzinfo=tz)
    end = _dt.datetime.combine(local_date + _dt.timedelta(days=1),
                               _dt.time.min, tzinfo=tz)
    return start, end


def navigation_events(db, start_utc: _dt.datetime,
                      end_utc: _dt.datetime) -> list:
    """browser_navigation ledger rows in [start, end), oldest first.
    Whole-day by design (D-048): the evening is included, not just the
    session hours — events without a session count too."""
    return db.query(
        "SELECT occurred_at_utc, session_id, observed_payload FROM event "
        "WHERE event_type='browser_navigation' AND occurred_at_utc>=? "
        "AND occurred_at_utc<? ORDER BY occurred_at_utc",
        (to_iso(start_utc), to_iso(end_utc)))


def profile_navigation(db, config: dict, local_date: _dt.date,
                       day: Optional[dict] = None) -> dict:
    """One day's navigation facts, split by where they happened.

    Returns counts (total, per consumption category, top hosts) and the
    timestamped consumption events (for the declared-rest-vs-drift
    split, D-047). If the day row is given, navigations are also split
    into before_window / window / after_window (the evening, D-048).
    """
    start, end = _local_day_bounds(local_date, config)
    rows = navigation_events(db, start, end)
    window_start = (day or {}).get("window_start_at")
    window_end = (day or {}).get("window_end_at")
    profile = {
        "total": 0,
        "consumption": 0,
        "counts": {},                       # category -> n
        "top_hosts": [],
        "consumption_events": [],           # [(occurred_at_utc, category)]
        "before_window": 0, "in_window": 0, "after_window": 0,
        "consumption_in_window": 0,
        "consumption_after_window": 0,      # the evening audience
    }
    hosts = {}
    for row in rows:
        try:
            payload = json.loads(row["observed_payload"] or "{}")
        except Exception:
            continue
        url = payload.get("url") or ""
        host = (urlparse(url).netloc or "").lower().split(":")[0]
        if not host:
            continue
        profile["total"] += 1
        hosts[host] = hosts.get(host, 0) + 1
        when = row["occurred_at_utc"]
        if window_start and window_end:
            if when < window_start:
                profile["before_window"] += 1
            elif when <= window_end:
                profile["in_window"] += 1
            else:
                profile["after_window"] += 1
        category = consumption_category(url)
        if category:
            profile["consumption"] += 1
            profile["counts"][category] = (
                profile["counts"].get(category, 0) + 1)
            profile["consumption_events"].append((when, category))
            if window_start and window_end:
                if when <= window_end:
                    profile["consumption_in_window"] += 1
                else:
                    profile["consumption_after_window"] += 1
    profile["top_hosts"] = sorted(hosts.items(),
                                  key=lambda kv: -kv[1])[:10]
    return profile


def stage_ratio(profile: dict, band: tuple = DEFAULT_AUDIENCE_BAND) -> dict:
    """Audience share of observed navigation, against the band.

    None (not 0.0) when nothing was observed: MISSING is not evidence
    of being on stage (the telemetry rule, models.TelemetryQuality).
    """
    total = profile.get("total") or 0
    consumption = profile.get("consumption") or 0
    share = (consumption / total) if total else None
    return {
        "total": total,
        "consumption": consumption,
        "audience_share": share,
        "band_low": band[0],
        "band_high": band[1],
        "observed": total > 0,
        # factual, never a verdict: the reader computes the distance
        "within_band": (share is not None
                        and band[0] <= share <= band[1]),
    }


def render_share(share) -> str:
    if share is None:
        return "no navigation observed"
    return f"{round(share * 100)}%"


# -- declared rest vs drift (D-047) ---------------------------------------

def drift_split(consumption_events: list, declarations: list) -> dict:
    """Consumption navigations inside declared leisure windows count as
    declared rest; the rest is drift. Timestamps are UTC ISO strings;
    declarations are leisure_declaration rows (created_at, ends_at)."""
    windows = []
    for row in declarations or []:
        try:
            windows.append((parse_iso(row["created_at"]),
                            parse_iso(row["ends_at"])))
        except Exception:
            continue                     # a malformed row is skipped, not guessed
    declared = 0
    drift = []
    for when, category in consumption_events or []:
        try:
            moment = parse_iso(when)
        except Exception:
            drift.append((when, category))
            continue
        if any(start <= moment <= end for start, end in windows):
            declared += 1
        else:
            drift.append((when, category))
    return {"declared_rest": declared, "drift": len(drift),
            "drift_events": drift[:50]}


# -- behavioral artifact test (D-099) ---------------------------------------

def compute_artifact_stage_ratio(db, start_utc: Optional[_dt.datetime] = None,
                                 end_utc: Optional[_dt.datetime] = None,
                                 window_minutes: int = 30) -> dict:
    """Behavioral stage classification: an opened content item is Stage if and only if
    it is followed by an accepted evidence event within window_minutes. Otherwise it is Audience."""
    opens_sql = "SELECT occurred_at_utc, observed_payload FROM event WHERE event_type = 'content_item_opened'"
    params = []
    if start_utc:
        opens_sql += " AND occurred_at_utc >= ?"
        params.append(to_iso(start_utc))
    if end_utc:
        opens_sql += " AND occurred_at_utc < ?"
        params.append(to_iso(end_utc))
    opens_sql += " ORDER BY occurred_at_utc ASC"

    open_rows = db.query(opens_sql, params)
    total_opens = len(open_rows)
    if total_opens == 0:
        return {
            "total_content_opened": 0,
            "stage_with_evidence": 0,
            "audience_unaccompanied": 0,
            "artifact_stage_ratio": None,
            "window_minutes": window_minutes
        }

    evidence_rows = db.query(
        "SELECT occurred_at_utc, observed_payload FROM event WHERE event_type = 'evidence_submitted' ORDER BY occurred_at_utc ASC"
    )
    evidence_times = []
    for ev_row in evidence_rows:
        try:
            evidence_times.append(parse_iso(ev_row["occurred_at_utc"]))
        except Exception:
            pass

    stage_count = 0
    audience_count = 0

    for op in open_rows:
        try:
            op_time = parse_iso(op["occurred_at_utc"])
        except Exception:
            audience_count += 1
            continue

        deadline = op_time + _dt.timedelta(minutes=window_minutes)
        has_evidence = any(op_time <= ev_t <= deadline for ev_t in evidence_times)
        if has_evidence:
            stage_count += 1
        else:
            audience_count += 1

    ratio = stage_count / total_opens if total_opens > 0 else 0.0
    return {
        "total_content_opened": total_opens,
        "stage_with_evidence": stage_count,
        "audience_unaccompanied": audience_count,
        "artifact_stage_ratio": round(ratio, 3),
        "window_minutes": window_minutes
    }
