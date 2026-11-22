"""Tests for Canonical FSRS-6 Scheduler & Card State Loop (§6.2.2)."""

from datetime import datetime, timezone, timedelta
import pytest
from dhriti.fsrs import (
    Scheduler,
    Card,
    Rating,
    State,
    retrievability,
    initial_stability,
    initial_difficulty,
    update_difficulty,
    stability_after_recall,
    stability_after_forget,
    next_interval,
    DEFAULT_PARAMS,
    DEFAULT_FSRS6_WEIGHTS,
)


def test_canonical_fsrs6_parameters():
    assert len(DEFAULT_FSRS6_WEIGHTS) == 21
    assert DEFAULT_FSRS6_WEIGHTS[0] == 0.212
    assert DEFAULT_FSRS6_WEIGHTS[3] == 8.2956
    assert DEFAULT_FSRS6_WEIGHTS[7] == 0.001


def test_retrievability_monotonicity():
    # R(0) = 1.0
    assert retrievability(0.0, 10.0) == 1.0
    # Decays over time
    r_5 = retrievability(5.0, 10.0)
    r_10 = retrievability(10.0, 10.0)
    assert r_5 > r_10
    # Higher stability gives higher retrievability at same elapsed days
    assert retrievability(10.0, 25.0) > retrievability(10.0, 5.0)


def test_fsrs6_difficulty_mean_reversion():
    d0_good = initial_difficulty(Rating.Good)
    # Easy review (grade 4) should decrease difficulty
    d_easy = update_difficulty(d0_good, Rating.Easy)
    assert d_easy < d0_good
    # Again review (grade 1) should increase difficulty
    d_again = update_difficulty(d0_good, Rating.Again)
    assert d_again > d0_good
    # Clamping
    assert 1.0 <= d_easy <= 10.0
    assert 1.0 <= d_again <= 10.0


def test_card_state_lifecycle():
    scheduler = Scheduler()
    now = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
    card = Card(card_id="flashcard_1")
    assert card.state == State.New

    # 1. First review: Good
    card = scheduler.review_card(card, Rating.Good, now_utc=now)
    assert card.state == State.Review
    assert card.reps == 1
    assert card.lapses == 0
    assert card.stability > 0.1
    assert card.due is not None
    assert card.due > now

    # 2. Second review after 3 days: Easy
    day2 = now + timedelta(days=3)
    s_before = card.stability
    card = scheduler.review_card(card, Rating.Easy, now_utc=day2)
    assert card.state == State.Review
    assert card.reps == 2
    assert card.stability > s_before

    # 3. Third review after 10 days: Again (Lapse)
    day3 = day2 + timedelta(days=10)
    card = scheduler.review_card(card, Rating.Again, now_utc=day3)
    assert card.state == State.Relearning
    assert card.lapses == 1
    assert card.stability < s_before


def test_card_serialization():
    card = Card(
        card_id="test_card",
        stability=4.5,
        difficulty=3.2,
        reps=3,
        lapses=1,
        state=State.Review,
        last_review=datetime(2026, 11, 20, 10, 0, 0, tzinfo=timezone.utc),
        due=datetime(2026, 11, 25, 10, 0, 0, tzinfo=timezone.utc),
    )
    d = card.to_dict()
    assert d["card_id"] == "test_card"
    assert d["reps"] == 3
    assert d["state"] == 2

    restored = Card.from_dict(d)
    assert restored.card_id == card.card_id
    assert restored.stability == card.stability
    assert restored.state == card.state
