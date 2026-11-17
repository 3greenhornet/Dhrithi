"""Dhriti Guard Kit -- guard metrics for the digest / Experiment view.

Pure functions, stdlib only. Feeds the aftermath (fifth view) with the
guard's own record: park:break ratio (near-miss pyramid), kill-chain
attribution (which barrier actually interrupted), and the EDRR novelty
detector (early detection, rapid response). The guard must be measured by
the same five-view honesty as everything else (L-7).
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional


# --------------------------------------------------------------------------
# Near-miss pyramid (D-085): park:break ratio as a leading indicator
# --------------------------------------------------------------------------

def park_break_ratio(series: list[dict], floor: float = 2.0) -> dict:
    """series: [{"label": "2026-W46", "parks": 9, "breaks": 2}, ...]
    ordered oldest -> newest.

    Health logic (safety-culture borrowing):
    - ratio >= floor  : healthy -- many near-misses per incident
    - parks falling while breaks hold steady across the last two buckets
      -> "routed_around": the guard is being bypassed, not obeyed
    """
    if not series:
        return {"ratio": None, "healthy": None, "routed_around": False,
                "note": "no data"}
    last = series[-1]
    ratio = (last["parks"] / last["breaks"]) if last["breaks"] else None
    routed = False
    if len(series) >= 2:
        prev, cur = series[-2], series[-1]
        parks_down = cur["parks"] < prev["parks"]
        breaks_steady = abs(cur["breaks"] - prev["breaks"]) <= max(
            1, int(0.2 * max(prev["breaks"], 1)))
        routed = parks_down and breaks_steady and last["parks"] <= prev["breaks"]
    healthy = (ratio is not None and ratio >= floor)
    return {"ratio": None if ratio is None else round(ratio, 2),
            "healthy": healthy, "routed_around": routed,
            "floor": floor,
            "note": ("falling parks with steady breaks: guard likely "
                     "routed around" if routed else "")}


# --------------------------------------------------------------------------
# Kill-chain attribution: where does the interruption actually fire?
# --------------------------------------------------------------------------

STAGES = ["tab_open", "navigate", "type", "send_held", "response_hidden",
          "thread_open_refused"]


def kill_chain_attribution(events: Iterable[dict]) -> dict:
    """events: guard_* ledger events with a 'stage' field (bridge handlers
    stamp it). Returns counts per stage + the dominant barrier. This is the
    stage-ratio idea applied to the guard funnel (D-046 analogue)."""
    counts = Counter(e.get("stage", "unknown") for e in events
                     if str(e.get("type", "")).startswith("guard_"))
    total = sum(counts.values())
    dominant = counts.most_common(1)[0][0] if counts else None
    return {"counts": dict(counts), "total": total, "dominant_stage": dominant,
            "note": "dominant stage tells you which barrier does the work"}


# --------------------------------------------------------------------------
# EDRR novelty detector (early detection, rapid response)
# --------------------------------------------------------------------------

def novelty_domains(seen: set[str], recent_domains: Counter | dict,
                    threshold: int = 3) -> list[dict]:
    """Domains never seen before that appeared >= threshold times in the
    recent window -> reclassify queue BEFORE habit formation. Pure; the
    caller feeds `seen` from the ledger's domain history."""
    found = []
    for domain, count in dict(recent_domains).items():
        if domain not in seen and count >= threshold:
            found.append({"domain": domain, "count": count})
    return sorted(found, key=lambda d: -d["count"])


# --------------------------------------------------------------------------
# Sensor conflict (D-080): two weak observers catch what one cannot
# --------------------------------------------------------------------------

def sensor_conflict(aw_browser_minutes: float, ext_nav_events: int,
                    aw_quality: str = "OK", ext_quality: str = "OK",
                    min_minutes: float = 1.0) -> Optional[dict]:
    """ActivityWatch reports browser-foreground minutes while the extension
    reports zero navigation events -> either a blind adapter or another
    browser (the named E1 hole). Both are digest-worthy; neither is
    silently dropped."""
    if aw_quality not in ("OK", "DEGRADED") or ext_quality not in ("OK", "DEGRADED"):
        return None  # a dead sensor proves nothing by disagreement
    if aw_browser_minutes >= min_minutes and ext_nav_events == 0:
        return {"conflict": True,
                "aw_browser_minutes": aw_browser_minutes,
                "ext_nav_events": ext_nav_events,
                "hypothesis": "other_browser_or_blind_adapter",
                "note": "check adapter arm status and browser coverage"}
    return None


# --------------------------------------------------------------------------
# Digest block renderer
# --------------------------------------------------------------------------

def render_guard_block(snapshot: dict, ratio: dict, chain: dict,
                       novel: list[dict]) -> str:
    """One factual block for the weekly digest / Experiment view."""
    lines = ["## Guard", ""]
    lines.append(f"- mode: {snapshot.get('mode')}")
    lines.append(f"- budget: {snapshot.get('prompt_budget_used')}/"
                 f"{snapshot.get('prompt_budget_limit')}")
    lines.append(f"- debt: {snapshot.get('debt_value')} / "
                 f"{snapshot.get('debt_ceiling')}"
                 + (" (frozen)" if snapshot.get("debt_frozen") else ""))
    lines.append(f"- open threads: "
                 f"{', '.join(snapshot.get('open_threads') or ['none'])}")
    lines.append(f"- park:break ratio: {ratio.get('ratio')}"
                 + (" -- healthy" if ratio.get("healthy") else ""))
    if ratio.get("routed_around"):
        lines.append(f"- FLAG: {ratio.get('note')}")
    if chain.get("dominant_stage"):
        lines.append(f"- dominant interruption stage: "
                     f"{chain['dominant_stage']} ({chain['total']} events)")
    if novel:
        lines.append("- novel domains (reclassify queue): "
                     + ", ".join(d["domain"] for d in novel))
    return "\n".join(lines)
