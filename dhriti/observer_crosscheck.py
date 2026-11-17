"""Dhriti Guard Kit -- observer cross-check (D-080).

Sensor disagreement as a bypass detector. The pure logic lives in
guard_metrics.sensor_conflict; this module adds the thin, best-effort
ActivityWatch poll (same shape as their activitywatch adapter: urllib,
loopback REST, never raises) and an hourly bucket join.

Their adapter family: this is an OBSERVATION-role helper, off by default,
armed like any other adapter (probe -> arm -> status).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

from dhriti.guard_metrics import sensor_conflict


AW_DEFAULT = "http://127.0.0.1:5600"


def poll_activitywatch(base_url: str = AW_DEFAULT,
                       bucket_id: str = "aw-watcher-window_",
                       timeout: float = 2.0,
                       query: str = "?timeframes=[{\"start\":\"1h ago\",\"end\":\"now\"}]") -> Optional[dict]:
    """Best-effort REST poll. Returns None on any failure (observer_poll_failed
    is the caller's event, matching house vocabulary)."""
    url = f"{base_url}/api/0/buckets/{bucket_id}/events{query}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def browser_minutes_from_aw(events: Optional[list],
                            browser_apps: tuple = ("chrome", "msedge",
                                                    "firefox", "brave")) -> float:
    """Sum app-duration minutes for known browser executables. Best-effort
    parse of aw-watcher-window events ({data: {app, duration}})."""
    if not events:
        return 0.0
    total_s = 0.0
    for e in events:
        data = (e or {}).get("data") or {}
        app = str(data.get("app", "")).lower()
        if any(b in app for b in browser_apps):
            total_s += float(data.get("duration", 0) or 0)
    return total_s / 60.0


def hourly_conflict_scan(hours: list[dict]) -> list[dict]:
    """hours: [{"hour": "14", "aw_browser_minutes": 12.0,
                "ext_nav_events": 0, "aw_quality": "OK",
                "ext_quality": "OK"}, ...]
    Returns conflict rows for the digest."""
    out = []
    for h in hours:
        c = sensor_conflict(h.get("aw_browser_minutes", 0.0),
                            h.get("ext_nav_events", 0),
                            h.get("aw_quality", "OK"),
                            h.get("ext_quality", "OK"))
        if c:
            c["hour"] = h.get("hour")
            out.append(c)
    return out


# --------------------------------------------------------------------------
# Known-bug-aware quality hint (borrowed from the raw-material AW notes)
# --------------------------------------------------------------------------
# The reference documents two ActivityWatch failure signatures:
#   1. PR #561 heartbeat bug: merged events lose their ID -> ALL event
#      durations become zero. Duration data looks present but is worthless.
#   2. Long-query bug: an "All time" web-UI query holds the GIL -> the
#      REST API returns 503 Server busy for up to ~40 minutes.
# A cross-check fed by a silently-worthless observer is worse than a dead
# one (D-077's logic, applied to the sensor). aw_quality_hint maps the
# signature to the house telemetry_quality vocabulary (OK / MISSING /
# DEGRADED / SUSPECT) so the digest can face it (L-7).

def aw_quality_hint(events: Optional[list],
                    polled: bool = True) -> str:
    """events: the list returned by poll_activitywatch (None = poll failed).
    Returns one of OK / MISSING / DEGRADED / SUSPECT."""
    if not polled or events is None:
        return "MISSING"          # poll failed (or 503 long-query window)
    if len(events) == 0:
        return "DEGRADED"         # reachable but empty -- watcher down?
    durations = [float(((e or {}).get("data") or {}).get("duration", 0) or 0)
                 for e in events]
    if durations and all(d == 0.0 for d in durations):
        return "SUSPECT"          # PR #561 zero-duration signature
    return "OK"


# --------------------------------------------------------------------------
# Process lineage cross-check (borrowed from the raw-material Sysmon notes)
# --------------------------------------------------------------------------
# Sysmon Event 1 parent fields can be spoofed (parent-PID injection via
# PROC_THREAD_ATTRIBUTE_PARENT_PROCESS). Security Event 4688's
# "Creator Process ID" records the REAL parent. The house rule from the
# reference: collect both; on disagreement, record `lineage_conflict`.
# Lineage keys are ProcessGuid / ParentProcessGuid, never bare PIDs.

EVENT_LINEAGE_CONFLICT = "guard_lineage_conflict"


def lineage_conflict(parent_sysmon: Optional[str],
                     parent_4688: Optional[str]) -> Optional[dict]:
    """Compare the parent reported by Sysmon Event 1 against the parent
    reported by Security 4688 for the same child process. Returns None
    when they agree or either is unknown (an unknown sensor is MISSING
    telemetry, not a conflict -- disagreement is only signal when both
    sensors spoke)."""
    if not parent_sysmon or not parent_4688:
        return None
    ps, p4 = parent_sysmon.strip().lower(), parent_4688.strip().lower()
    if ps == p4:
        return None
    return {
        "conflict": True,
        "sysmon_parent": parent_sysmon,
        "sec4688_parent": parent_4688,
        "event": EVENT_LINEAGE_CONFLICT,
        "note": "Sysmon Event 1 parent can be spoofed "
                "(PROC_THREAD_ATTRIBUTE_PARENT_PROCESS); 4688 Creator "
                "Process ID is authoritative. Track by ProcessGuid, "
                "never bare PID.",
    }
