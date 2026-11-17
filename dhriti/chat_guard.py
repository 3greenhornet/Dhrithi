"""Dhriti Guard Kit -- deterministic conversation-guard core.

Covers: D-071 (hidden-response -> parking lot is handled by bridge/extension),
D-072 (rate governor), D-073 (length governor flag), D-076 (mode mapping +
escalation ladder), D-078 (Schmitt taper), D-079 (divergence debt with
anti-windup), D-082 (thread interlock).

LAW COMPLIANCE BY CONSTRUCTION:
- L-4 (content-blind): NO function in this module accepts or returns message
  text. Inputs are counters, timestamps, budget states, and verdict CODES.
  Verdict payloads that carry text never reach this module; the extension
  hashes/stores text via the sidecar content store (see content_store.py).
- L-2 (shame-safety): card lines are factual; test_card_lines_lint enforces.
- L-5 (bounded release): every budget, debt, and toll has a ceiling/expiry.
- D-014 spirit: sidecar verdicts are ESCALATION-ONLY. They can raise the
  action at most to the mode's off-scope floor; they can never produce a
  silent denial that deterministic rules would not produce.

Integration point: consumed by bridge additions (bridge/bridge_additions.py)
and persisted via content_store.kv (sidecar DB, never the ledger chain).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

class GuardMode(str, Enum):
    FULL_LOCK = "full_lock"
    REDUCED_LOCK = "reduced_lock"
    CHECKPOINT = "checkpoint"
    ADVISORY = "advisory"


class GuardAction(str, Enum):
    SEND = "send"
    HOLD_TOLL = "hold_toll"          # hold the prompt; send allowed after toll
    PARK_ONLY = "park_only"          # prompt goes to parking lot, no send
    ADVISE = "advise"                # card line only, send proceeds


R_IN_SCOPE = "in_scope"
R_BUDGET_EXHAUSTED = "budget_exhausted"
R_BURST_TOLL = "burst_toll"
R_THREAD_INTERLOCK = "thread_interlock"
R_PIVOT_BUDGET = "pivot_budget"
R_OFFSCOPE_SIDECAR = "offscope_sidecar"      # escalation-only source
R_TOLL_PAID = "toll_paid"
R_MODE_FLOOR = "mode_floor"

# Ledger event types this module suggests (caller appends them to its ledger).
EVENT_SEND_HELD = "guard_send_held"
EVENT_TOLL_PAID = "guard_toll_paid"
EVENT_PARKED = "guard_parked"
EVENT_OVERRIDE_USED = "guard_override_used"
EVENT_BURST_TOLL = "guard_burst_toll"
EVENT_THREAD_INTERLOCKED = "guard_thread_interlocked"
EVENT_THREAD_DISPOSED = "guard_thread_disposed"
EVENT_ADAPTER_BLIND = "guard_adapter_blind"
EVENT_DOM_CANARY_MISSING = "guard_dom_canary_missing"
EVENT_E2_CANARY_MISSING = "guard_e2_canary_missing"
EVENT_CONTENT_PURGED = "guard_content_purged"
EVENT_SIDECAR_ARMED = "guard_sidecar_armed"
EVENT_SENSOR_CONFLICT = "guard_sensor_conflict"
EVENT_NOVEL_DOMAIN = "guard_novel_domain"

# Taper stages, index 0 (open) .. 3 (strictest). Schmitt trigger moves on
# this ladder. Asymmetric: up is immediate on breach, down needs a clean
# streak (D-078).
TAPER_LADDER = [GuardMode.ADVISORY, GuardMode.CHECKPOINT,
                GuardMode.REDUCED_LOCK, GuardMode.FULL_LOCK]


# --------------------------------------------------------------------------
# Configuration (all values live in sealed config; nothing hot-loaded)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ModePolicy:
    """What the guard may do in each mode (D-076 mapping)."""
    hold_toll_s: int            # toll for off-scope sends (0 = no hold path)
    park_only_offscope: bool    # off-scope prompts are parked, never sent
    collapse_response: bool     # collapse-seal responses of off-scope sends
    advisory_only: bool         # never blocks anything, card lines only


MODE_POLICY: dict[GuardMode, ModePolicy] = {
    GuardMode.FULL_LOCK:    ModePolicy(0, True, False, False),
    GuardMode.REDUCED_LOCK: ModePolicy(10, False, False, False),
    GuardMode.CHECKPOINT:   ModePolicy(0, False, True, False),
    GuardMode.ADVISORY:     ModePolicy(0, False, False, True),
}

# Pivot budget per mode (declared new threads per day, D-082 companion rule).
PIVOT_BUDGET: dict[GuardMode, Optional[int]] = {
    GuardMode.FULL_LOCK: 0,
    GuardMode.REDUCED_LOCK: 1,
    GuardMode.CHECKPOINT: None,     # unlimited but each pivot is logged
    GuardMode.ADVISORY: None,
}


@dataclass(frozen=True)
class BurstConfig:
    window_s: int = 600          # 10 minutes
    threshold: int = 3           # >= 3 sends in window -> toll (D-057 live)
    toll_s: int = 10             # hold-to-send seconds while bursting
    cooldown_s: int = 600        # toll lingers this long after the breach


@dataclass(frozen=True)
class DebtConfig:
    ceiling: float = 10.0        # L-5: debt is bounded
    accrual_per_event: float = 1.0
    daily_decay: float = 0.5     # bleeds off at each cold-day boundary
    # Anti-windup (D-079): accrual freezes while the actuator is saturated.
    freeze_under: tuple = (GuardMode.FULL_LOCK,)


@dataclass(frozen=True)
class SchmittConfig:
    down_days: int = 3           # clean streak required to relax one step
    up_immediate: bool = True    # one breach tightens immediately


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

@dataclass
class ThreadInfo:
    thread_id: str
    site: str
    opened_ts: float
    disposition: Optional[str] = None   # 'parked' | 'completed' | 'abandoned'


@dataclass
class DebtState:
    value: float = 0.0
    last_decay_day: Optional[str] = None  # ISO date


@dataclass
class GuardState:
    mode: GuardMode = GuardMode.CHECKPOINT
    topic_label: str = ""            # contract-declared work line (fact only)
    prompt_budget_limit: int = 15    # per research pass (their D-054 family)
    prompt_budget_used: int = 0
    pivots_used_today: int = 0
    sends: list = field(default_factory=list)   # recent send timestamps (s)
    burst_active_until: float = 0.0             # burst toll lingering window
    threads: dict = field(default_factory=dict) # thread_id -> ThreadInfo
    debt: DebtState = field(default_factory=DebtState)
    burst: BurstConfig = field(default_factory=BurstConfig)
    debt_cfg: DebtConfig = field(default_factory=DebtConfig)
    schmitt: SchmittConfig = field(default_factory=SchmittConfig)
    clean_streak: int = 0
    taper_index: int = 1             # index into TAPER_LADDER
    sidecar_armed: bool = False      # L-9 / L-6: off by default

    def to_snapshot(self) -> str:
        return json.dumps({
            "mode": self.mode.value, "topic_label": self.topic_label,
            "prompt_budget_limit": self.prompt_budget_limit,
            "prompt_budget_used": self.prompt_budget_used,
            "pivots_used_today": self.pivots_used_today,
            "sends": self.sends[-200:],
            "burst_active_until": self.burst_active_until,
            "threads": {k: vars(v) for k, v in self.threads.items()},
            "debt": vars(self.debt), "clean_streak": self.clean_streak,
            "taper_index": self.taper_index,
            "sidecar_armed": self.sidecar_armed,
        }, sort_keys=True)

    @classmethod
    def from_snapshot(cls, raw: str) -> "GuardState":
        d = json.loads(raw)
        st = cls(
            mode=GuardMode(d["mode"]), topic_label=d.get("topic_label", ""),
            prompt_budget_limit=d["prompt_budget_limit"],
            prompt_budget_used=d["prompt_budget_used"],
            pivots_used_today=d.get("pivots_used_today", 0),
            sends=list(d.get("sends", [])),
            burst_active_until=float(d.get("burst_active_until", 0.0)),
            clean_streak=d.get("clean_streak", 0),
            taper_index=d.get("taper_index", 1),
            sidecar_armed=bool(d.get("sidecar_armed", False)),
        )
        st.debt = DebtState(**d.get("debt", {}))
        for tid, t in (d.get("threads") or {}).items():
            st.threads[tid] = ThreadInfo(**t)
        return st


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------

def prompt_fingerprint(text: str) -> str:
    """sha256 of the prompt. This is the ONLY form in which prompt content
    participates in guard decisions: a hash, never the text (L-4)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def decay_debt(state: GuardState, today: date) -> float:
    """Daily decay at cold-day boundary. Idempotent per day."""
    iso = today.isoformat()
    if state.debt.last_decay_day == iso:
        return state.debt.value
    state.debt.value = max(0.0, state.debt.value - state.debt_cfg.daily_decay)
    state.debt.last_decay_day = iso
    return state.debt.value


def accrue_debt(state: GuardState, amount: Optional[float] = None) -> float:
    """Accrue on hold/park events. Anti-windup: frozen under FULL_LOCK so a
    long lock cannot accumulate unbounded rebound pressure (D-079)."""
    if state.mode in state.debt_cfg.freeze_under:
        return state.debt.value
    amt = state.debt_cfg.accrual_per_event if amount is None else float(amount)
    state.debt.value = min(state.debt_cfg.ceiling, state.debt.value + amt)
    return state.debt.value


def burst_toll_active(state: GuardState, now_ts: float) -> tuple[bool, int]:
    """Rate governor (D-072). True once >= threshold sends fall inside the
    window; the toll then lingers for cooldown_s after the burst passes.
    Content-blind: timestamps only. Side effect: arms the lingering window
    when the threshold is crossed."""
    cfg = state.burst
    recent = [t for t in state.sends if now_ts - t <= cfg.window_s]
    if len(recent) >= cfg.threshold:
        state.burst_active_until = max(state.burst_active_until,
                                       now_ts + cfg.cooldown_s)
        return True, cfg.toll_s
    if now_ts < state.burst_active_until:
        return True, cfg.toll_s
    return False, 0


def schmitt_step(state: GuardState, breach: bool) -> GuardMode:
    """D-078: asymmetric stage transition. Breach -> one step stricter
    immediately; clean_streak >= down_days -> one step relaxed."""
    cfg = state.schmitt
    if breach:
        state.taper_index = min(len(TAPER_LADDER) - 1, state.taper_index + 1)
        state.clean_streak = 0
    else:
        state.clean_streak += 1
        if state.clean_streak >= cfg.down_days and state.taper_index > 0:
            state.taper_index -= 1
            state.clean_streak = 0
    state.mode = TAPER_LADDER[state.taper_index]
    return state.mode


# --------------------------------------------------------------------------
# Thread interlock (D-082): trapped-key for chat threads
# --------------------------------------------------------------------------

def can_open_thread(state: GuardState, thread_id: str,
                    site: str, now_ts: float) -> tuple[bool, str]:
    """A new thread is a declared pivot. Rules, all structural:
    1. Any prior thread still open (not parked/completed/abandoned) must be
       disposed first -- the key to thread N+1 is the disposal of thread N.
    2. Pivot budget per mode (FULL_LOCK: 0, REDUCED_LOCK: 1, else logged).
    """
    if thread_id in state.threads:
        return True, R_IN_SCOPE
    open_threads = [t for t in state.threads.values() if t.disposition is None]
    if open_threads:
        return False, R_THREAD_INTERLOCK
    budget = PIVOT_BUDGET[state.mode]
    if budget is not None and state.pivots_used_today >= budget:
        return False, R_PIVOT_BUDGET
    return True, R_IN_SCOPE


def open_thread(state: GuardState, thread_id: str, site: str,
                now_ts: float) -> tuple[bool, str, list]:
    ok, reason = can_open_thread(state, thread_id, site, now_ts)
    events = []
    if not ok:
        events.append({"type": EVENT_THREAD_INTERLOCKED,
                       "thread_id": thread_id, "site": site,
                       "reason": reason, "ts": now_ts})
        return False, reason, events
    if thread_id not in state.threads:
        state.pivots_used_today += 1
    state.threads[thread_id] = ThreadInfo(thread_id, site, now_ts)
    return True, reason, events


def dispose_thread(state: GuardState, thread_id: str, disposition: str,
                   now_ts: float) -> list:
    info = state.threads.get(thread_id)
    events = []
    if info is not None and info.disposition is None:
        if disposition not in ("parked", "completed", "abandoned"):
            raise ValueError("disposition must be parked|completed|abandoned")
        info.disposition = disposition
        events.append({"type": EVENT_THREAD_DISPOSED, "thread_id": thread_id,
                       "disposition": disposition, "ts": now_ts})
    return events


# --------------------------------------------------------------------------
# Decision engine
# --------------------------------------------------------------------------

@dataclass
class Decision:
    action: GuardAction
    reason: str
    toll_seconds: int = 0
    collapse_response: bool = False
    card_lines: list = field(default_factory=list)   # factual, L-2-safe
    events: list = field(default_factory=list)
    prompt_hash: str = ""


def budget_line(state: GuardState) -> str:
    remaining = max(0, state.prompt_budget_limit - state.prompt_budget_used)
    return f"Pass budget: {remaining} remaining"


def _card(state: GuardState, *facts: Optional[str],
          tail: str = "Park, take the toll, or cancel.") -> list:
    """Neutral card lines. Facts only; the caller states the off-scope fact
    explicitly so a burst-hold of an IN-scope prompt never claims otherwise
    (L-7: the record is faced, not bent)."""
    lines = [f for f in facts if f]
    lines.append(tail)
    return lines


def offscope_line(state: GuardState) -> Optional[str]:
    return f"Off-scope for: {state.topic_label}" if state.topic_label else None


def _mode_floor(state: GuardState, in_scope: bool) -> Decision:
    """Baseline action from mode policy alone (D-076)."""
    pol = MODE_POLICY[state.mode]
    if pol.advisory_only:
        if not in_scope:
            return Decision(GuardAction.SEND, R_MODE_FLOOR,
                            card_lines=_card(state, offscope_line(state),
                                             budget_line(state),
                                             tail="Noted."))
        return Decision(GuardAction.SEND, R_MODE_FLOOR)
    if in_scope:
        return Decision(GuardAction.SEND, R_IN_SCOPE)
    if pol.park_only_offscope:
        return Decision(GuardAction.PARK_ONLY, R_MODE_FLOOR,
                        card_lines=_card(state, offscope_line(state),
                                         tail="Parked. Disposal at day_close."))
    if pol.hold_toll_s > 0:
        return Decision(GuardAction.HOLD_TOLL, R_MODE_FLOOR,
                        toll_seconds=pol.hold_toll_s,
                        card_lines=_card(state, offscope_line(state),
                                         budget_line(state)))
    return Decision(GuardAction.SEND, R_MODE_FLOOR,
                    collapse_response=pol.collapse_response,
                    card_lines=_card(state, offscope_line(state),
                                     budget_line(state),
                                     tail="Response will be held until "
                                          "cold review."))


def structural_reason(state: GuardState, now_ts: float) -> Optional[str]:
    """Which structural rule would fire first (for /guard/state previews)."""
    if state.prompt_budget_used >= state.prompt_budget_limit:
        return R_BUDGET_EXHAUSTED
    if burst_toll_active(state, now_ts)[0]:
        return R_BURST_TOLL
    return None


def decide(state: GuardState, now_ts: float, in_scope: Optional[bool] = None,
           sidecar_verdict: Optional[dict] = None,
           prompt_hash: str = "") -> Decision:
    """Single entry point for a send attempt.

    in_scope: None = unknown (no classification available -> structural
    rules only). True/False come from the deterministic embedding gate or
    the sidecar (escalation-only).
    sidecar_verdict: {"escalate": "park"|"collapse"|None, "function_code":
    "P-15"|..., "confidence": float} -- see classifier_sidecar/verdict.py.
    """
    events: list = []
    scope_known = in_scope is not None
    base = _mode_floor(state, bool(in_scope) if scope_known else True)
    decision = replace(base, prompt_hash=prompt_hash)

    # 1. Budget ceiling (L-5) outranks everything else.
    if state.prompt_budget_used >= state.prompt_budget_limit:
        if MODE_POLICY[state.mode].advisory_only:
            decision.reason = R_BUDGET_EXHAUSTED
            decision.card_lines = _card(state, budget_line(state),
                                        tail="Budget exhausted. Noted.")
        else:
            decision = replace(decision,
                               action=GuardAction.PARK_ONLY,
                               reason=R_BUDGET_EXHAUSTED,
                               toll_seconds=0, collapse_response=False,
                               card_lines=_card(state, budget_line(state),
                                                tail="Pass budget exhausted. "
                                                     "Park it."))

    # 2. Burst toll (rate governor) applies regardless of scope.
    elif burst_toll_active(state, now_ts)[0] and \
            not MODE_POLICY[state.mode].advisory_only:
        _, toll = burst_toll_active(state, now_ts)
        if decision.action == GuardAction.SEND:
            decision.action = GuardAction.HOLD_TOLL
        decision.toll_seconds = max(decision.toll_seconds, toll)
        decision.reason = R_BURST_TOLL
        decision.card_lines = _card(state, budget_line(state),
                                    tail="Burst toll active. Park, take the "
                                         "toll, or cancel.")
        events.append({"type": EVENT_BURST_TOLL, "ts": now_ts,
                       "prompt_hash": prompt_hash})

    # 3. Sidecar escalation (bounded by mode floor; never silent-deny).
    if sidecar_verdict and sidecar_verdict.get("escalate") and \
            decision.reason != R_BUDGET_EXHAUSTED:
        pol = MODE_POLICY[state.mode]
        if state.mode == GuardMode.FULL_LOCK or pol.park_only_offscope:
            decision.action = GuardAction.PARK_ONLY
            decision.card_lines = _card(state, offscope_line(state),
                                        budget_line(state),
                                        tail="Parked. Disposal at day_close.")
        elif state.mode == GuardMode.REDUCED_LOCK:
            decision.action = GuardAction.HOLD_TOLL
            decision.toll_seconds = max(decision.toll_seconds,
                                        pol.hold_toll_s)
            decision.card_lines = _card(state, offscope_line(state),
                                        budget_line(state))
        else:  # CHECKPOINT / ADVISORY: collapse-seal response, never block
            decision.collapse_response = True
            decision.card_lines = _card(state, offscope_line(state),
                                        budget_line(state),
                                        tail="Response will be held until "
                                             "cold review.")
        decision.reason = R_OFFSCOPE_SIDECAR
        events.append({"type": EVENT_SEND_HELD, "ts": now_ts,
                       "prompt_hash": prompt_hash,
                       "source": "sidecar",
                       "code": sidecar_verdict.get("function_code")})

    # 4. Structural off-scope (embedding gate, no sidecar involved).
    elif scope_known and not in_scope and \
            decision.reason not in (R_OFFSCOPE_SIDECAR, R_BUDGET_EXHAUSTED):
        pol = MODE_POLICY[state.mode]
        if pol.advisory_only:
            decision.card_lines = _card(state, offscope_line(state),
                                        budget_line(state), tail="Noted.")
        elif pol.park_only_offscope:
            decision = replace(decision, action=GuardAction.PARK_ONLY,
                               reason=R_MODE_FLOOR,
                               card_lines=_card(state, offscope_line(state),
                                                tail="Parked. Disposal at "
                                                     "day_close."))
        elif pol.hold_toll_s > 0 and decision.action == GuardAction.SEND:
            decision = replace(decision, action=GuardAction.HOLD_TOLL,
                               toll_seconds=max(decision.toll_seconds,
                                                pol.hold_toll_s),
                               reason=R_MODE_FLOOR,
                               card_lines=_card(state, offscope_line(state),
                                                budget_line(state)))
        elif pol.collapse_response and decision.action == GuardAction.SEND:
            decision.collapse_response = True

    # 5. Debt accrual + event record for anything that was not a clean send.
    if decision.action in (GuardAction.HOLD_TOLL, GuardAction.PARK_ONLY):
        new_debt = accrue_debt(state)
        events.append({"type": EVENT_SEND_HELD, "ts": now_ts,
                       "prompt_hash": prompt_hash, "reason": decision.reason,
                       "action": decision.action.value, "debt": new_debt})
    if decision.action == GuardAction.SEND and not decision.collapse_response:
        state.prompt_budget_used += 1
        state.sends.append(now_ts)
    return decision


def confirm_toll_paid(state: GuardState, now_ts: float,
                      prompt_hash: str = "") -> Decision:
    """Extension reports the toll countdown completed. Honesty: the delay is
    recorded (mirrors break_glass honored_delay honesty)."""
    state.sends.append(now_ts)
    state.prompt_budget_used += 1
    return Decision(GuardAction.SEND, R_TOLL_PAID,
                    prompt_hash=prompt_hash,
                    events=[{"type": EVENT_TOLL_PAID, "ts": now_ts,
                             "prompt_hash": prompt_hash,
                             "honored_delay": True}])


def record_override(state: GuardState, now_ts: float,
                    prompt_hash: str = "") -> list:
    """User overrode a soft action (collapse/park). Logged, never hidden."""
    return [{"type": EVENT_OVERRIDE_USED, "ts": now_ts,
             "prompt_hash": prompt_hash}]


def mark_adapter_blind(state: GuardState, site: str, now_ts: float,
                       detail: str = "") -> list:
    """Fail-visible blindness: guard must announce it, never pass silently."""
    return [{"type": EVENT_ADAPTER_BLIND, "site": site, "ts": now_ts,
             "detail": detail}]


def snapshot_for_digest(state: GuardState, now_ts: float) -> dict:
    """Metrics for the Experiment view (guard measured by its own rules)."""
    bursting, _ = burst_toll_active(state, now_ts)
    return {
        "mode": state.mode.value,
        "prompt_budget_used": state.prompt_budget_used,
        "prompt_budget_limit": state.prompt_budget_limit,
        "pivots_used_today": state.pivots_used_today,
        "open_threads": [t.thread_id for t in state.threads.values()
                         if t.disposition is None],
        "debt_value": round(state.debt.value, 2),
        "debt_ceiling": state.debt_cfg.ceiling,
        "debt_frozen": state.mode in state.debt_cfg.freeze_under,
        "bursting": bursting,
        "clean_streak": state.clean_streak,
        "taper_stage": state.mode.value,
        "sidecar_armed": state.sidecar_armed,
    }
