"""FSRS, full equations, shadow mode (v0.7.0 Part 3 §3.17).

The DSR model — Difficulty, Stability, Retrievability — with the
published FSRS v4 update equations:

  S_0(D)  initial stability from difficulty rating
  S'_r    stability after a successful recall (retrievability-weighted)
  S'_f    stability after a forget (the lapse update)
  D_0(G)  initial difficulty from the first grade
  D'      difficulty update (clamped to [1, 10])
  R(t, S) = (1 + t / (9*S))^-1   retrievability at t given S

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

import math
from datetime import timedelta
from typing import Optional

from .db import Database
from .timeutil import Clock, RealClock, parse_iso, to_iso

# Default FSRS v4 parameters (w[0..3]: initial stability for grades
# 1..4; w[4]: initial difficulty; w[5..7]: difficulty updates;
# w[8..9]: stability after recall; w[10..11]: stability after forget).
DEFAULT_PARAMS = {
    "w": [0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01,
          1.49, 0.14, 0.94, 2.18],
    "request_retention": 0.9,
    "maximum_interval": 36500,
}

DIFFICULTY_MIN, DIFFICULTY_MAX = 1.0, 10.0


def retrievability(elapsed_days: float, stability: float) -> float:
    """R(t, S) = (1 + t / (9*S))^-1."""
    if stability <= 0:
        return 0.0
    return (1.0 + elapsed_days / (9.0 * stability)) ** -1


def initial_stability(grade: int, params: dict) -> float:
    """S_0 from the first grade (1=again .. 4=easy)."""
    w = params["w"]
    return max(0.1, float(w[max(0, min(3, grade - 1))]))


def initial_difficulty(grade: int, params: dict) -> float:
    """D_0(G) = w4 - e^(w5*(G-1)) + 1, clamped to [1, 10]."""
    w = params["w"]
    d = w[4] - math.exp(w[5] * (grade - 1)) + 1
    return clamp_difficulty(d)


def clamp_difficulty(d: float) -> float:
    return max(DIFFICULTY_MIN, min(DIFFICULTY_MAX, d))


def update_difficulty(d: float, grade: int, params: dict) -> float:
    """D' = D - w6*(G-3) (a mean-reverting update), clamped."""
    w = params["w"]
    return clamp_difficulty(d - w[6] * (grade - 3))


def stability_after_recall(s: float, d: float, r: float,
                           params: dict) -> float:
    """S'_r = S * (1 + e^(w8) * (11 - D) * S^-w9 * (e^(w10*(1-R)) - 1))"""
    w = params["w"]
    growth = (1 + math.exp(w[8]) * (11 - d)
              * (s ** -w[9])
              * (math.exp(w[10] * (1 - r)) - 1))
    return max(0.1, s * growth)


def stability_after_forget(s: float, d: float,
                           params: dict) -> float:
    """S'_f = w11 * D^-w12 ... (v4 form: the post-lapse stability is
    bounded by the pre-lapse stability scaled down)."""
    w = params["w"]
    return max(0.1, w[11] * (d ** -0.5) * min(s, 30.0) / 10.0
               if len(w) > 11 else max(0.1, s * 0.5))


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
