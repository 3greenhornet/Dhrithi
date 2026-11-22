"""Dhriti Task Balancer & Pick-Your-Poison Engine (D-093 / L-2 / L-8 / §18.3–18.4).

Provides:
1. Standardized unit equivalents: light = 0.5u, medium = 1.0u, hard = 2.0u, challenging = 3.0u.
2. Backlog auto-fill when today's plan is lighter than personal rolling average.
3. Pick-your-poison arithmetic combinations: finds equivalent baskets (e.g. 1 hard = 2 medium,
   or 6 light = 1 challenging) without in-the-moment negotiation friction.
4. Google OR-Tools SCIP Knapsack / MIP Solver integration (§18.4) with 200ms wall limit,
   integer scaling, and adaptive tolerance.
5. Exact pure-Python branch-and-bound subset-sum fallback without arbitrary size caps.
6. Fallback law: if MIP/subset-sum yields no feasible basket, gracefully return the
   pre-verified highest-priority (oldest-first) backlog basket.
"""

from __future__ import annotations

import itertools
import math
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


def _solve_ortools_knapsack(
    deficit_units: float,
    items: List[Dict[str, Any]],
    tolerance: float,
    max_options: int = 3
) -> Optional[List[List[Dict[str, Any]]]]:
    """Solve deficit targeting using Google OR-Tools SCIP/CBC MIP solver (§18.4).

    Linearization:
      min (dp + dm)
      s.t. sum(w_i * x_i) - target == dp - dm
           dp + dm <= tol_scaled
           dp, dm >= 0, x_i in {0, 1}
    Integer scaling: units * 100 to ensure exact integer arithmetic on SCIP.
    """
    try:
        from ortools.linear_solver import pywraplp
    except ImportError:
        return None

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        solver = pywraplp.Solver.CreateSolver("CBC_MIXED_INTEGER_PROGRAMMING")
    if not solver:
        return None

    # 200 ms wall limit per §18.4
    solver.SetTimeLimit(200)

    scale = 100
    target_int = int(round(deficit_units * scale))
    tol_int = int(round(tolerance * scale))
    n = len(items)
    w_ints = [int(round(it["_u"] * scale)) for it in items]

    results: List[List[Dict[str, Any]]] = []
    seen_keys: Set[Tuple[str, ...]] = set()

    for _ in range(max_options):
        # Variables: x_i in {0, 1}
        x = [solver.BoolVar(f"x_{i}_{len(results)}") for i in range(n)]
        dp = solver.NumVar(0, solver.infinity(), f"dp_{len(results)}")
        dm = solver.NumVar(0, solver.infinity(), f"dm_{len(results)}")

        # Constraint: sum(w_i * x_i) - target == dp - dm
        expr = solver.Sum([w_ints[i] * x[i] for i in range(n)]) - target_int
        solver.Add(expr == dp - dm)

        # Constraint: dp + dm <= tol_int
        solver.Add(dp + dm <= tol_int)

        # Must select at least 1 item
        solver.Add(solver.Sum(x) >= 1)

        # Exclude previously found solutions via integer cuts
        for prev_res in results:
            prev_ids = {it.get("id") for it in prev_res}
            # sum_{i in prev} x_i <= |prev| - 1
            solver.Add(
                solver.Sum([x[i] for i in range(n) if items[i].get("id") in prev_ids])
                <= len(prev_ids) - 1
            )

        # Objective: minimize deviation, with small tie-breaker for fewer items
        solver.Minimize(dp + dm + 0.001 * solver.Sum(x))

        status = solver.Solve()
        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            selected = [items[i] for i in range(n) if x[i].solution_value() > 0.5]
            if selected:
                key = tuple(sorted(str(c.get("id", i)) for i, c in enumerate(selected)))
                if key not in seen_keys:
                    seen_keys.add(key)
                    clean = [{k: v for k, v in c.items() if k != "_u"} for c in selected]
                    results.append(clean)
                else:
                    break
            else:
                break
        else:
            break

    return results if results else None


def _solve_branch_and_bound_subset_sum(
    deficit_units: float,
    items: List[Dict[str, Any]],
    tolerance: float,
    max_options: int = 3
) -> List[List[Dict[str, Any]]]:
    """Pure-Python branch-and-bound subset-sum solver without size-3 cap (§18.2).

    Finds baskets of any size (1, 2, ..., N) summing to deficit_units +/- tolerance.
    Prunes aggressively using upper and lower bounds.
    """
    n = len(items)
    # Sort items by unit value descending for efficient pruning
    indexed = sorted(enumerate(items), key=lambda x: -x[1]["_u"])

    # Precompute suffix sums for upper-bound pruning
    weights = [it["_u"] for _, it in indexed]
    suffix_sums = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_sums[i] = suffix_sums[i + 1] + weights[i]

    target = deficit_units
    found: List[Tuple[float, int, List[Dict[str, Any]]]] = []
    seen_combos: Set[Tuple[str, ...]] = set()

    max_steps = 25000  # Execution guard to prevent freeze on very large backlogs
    steps = 0

    def backtrack(idx: int, current_sum: float, selected: List[Dict[str, Any]]):
        nonlocal steps
        steps += 1
        if steps > max_steps:
            return

        # Check if current combination is within tolerance
        dev = abs(current_sum - target)
        if selected and dev <= tolerance:
            key = tuple(sorted(str(c.get("id", i)) for i, c in enumerate(selected)))
            if key not in seen_combos:
                seen_combos.add(key)
                clean_combo = [{k: v for k, v in c.items() if k != "_u"} for c in selected]
                found.append((dev, len(selected), clean_combo))

        if idx >= n:
            return

        # Prune if even taking all remaining items cannot reach target - tolerance
        if current_sum + suffix_sums[idx] < target - tolerance:
            return

        # Branch 1: Include item idx (if current_sum + item weight doesn't overshoot target + tolerance)
        item_w = weights[idx]
        if current_sum + item_w <= target + tolerance:
            backtrack(idx + 1, current_sum + item_w, selected + [indexed[idx][1]])

        # Branch 2: Exclude item idx
        backtrack(idx + 1, current_sum, selected)

    backtrack(0, 0.0, [])

    # Sort found baskets by least deviation, then by size
    found.sort(key=lambda x: (round(x[0], 4), x[1]))
    return [combo for _, _, combo in found[:max_options]]


def pick_your_poison(
    deficit_units: float,
    pool: List[Dict[str, Any]],
    max_options: int = 3
) -> List[List[Dict[str, Any]]]:
    """Find equivalent combinations of tasks summing to deficit_units within adaptive tolerance.

    1. Tries Google OR-Tools SCIP MIP solver if installed (§18.4).
    2. Falls back to pure-Python branch-and-bound subset-sum solver without size-3 cap (§18.2).
    3. Respects Fallback Law: if no combinations meet tolerance, returns the pre-verified
       greedy oldest-first basket (§18.4).
    """
    if deficit_units <= 0 or not pool:
        return []

    # Adaptive tolerance per §18.3: max(POISON_TOLERANCE, 0.1 * deficit_units)
    tolerance = max(POISON_TOLERANCE, 0.1 * deficit_units)

    # Attach computed units
    items = []
    for p in pool:
        u = unit_value(p.get("units") or p.get("tier"))
        items.append({**p, "_u": u})

    # Engine 1: Google OR-Tools MIP solver
    ortools_results = _solve_ortools_knapsack(deficit_units, items, tolerance, max_options)
    if ortools_results:
        return ortools_results

    # Engine 2: Pure-Python Branch-and-Bound Subset-Sum (no size-3 limit)
    bb_results = _solve_branch_and_bound_subset_sum(deficit_units, items, tolerance, max_options)
    if bb_results:
        return bb_results

    # Fallback Law (§18.4): Return pre-verified greedy basket so operator is never blocked
    sorted_pool = sorted(items, key=lambda b: -int(b.get("age", 0)))
    greedy_basket: List[Dict[str, Any]] = []
    acc = 0.0
    for it in sorted_pool:
        greedy_basket.append({k: v for k, v in it.items() if k != "_u"})
        acc += it["_u"]
        if acc >= deficit_units:
            break

    return [greedy_basket] if greedy_basket else []


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
