"""Tests for Knapsack Task Balancer & Pick-Your-Poison (§18.3–§18.4)."""

import pytest
from dhriti.task_balancer import (
    pick_your_poison,
    unit_value,
    calculate_daily_load,
    evaluate_auto_fill,
    _solve_branch_and_bound_subset_sum,
)


def test_unit_normalization():
    assert unit_value("light") == 0.5
    assert unit_value("easy") == 0.5
    assert unit_value("medium") == 1.0
    assert unit_value("hard") == 2.0
    assert unit_value("challenging") == 3.0
    assert unit_value("ambitious") == 3.0
    assert unit_value(2.5) == 2.5
    assert unit_value("unknown") == 1.0


def test_calculate_daily_load():
    targets = [
        {"title": "Task A", "tier": "light"},
        {"title": "Task B", "tier": "medium"},
        {"title": "Task C", "tier": "hard"},
    ]
    load = calculate_daily_load(targets)
    assert load == 3.5


def test_deficit_targeting_no_size_limit():
    """Verify resolution of the size-3 cap defect (§18.2): 6 x 0.5u = 3.0u basket."""
    pool = [{"id": f"t_{i}", "title": f"Light task {i}", "tier": "light"} for i in range(1, 10)]
    baskets = pick_your_poison(3.0, pool, max_options=3)

    assert len(baskets) >= 1
    # First basket should have 6 items totaling 3.0 units
    assert len(baskets[0]) == 6
    total_u = sum(unit_value(t["tier"]) for t in baskets[0])
    assert total_u == pytest.approx(3.0, 0.05)


def test_pick_your_poison_multiple_options():
    backlog = [
        {"id": "t1", "title": "Subsystem A", "tier": "hard", "units": 2.0},
        {"id": "t2", "title": "Subsystem B1", "tier": "medium", "units": 1.0},
        {"id": "t3", "title": "Subsystem B2", "tier": "medium", "units": 1.0},
        {"id": "t4", "title": "Subsystem C1", "tier": "light", "units": 0.5},
        {"id": "t5", "title": "Subsystem C2", "tier": "light", "units": 0.5},
        {"id": "t6", "title": "Subsystem C3", "tier": "light", "units": 0.5},
        {"id": "t7", "title": "Subsystem C4", "tier": "light", "units": 0.5},
    ]

    options = pick_your_poison(deficit_units=2.0, pool=backlog, max_options=3)
    assert len(options) >= 2
    # Verify each basket sums close to 2.0 units
    for basket in options:
        basket_sum = sum(unit_value(t["tier"]) for t in basket)
        assert abs(basket_sum - 2.0) <= 0.25


def test_evaluate_auto_fill_needed_and_unneeded():
    backlog = [
        {"id": "t1", "tier": "medium", "units": 1.0, "age": 5},
        {"id": "t2", "tier": "medium", "units": 1.0, "age": 10},
        {"id": "t3", "tier": "hard", "units": 2.0, "age": 2},
    ]

    # Full day: no auto-fill needed
    res_full = evaluate_auto_fill(
        today_targets=[{"tier": "challenging"}], # 3.0u
        backlog=backlog,
        avg_units=3.0
    )
    assert res_full["needed"] is False
    assert len(res_full["auto_added"]) == 0

    # Light day: auto-fill needed
    res_light = evaluate_auto_fill(
        today_targets=[{"tier": "light"}], # 0.5u -> deficit 2.5u
        backlog=backlog,
        avg_units=3.0
    )
    assert res_light["needed"] is True
    assert res_light["deficit"] == 2.5
    assert len(res_light["auto_added"]) >= 1
    # Oldest item (age 10) must be included first
    assert res_light["auto_added"][0]["id"] == "t2"
