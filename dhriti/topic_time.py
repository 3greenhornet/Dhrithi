"""Dhriti Topic-Time Histogram Builder (D-091 / L-11).

Transforms topic tick events into structured domain/topic stacked bar histograms
for the dashboard and digest.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Dict, Any
from .topic_extract import children_of

# Curated, consistent color palette indices
PALETTE_COUNT = 8


def day_histogram(events: List[Dict[str, Any]], minutes_window: int = 60) -> Dict[str, Any]:
    """Compile topic_tick events {host, genre, tokens, minutes, on_topic} into domain breakdown.

    Returns:
        {
            "hosts": {
                host: {
                    "total": float,
                    "segments": [{"topic": str, "minutes": float, "color_idx": int, "on": bool}],
                    "children": {topic: {subtopic: minutes}}
                }
            },
            "chips": [str],
            "total_minutes": float,
            "stage_minutes": float,
            "audience_minutes": float
        }
    """
    per_host: Dict[str, Dict[str, Any]] = {}
    all_chips: set = set()
    total_m = 0.0
    stage_m = 0.0

    for e in events:
        host = e.get("host", "unknown")
        m = float(e.get("minutes", 1.0))
        on_topic = bool(e.get("on_topic", True))
        total_m += m
        if on_topic:
            stage_m += m

        h_data = per_host.setdefault(host, {
            "total": 0.0,
            "topics": Counter(),
            "on_topic_map": {}
        })
        key = e.get("genre") or (e.get("tokens", ["untitled"])[0] if e.get("tokens") else "untitled")
        h_data["topics"][key] += m
        h_data["total"] += m
        h_data["on_topic_map"][key] = on_topic

        for ch in e.get("chips", []):
            all_chips.add(ch)

    out_hosts: Dict[str, Any] = {}
    for host, d in sorted(per_host.items(), key=lambda kv: -kv[1]["total"]):
        segs = [
            {
                "topic": t,
                "minutes": round(m, 1),
                "color_idx": i % PALETTE_COUNT,
                "on": d["on_topic_map"].get(t, True)
            }
            for i, (t, m) in enumerate(d["topics"].most_common())
        ]
        out_hosts[host] = {
            "total": round(d["total"], 1),
            "segments": segs,
            "children": {s["topic"]: children_of(s["topic"], events) for s in segs}
        }

    return {
        "hosts": out_hosts,
        "chips": sorted(list(all_chips))[:20],
        "total_minutes": round(total_m, 1),
        "stage_minutes": round(stage_m, 1),
        "audience_minutes": round(total_m - stage_m, 1),
    }
