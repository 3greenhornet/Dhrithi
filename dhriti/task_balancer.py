"""Dhriti Task Balancer & Pick-Your-Poison Engine (D-093 / L-2 / L-8).

Provides:
1. Standardized unit equivalents: light = 0.5u, medium = 1.0u, hard = 2.0u, challenging = 3.0u.
2. Backlog auto-fill when today's plan is lighter than personal rolling average.
3. Pick-your-poison arithmetic combinations: finds equivalent baskets (e.g. 1 hard = 2 medium)
   without in-the-moment negotiation friction.
"""

from __future__ import annotations

import itertools
from typing import List, Dict, Any, Tuple, Optional, Set

TIER_UNITS = {
    "light": 0.5,
    "easy": 0.5,
    "medium": 1.0,
    "hard": 2.0,
    "challenging": 3.0,
    "ambitious": 3.0,
}

POISON_TOLERANCE = 0.25


def unit_value(tier_or_units: Any) -> float:
    """Normalize tier string or numeric units to float."""
    if isinstance(tier_or_units, (int, float)):
        return float(tier_or_units)
    if isinstance(tier_or_units, str):
        return TIER_UNITS.get(tier_or_units.lower().strip(), 1.0)
    return 1.0


def pick_your_poison(deficit_units: float, pool: List[Dict[str, Any]], max_options: int = 3) -> List[List[Dict[str, Any]]]:
    """Find equivalent combinations of tasks summing to deficit_units within tolerance.

    Returns up to max_options combination baskets. Zero ranking, purely structural.
    """
    if deficit_units <= 0 or not pool:
        return []

    # Attach computed units
    items = []
    for p in pool:
        u = unit_value(p.get("units") or p.get("tier"))
        items.append({**p, "_u": u})

    found: List[List[Dict[str, Any]]] = []
    seen_combos: Set[Tuple[str, ...]] = set()

    # Search combinations of size 1, 2, 3
    for size in (1, 2, 3):
        for combo in itertools.combinations(items, size):
            total = sum(c["_u"] for c in combo)
            if abs(total - deficit_units) <= POISON_TOLERANCE:
                key = tuple(sorted(str(c.get("id", i)) for i, c in enumerate(combo)))
                if key not in seen_combos:
                    seen_combos.add(key)
                    # Clean up temporary field
                    clean_combo = [{k: v for k, v in c.items() if k != "_u"} for c in combo]
                    found.append(clean_combo)
                    if len(found) >= max_options:
                        return found

    return found


def calculate_daily_load(targets: List[Dict[str, Any]]) -> float:
    """Calculate the total units of a set of contract targets."""
    return sum(unit_value(t.get("units") or t.get("tier")) for t in targets)


def evaluate_auto_fill(
    today_targets: List[Dict[str, Any]],
    backlog: List[Dict[str, Any]],
    avg_units: float = 3.0
) -> Dict[str, Any]:
    """Evaluate whether today is light and determine auto-added tasks or poison options."""
    today_units = calculate_daily_load(today_targets)
    deficit = avg_units - today_units

    if deficit <= 0.2:
        return {
            "needed": False,
            "deficit": 0.0,
            "today_units": today_units,
            "auto_added": [],
            "poison_options": []
        }

    # Sort backlog by age (oldest first)
    sorted_backlog = sorted(backlog, key=lambda b: -int(b.get("age", 0)))
    basket: List[Dict[str, Any]] = []
    u_acc = 0.0

    for item in sorted_backlog:
        item_u = unit_value(item.get("units") or item.get("tier"))
        basket.append(item)
        u_acc += item_u
        if u_acc >= deficit:
            break

    # Check if alternative equivalent combinations exist (pick-your-poison)
    alternatives = pick_your_poison(deficit, sorted_backlog, max_options=3)

    return {
        "needed": True,
        "deficit": round(deficit, 1),
        "today_units": round(today_units, 1),
        "avg_units": avg_units,
        "auto_added": basket,
        "poison_options": alternatives
    }
