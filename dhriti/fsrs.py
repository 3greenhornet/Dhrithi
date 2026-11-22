"""FSRS, full equations, shadow mode, and canonical FSRS-6 scheduler (v0.7.0 Part 3 §3.17 & §6.2).

The DSR model — Difficulty, Stability, Retrievability — with the
canonical 21-parameter FSRS-6 equations and card state loop:

  S_0(G)  initial stability from first grade (grades 1=Again .. 4=Easy)
  S'_r    stability after a successful recall (retrievability- & grade-weighted)
  S'_f    stability after a forget (the post-lapse power update)
  D_0(G)  initial difficulty from the first grade
  D'      mean-reverting difficulty update (clamped to [1, 10])
  R(t, S) = (1 + t / (9*S))^-1   retrievability at t given S

FSRS-6 21-parameter canonical weight vector:
  [0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001,
   1.8722, 0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014,
   1.8729, 0.5425, 0.0912, 0.0658, 0.1542]

Shadow mode: from day 30 of mirror use, a weekly computation ranks
the pile under age-only and under FSRS-stability, stores the
comparison in fsrs_shadow, and emits fsrs_shadow_computed.

Gate 3 (production ranking, mirror.decay.use_stability) requires:
  (a) 6 months of mirror use,
  (b) 100 items with 3+ events,
  (c) shadow correlation >= 0.85 AND top-choice agreement in > 80% of
      weeks — the shadow must EARN the switch by agreeing with (or
      beating) the simple rule, not by novelty.
Opening is `dhriti gate open fsrs` (a cold-state act); the gate check
itself is automated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Optional, Dict, Any

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso

# Canonical 21-parameter FSRS-6 default weights per §6.2.2 (P. 20)
DEFAULT_FSRS6_WEIGHTS = [
    0.212, 1.2931, 2.3065, 8.2956,
    6.4133, 0.8334, 3.0194, 0.001,
    1.8722, 0.1666, 0.796, 1.4835,
    0.0614, 0.2629, 1.6483, 0.6014,
    1.8729, 0.5425, 0.0912, 0.0658,
    0.1542
]

DEFAULT_PARAMS = {
    "w": list(DEFAULT_FSRS6_WEIGHTS),
    "request_retention": 0.9,
    "maximum_interval": 36500,
}

DIFFICULTY_MIN, DIFFICULTY_MAX = 1.0, 10.0


class Rating(IntEnum):
    Again = 1
    Hard = 2
    Good = 3
    Easy = 4


class State(IntEnum):
    New = 0
    Learning = 1
    Review = 2
    Relearning = 3


@dataclass
class Card:
    card_id: str = ""
    stability: float = 0.0
    difficulty: float = 0.0
    reps: int = 0
    lapses: int = 0
    state: State = State.New
    last_review: Optional[datetime] = None
    due: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "stability": round(self.stability, 4),
            "difficulty": round(self.difficulty, 4),
            "reps": self.reps,
            "lapses": self.lapses,
            "state": int(self.state),
            "last_review": to_iso(self.last_review) if self.last_review else None,
            "due": to_iso(self.due) if self.due else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Card:
        def _parse(val: Any) -> Optional[datetime]:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            val_str = str(val).replace("+00:00", "Z")
            if not val_str.endswith("Z"):
                val_str += "Z"
            try:
                return parse_iso(val_str)
            except Exception:
                try:
                    return datetime.fromisoformat(str(val))
                except Exception:
                    return None

        last_rev = _parse(data.get("last_review"))
        due_dt = _parse(data.get("due"))
        return cls(
            card_id=str(data.get("card_id", "")),
            stability=float(data.get("stability", 0.0)),
            difficulty=float(data.get("difficulty", 0.0)),
            reps=int(data.get("reps", 0)),
            lapses=int(data.get("lapses", 0)),
            state=State(int(data.get("state", 0))),
            last_review=last_rev,
            due=due_dt,
        )


def retrievability(elapsed_days: float, stability: float) -> float:
    """R(t, S) = (1 + t / (9*S))^-1."""
    if stability <= 0:
        return 0.0
    if elapsed_days <= 0:
        return 1.0
    return (1.0 + elapsed_days / (9.0 * stability)) ** -1


def initial_stability(grade: int, params: Optional[dict] = None) -> float:
    """S_0 from the first grade (1=Again .. 4=Easy)."""
    p = params or DEFAULT_PARAMS
    w = p["w"]
    idx = max(0, min(3, grade - 1))
    return max(0.1, float(w[idx]))


def initial_difficulty(grade: int, params: Optional[dict] = None) -> float:
    """D_0(G) = w4 - e^(w5*(G-1)) + 1, clamped to [1, 10]."""
    p = params or DEFAULT_PARAMS
    w = p["w"]
    d = w[4] - math.exp(w[5] * (grade - 1)) + 1
    return clamp_difficulty(d)


def clamp_difficulty(d: float) -> float:
    return max(DIFFICULTY_MIN, min(DIFFICULTY_MAX, d))


def update_difficulty(d: float, grade: int, params: Optional[dict] = None) -> float:
    """D' with mean reversion (FSRS-6 canonical):
    D_raw = D - w6 * (G - 3)
    D' = w7 * D0(3) + (1 - w7) * D_raw, clamped to [1, 10].
    """
    p = params or DEFAULT_PARAMS
    w = p["w"]
    w6 = w[6]
    w7 = w[7] if len(w) > 7 else 0.0
    d_raw = d - w6 * (grade - 3)
    if w7 > 0 and len(w) > 5:
        d0_good = w[4] - math.exp(w[5] * 2) + 1  # D0(3)
        d_prime = w7 * d0_good + (1.0 - w7) * d_raw
    else:
        d_prime = d_raw
    return clamp_difficulty(d_prime)


def stability_after_recall(
    s: float,
    d: float,
    r: float,
    params: Optional[dict] = None,
    grade: int = 3
) -> float:
    """S'_r = S * (1 + e^w8 * (11 - D) * S^-w9 * (e^(w10*(1-R)) - 1) * h(G))."""
    p = params or DEFAULT_PARAMS
    w = p["w"]

    # FSRS-6 grade factor h(G)
    grade_factor = 1.0
    if len(w) > 16:
        if grade == Rating.Hard:
            grade_factor = float(w[15])
        elif grade == Rating.Easy:
            grade_factor = float(w[16])

    growth = (1.0 + math.exp(w[8]) * (11.0 - d)
              * (s ** -w[9])
              * (math.exp(w[10] * (1.0 - r)) - 1.0)
              * grade_factor)
    return max(0.1, s * growth)


def stability_after_forget(
    s: float,
    d: float,
    r: float = 0.5,
    params: Optional[dict] = None
) -> float:
    """S'_f: canonical FSRS-6 lapse update when w has >= 15 params:
    S'_f = w11 * D^-w12 * ((S + 1)^w13 - 1) * e^(w14 * (1 - R))
    """
    p = params or DEFAULT_PARAMS
    w = p["w"]
    if len(w) >= 15:
        w11, w12, w13, w14 = w[11], w[12], w[13], w[14]
        try:
            s_f = w11 * (d ** -w12) * (((s + 1.0) ** w13) - 1.0) * math.exp(w14 * (1.0 - r))
            return max(0.1, min(s, s_f))
        except (OverflowError, ValueError):
            return max(0.1, s * 0.2)
    elif len(w) > 11:
        return max(0.1, w[11] * (d ** -0.5) * min(s, 30.0) / 10.0)
    else:
        return max(0.1, s * 0.5)


def next_interval(stability: float, request_retention: float = 0.9, max_interval: int = 36500) -> float:
    """Interval inverse: I = 9 * S * (1 / R_target - 1), clamped to [1, max_interval]."""
    if stability <= 0:
        return 1.0
    target_r = max(0.01, min(0.99, request_retention))
    interval = 9.0 * stability * (1.0 / target_r - 1.0)
    return max(1.0, min(float(max_interval), round(interval, 2)))


class Scheduler:
    """FSRS-6 Production Scheduler implementing the card-state loop (§6.2.2)."""

    def __init__(self, params: Optional[dict] = None):
        self.params = dict(DEFAULT_PARAMS)
        if params:
            self.params.update(params)

    def review_card(self, card: Card, rating: Rating, now_utc: Optional[datetime] = None) -> Card:
        """Advance a card's state through FSRS-6 review."""
        now = now_utc or datetime.now(timezone.utc)
        grade = int(rating)
        req_retention = self.params.get("request_retention", 0.9)
        max_int = self.params.get("maximum_interval", 36500)

        if card.state == State.New:
            card.stability = initial_stability(grade, self.params)
            card.difficulty = initial_difficulty(grade, self.params)
            card.reps = 1
            if grade == Rating.Again:
                card.lapses = 1
                card.state = State.Learning
            else:
                card.lapses = 0
                card.state = State.Review
        else:
            elapsed_days = 1.0
            if card.last_review:
                elapsed_days = max(0.0, (now - card.last_review).total_seconds() / 86400.0)

            r = retrievability(elapsed_days, card.stability)
            card.difficulty = update_difficulty(card.difficulty, grade, self.params)

            if grade == Rating.Again:
                card.stability = stability_after_forget(card.stability, card.difficulty, r, self.params)
                card.lapses += 1
                card.state = State.Relearning
            else:
                card.stability = stability_after_recall(card.stability, card.difficulty, r, self.params, grade=grade)
                card.reps += 1
                card.state = State.Review

        interval_days = next_interval(card.stability, req_retention, max_int)
        card.last_review = now
        card.due = now + timedelta(days=interval_days)
        return card


class FsrsShadow:
    """The weekly shadow computation + the production gate."""

    def __init__(self, db: Database, config: dict,
                 clock: Optional[Clock] = None, ledger=None):
        self.db = db
        self.config = config.get("mirror", {})
        self.clock = clock or RealClock()
        self.ledger = ledger
        self.params = dict(DEFAULT_PARAMS)
        self.params.update(self.config.get("decay", {}).get(
            "fsrs_params", {}))

    # -- the shadow (gate 2) --------------------------------------------------
    def compute_shadow(self, week_start_iso: str) -> Optional[dict]:
        """Rank the open pile under age-only and under
        age/current_stability; store the comparison; emit the event."""
        items = self.db.query(
            "SELECT id, title, saved_at_utc, current_stability_days "
            "FROM content_item WHERE opened_at IS NULL AND "
            "abandoned_at IS NULL AND aged_out_at IS NULL "
            "AND intent_class != 'reference'")
        if len(items) < 2:
            return None
        now = self.clock.now_utc()

        def age_days(row):
            return (now - parse_iso(row["saved_at_utc"])).total_seconds() \
                / 86400.0

        by_age = sorted(items, key=age_days, reverse=True)
        by_stability = sorted(
            items,
            key=lambda r: age_days(r) / max(
                0.1, float(r["current_stability_days"])),
            reverse=True)
        top_age = by_age[0]["id"]
        top_stab = by_stability[0]["id"]
        different = sum(
            1 for a, b in zip(by_age, by_stability) if a["id"] != b["id"])

        # Spearman-style rank correlation between the two orderings
        rank_age = {row["id"]: i for i, row in enumerate(by_age)}
        rank_stab = {row["id"]: i for i, row in enumerate(by_stability)}
        n = len(items)
        d2 = sum((rank_age[row["id"]] - rank_stab[row["id"]]) ** 2
                 for row in items)
        correlation = 1 - 6 * d2 / (n * (n * n - 1)) if n > 1 else 1.0

        now_iso = to_iso(now)
        self.db.insert("fsrs_shadow", {
            "computed_at": now_iso,
            "week_start": week_start_iso,
            "items_compared": n,
            "items_with_different_top_choice": int(top_age != top_stab),
            "top_item_age_based": top_age,
            "top_item_stability_based": top_stab,
            "rank_correlation": round(correlation, 4),
        })
        if self.ledger is not None:
            self.ledger.record(
                "fsrs_shadow_computed",
                observed={"week": week_start_iso, "items": n,
                          "top_differs": top_age != top_stab,
                          "rank_correlation":
                              round(correlation, 4)},
                action_taken="shadow computed; the simple rule still "
                             "rules until gate 3 opens")
        return {"items_compared": n,
                "top_differs": top_age != top_stab,
                "rank_correlation": round(correlation, 4)}

    # -- gate 2: shadow mode opens at day 30 of mirror use -----------------
    def shadow_gate_open(self) -> bool:
        first = self.db.query_one(
            "SELECT MIN(saved_at_utc) AS first FROM content_item")
        if not first or not first["first"]:
            return False
        days = (self.clock.now_utc()
                - parse_iso(first["first"])).days
        return days >= 30

    # -- gate 3: production ranking -------------------------------------------
    def production_gate_status(self) -> dict:
        """(a) 6 months of use, (b) 100 items with 3+ events,
        (c) shadow agreement: correlation >= 0.85 across weeks AND
        top-choice differs in <= 20% of weeks."""
        first = self.db.query_one(
            "SELECT MIN(saved_at_utc) AS first FROM content_item")
        months_of_use = 0
        if first and first["first"]:
            months_of_use = (self.clock.now_utc()
                             - parse_iso(first["first"])).days / 30.0
        mature_items = self.db.query_one(
            "SELECT COUNT(*) AS n FROM content_item c WHERE "
            "(SELECT COUNT(*) FROM event e WHERE e.event_type LIKE "
            "'content_item_%' AND e.observed_payload LIKE "
            "'%' || substr(c.id, 1, 8) || '%') >= 3")["n"]
        shadows = self.db.query(
            "SELECT * FROM fsrs_shadow ORDER BY week_start")
        weeks = len(shadows)
        agreeing = sum(1 for s in shadows
                       if (s["rank_correlation"] or 0) >= 0.85)
        top_same = sum(1 for s in shadows
                       if not s["items_with_different_top_choice"])
        correlation_ok = weeks > 0 and agreeing == weeks
        top_ok = weeks > 0 and (top_same / weeks) > 0.8
        return {
            "months_of_use": round(months_of_use, 1),
            "mature_items": mature_items,
            "weeks_of_shadow": weeks,
            "correlation_ok": correlation_ok,
            "top_choice_ok": top_ok,
            "open": (months_of_use >= 6 and mature_items >= 100
                     and correlation_ok and top_ok),
        }

    def open_production_gate(self) -> bool:
        """The cold-state act (`dhriti gate open fsrs`): refused unless
        every condition holds. The refusal states exactly what is
        missing."""
        status = self.production_gate_status()
        if not status["open"]:
            missing = []
            if status["months_of_use"] < 6:
                missing.append(
                    f"{6 - status['months_of_use']:.1f} more months "
                    "of mirror use")
            if status["mature_items"] < 100:
                missing.append(
                    f"{100 - status['mature_items']} more items with "
                    "3+ events")
            if not status["correlation_ok"]:
                missing.append(
                    "shadow correlation below 0.85 in one or more weeks")
            if not status["top_choice_ok"]:
                missing.append(
                    "top choice differs in > 20% of shadow weeks")
            raise ValueError(
                "the FSRS gate is closed. Missing: "
                + "; ".join(missing))
        if self.ledger is not None:
            self.ledger.record(
                "fsrs_shadow_gate_opened",
                observed=status,
                action_taken="production ranking switched to "
                             "stability-based (cold-state act)")
        return True
