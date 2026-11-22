"""Dhriti Guard Kit -- conformance view (D-083 / §8.1–8.3): the contract as a normative
process model.

Provides:
1. Normative Petri Net model N = (P, T, F) constructed from the sealed contract stages.
2. Token-based Petri Net replay (§8.2) measuring fitness:
     Fitness(sigma, N) = 1/2 * (1 - m/c) + 1/2 * (1 - r/p)
   where:
     p = tokens produced
     c = tokens consumed
     m = missing tokens (mandatory transitions skipped or fired out of order)
     r = remaining tokens (improper completion or unconsumed state)
   Protocol violation threshold: Fitness < 0.95.
3. Resolution of the Circularity Defect (§8.3): replays observed events against the
   pre-authored sealed contract normative model, never discovering a tautological model
   from the observed log itself.
4. Pure-Python stdlib token replay engine (always available offline) + optional PM4Py
   integration when pm4py is installed.
5. First divergence identification and formatted markdown conformance reporting.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


# --------------------------------------------------------------------------
# Normative model from the contract + day window config
# --------------------------------------------------------------------------

def build_normative(
    day_window: dict,
    contract_line: str = "",
    expected_evidence: int = 1
) -> list[dict]:
    """day_window: {"start": "HH:MM", "day_close": "HH:MM", "end": "HH:MM"}
    Returns ordered stages with required/forbidden event predicates.
    """
    return [
        {
            "name": "sealed_contract",
            "require": ("contract_sealed",),
            "forbid": (),
            "note": contract_line or "contract present"
        },
        {
            "name": "session_active",
            "require": ("session_active",),
            "forbid": (),
            "note": f"evidence events >= {expected_evidence}"
        },
        {
            "name": "evidence_submitted",
            "require": ("evidence_submitted",),
            "forbid": (),
            "note": "at least 1 valid learning/work proof submitted"
        },
        {
            "name": "deep_work",
            "require": (),
            "forbid": ("browser_navigation:blocked_category", "guard_break_tripped"),
            "note": "no blocked-category navigation while ACTIVE"
        },
        {
            "name": "pass_closure",
            "require": (),
            "forbid": ("research_pass_expired",),
            "note": "no pass expires UNANSWERED"
        },
        {
            "name": "day_close",
            "require": ("day_close",),
            "forbid": (),
            "note": "release at window_end (L-5)"
        },
    ]


# --------------------------------------------------------------------------
# Token-Based Petri Net Replay (§8.2 - Pure Python Engine)
# --------------------------------------------------------------------------

class NormativePetriNet:
    """Normative Petri Net N = (P, T, F) constructed from the sealed contract."""

    def __init__(self, stages: list[dict]):
        self.stages = stages
        # Ordered places: p_start -> p_sealed -> p_active -> p_evidence -> p_closed
        self.places = ["p_start", "p_sealed", "p_active", "p_evidence", "p_closed"]
        self.initial_place = "p_start"
        self.final_place = "p_closed"

        # Allowed transitions mapping: event_type -> (input_place, output_place)
        self.transitions: Dict[str, Tuple[str, str]] = {
            "contract_sealed": ("p_start", "p_sealed"),
            "session_active": ("p_sealed", "p_active"),
            "evidence_submitted": ("p_active", "p_evidence"),
            "learning_proof_submitted": ("p_active", "p_evidence"),
            "work_proof_submitted": ("p_active", "p_evidence"),
            "day_close": ("p_evidence", "p_closed"),
            "session_close": ("p_evidence", "p_closed"),
            "contract_fulfilled": ("p_evidence", "p_closed"),
        }

        # Neutral work loop transitions (fired during active session without stage change)
        self.loop_transitions = {
            "target_progress", "code_commit", "task_completed", "pomodoro_completed",
            "heartbeat", "guard_park", "research_pass_granted", "research_pass_closed"
        }

        # Explicit forbidden events from stages
        self.forbidden_events: set[str] = set()
        for st in stages:
            for fb in st.get("forbid", ()):
                self.forbidden_events.add(fb)

    def replay_trace(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replay an event trace against the normative Petri Net.

        Maintains token counts:
          p: produced
          c: consumed
          m: missing (fired without required input token)
          r: remaining (tokens left in unclosed places at end)

        Fitness = 1/2 * (1 - m/c) + 1/2 * (1 - r/p)
        """
        tokens = defaultdict(int)
        # Initial marking: 1 token in initial_place
        tokens[self.initial_place] = 1
        p = 1
        c = 0
        m = 0

        first_divergence: Optional[Dict[str, Any]] = None
        fired_transitions = []

        for e in events:
            etype = e.get("type", "")
            cat = e.get("category", "")
            full_type = f"{etype}:{cat}" if cat else etype

            # Check if event is explicitly forbidden
            is_forbidden = (
                etype in self.forbidden_events
                or full_type in self.forbidden_events
                or etype.startswith("guard_break")
                or etype == "research_pass_expired"
            )

            if is_forbidden:
                # Forbidden transition: incurs missing token penalty
                m += 1
                c += 1
                if first_divergence is None:
                    first_divergence = {
                        "event": e,
                        "reason": f"forbidden_event_occurred: {full_type}"
                    }
                continue

            # Check if event corresponds to a normative state transition
            trans = self.transitions.get(etype)
            if trans:
                in_p, out_p = trans
                # Try consuming token from in_p
                if tokens[in_p] > 0:
                    tokens[in_p] -= 1
                    c += 1
                else:
                    # Missing token penalty
                    m += 1
                    c += 1
                    if first_divergence is None:
                        first_divergence = {
                            "event": e,
                            "reason": f"missing_prerequisite_token: {in_p} required for {etype}"
                        }

                # Produce token to out_p
                tokens[out_p] += 1
                p += 1
                fired_transitions.append(etype)
            elif etype in self.loop_transitions or "progress" in etype or "heartbeat" in etype:
                # Active session loop transition
                if tokens["p_active"] > 0 or tokens["p_evidence"] > 0:
                    pass
                else:
                    # Action occurred while session was not active
                    m += 1
                    c += 1
                    if first_divergence is None:
                        first_divergence = {
                            "event": e,
                            "reason": f"work_event_outside_active_session: {etype}"
                        }

        # Calculate remaining tokens at trace termination
        # Proper completion expects exactly 1 token in final_place and 0 elsewhere
        r = 0
        for pl, count in tokens.items():
            if pl == self.final_place:
                if count > 1:
                    r += (count - 1)
            else:
                r += count

        # If trace finished without reaching final_place, count deficit as missing completion
        if tokens[self.final_place] == 0:
            m += 1
            c += 1

        # Prevent division by zero
        c_eff = max(1, c)
        p_eff = max(1, p)

        fitness = 0.5 * (1.0 - (m / c_eff)) + 0.5 * (1.0 - (r / p_eff))
        fitness = max(0.0, min(1.0, fitness))

        compliant = fitness >= 0.95

        return {
            "fitness": round(fitness, 4),
            "compliant": compliant,
            "produced": p,
            "consumed": c,
            "missing": m,
            "remaining": r,
            "tokens_final": dict(tokens),
            "first_divergence": first_divergence,
            "fired_transitions": fired_transitions,
        }


# --------------------------------------------------------------------------
# stdlib conformance check
# --------------------------------------------------------------------------

def stdlib_check(
    events: list[dict],
    stages: list[dict],
    evidence_count: int = 0
) -> dict:
    """events: [{"type": "session_active", "ts": ...}, ...] for the day.
    Deviations are facts, not judgments (L-7): no softening phrases.
    """
    types = [e.get("type", "") for e in events]
    deviations = []

    for st in stages:
        for req in st.get("require", ()):
            if req not in types:
                deviations.append({
                    "kind": "missing_required",
                    "stage": st["name"],
                    "detail": req
                })
        for fb in st.get("forbid", ()):
            if ":" in fb:
                base, sub = fb.split(":", 1)
                hit = [
                    e for e in events
                    if e.get("type") == base and e.get("category") == sub
                ]
            else:
                hit = [e for e in events if e.get("type") == fb]
            for e in hit:
                deviations.append({
                    "kind": "forbidden_occurred",
                    "stage": st["name"],
                    "detail": fb,
                    "ts": e.get("ts")
                })

    exp_ev = expected_evidence_of(stages)
    if evidence_count < exp_ev and "session_active" in types:
        actual_ev = sum(
            1 for e in events
            if "evidence" in e.get("type", "") or "proof" in e.get("type", "")
        )
        if actual_ev < exp_ev:
            deviations.append({
                "kind": "evidence_shortfall",
                "stage": "session_active",
                "detail": f"{actual_ev} evidence events (expected >= {exp_ev})"
            })

    # Run Token-based Petri Net Replay
    petri_net = NormativePetriNet(stages)
    replay_res = petri_net.replay_trace(events)

    first_div = replay_res.get("first_divergence")
    if not first_div:
        for e in events:
            if str(e.get("type", "")).startswith(("guard_break", "break_")):
                first_div = {"event": e, "reason": e.get("type")}
                break

    conformant = (len(deviations) == 0) and replay_res["compliant"]

    return {
        "deviations": deviations,
        "first_divergence": first_div,
        "conformant": conformant,
        "token_replay": replay_res,
        "fitness": replay_res["fitness"],
        "protocol_violation": not replay_res["compliant"],
    }


def expected_evidence_of(stages: list[dict]) -> int:
    for st in stages:
        if st["name"] == "session_active":
            try:
                return int(str(st["note"]).split(">=")[1].strip())
            except Exception:
                return 1
    return 1


# --------------------------------------------------------------------------
# PM4Py path (Resolution of the Circularity Defect, §8.3)
# --------------------------------------------------------------------------

def pm4py_check(events: list[dict], stages: Optional[list[dict]] = None) -> Optional[dict]:
    """Token replay of the day's log against the normative model.

    Resolves the Circularity Defect (§8.3): replays against the pre-authored
    normative model rather than discovering a tautological process tree from the log itself.
    Returns honest availability status if pm4py is not installed.
    """
    try:
        import pm4py
        from pm4py.objects.petri_net.obj import PetriNet, Marking
        from pm4py.objects.petri_net.utils import petri_utils
        from pm4py.conformance import conformance_diagnostics_token_based_replay
        import pandas as pd
    except ImportError:
        # Fall back to pure-Python normative token replay engine
        net = NormativePetriNet(stages or build_normative({}))
        rep = net.replay_trace(events)
        return {
            "available": False,
            "engine": "native_normative_petri_net",
            "fitness": rep["fitness"],
            "compliant": rep["compliant"],
            "note": "pm4py not installed; native normative token replay engine used (honest)"
        }

    try:
        # Construct normative Petri Net in pm4py structures
        st = stages or build_normative({})
        pnet = PetriNet("normative_contract_net")
        im = Marking()
        fm = Marking()

        p_start = PetriNet.Place("p_start")
        p_sealed = PetriNet.Place("p_sealed")
        p_active = PetriNet.Place("p_active")
        p_evidence = PetriNet.Place("p_evidence")
        p_closed = PetriNet.Place("p_closed")

        for p in [p_start, p_sealed, p_active, p_evidence, p_closed]:
            pnet.places.add(p)

        im[p_start] = 1
        fm[p_closed] = 1

        t_seal = PetriNet.Transition("contract_sealed", "contract_sealed")
        t_active = PetriNet.Transition("session_active", "session_active")
        t_ev = PetriNet.Transition("evidence_submitted", "evidence_submitted")
        t_close = PetriNet.Transition("day_close", "day_close")

        for t in [t_seal, t_active, t_ev, t_close]:
            pnet.transitions.add(t)

        petri_utils.add_arc_from_to(p_start, t_seal, pnet)
        petri_utils.add_arc_from_to(t_seal, p_sealed, pnet)
        petri_utils.add_arc_from_to(p_sealed, t_active, pnet)
        petri_utils.add_arc_from_to(t_active, p_active, pnet)
        petri_utils.add_arc_from_to(p_active, t_ev, pnet)
        petri_utils.add_arc_from_to(t_ev, p_evidence, pnet)
        petri_utils.add_arc_from_to(p_evidence, t_close, pnet)
        petri_utils.add_arc_from_to(t_close, p_closed, pnet)

        df = pd.DataFrame([{
            "case:concept:name": "day_case",
            "concept:name": e.get("type", "unknown"),
            "time:timestamp": pd.to_datetime(e.get("ts") or datetime.utcnow())
        } for e in events])

        log = pm4py.format_dataframe(
            df,
            case_id='case:concept:name',
            activity_key='concept:name',
            timestamp_key='time:timestamp'
        )
        replay = conformance_diagnostics_token_based_replay(log, pnet, im, fm)
        fit = replay[0].get("trace_fitness", 0.0) if replay else 0.0

        return {
            "available": True,
            "engine": "pm4py_normative_token_replay",
            "fitness": round(fit, 4),
            "compliant": fit >= 0.95,
            "replay": replay,
            "note": "normative sealed contract replay (circularity defect resolved)"
        }
    except Exception as exc:
        return {"available": False, "note": f"pm4py replay failed: {exc}"}


# --------------------------------------------------------------------------
# Report block
# --------------------------------------------------------------------------

def render_conformance_md(result: dict) -> str:
    lines = ["## Conformance", ""]
    status_str = "PASS" if result.get("conformant") else "DEVIATIONS"
    lines.append(f"- conformance: {status_str}")
    if "fitness" in result:
        lines.append(f"- petri_net_fitness: {result.get('fitness')}")
        lines.append(f"- protocol_violation: {'YES' if result.get('protocol_violation') else 'NO'}")

    for d in result.get("deviations", []):
        ts = f" @ {d['ts']}" if d.get("ts") else ""
        lines.append(f"  - [{d['kind']}] {d['stage']}: {d['detail']}{ts}")

    fd = result.get("first_divergence")
    if fd:
        ev = fd.get("event", {})
        ev_type = ev.get("type") or fd.get("reason", "divergence")
        ts = ev.get("ts", "")
        lines.append(f"- first divergence: {ev_type}{f' @ {ts}' if ts else ''}")

    rep = result.get("token_replay", {})
    if rep:
        lines.append(f"- token_inventory: produced={rep.get('p', rep.get('produced'))}, "
                     f"consumed={rep.get('c', rep.get('consumed'))}, "
                     f"missing={rep.get('m', rep.get('missing'))}, "
                     f"remaining={rep.get('r', rep.get('remaining'))}")

    pm = result.get("pm4py")
    if pm:
        lines.append(f"- pm4py: {'replayed' if pm.get('available') else pm.get('note')}")
    return "\n".join(lines)
