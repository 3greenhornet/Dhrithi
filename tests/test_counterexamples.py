"""Dhriti Guard Kit -- counterexample replay (D-089).

Closes the golden-path-only gap the repo's own audit named (Note-2:
the golden-day fixture only exercises the golden path) for the guard
subsystem, using the discipline of the repo's TLA+ work (D-020).

fixtures/tla_counterexamples.json holds traces, each with a stated
invariant and an attack story written from the user's side ("what I
would try"). The runner is generic: steps call a small registry of
guard primitives; asserts check one state field each. A failing trace
means a guard bug; a passing trace re-proves the invariant against
that specific attack.

Scope honesty: these are guard-LOCAL invariants. The lifecycle
invariants (NoActiveWithoutSealed, EmergencyAlwaysPossible,
RelaxationIsDelayed, DayReleaseIsBounded, InterruptedRecovers) remain
the TLA+ artefacts in the repo. Real TLC counterexample output can be
hand-translated into steps+asserts here -- the format is deliberately
the same shape.
"""

from __future__ import annotations

import json
import os
import unittest

try:
    from dhriti import chat_guard as cg
except ImportError:  # pragma: no cover
    import chat_guard as cg  # type: ignore

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "fixtures", "tla_counterexamples.json")


class Replay:
    """One trace's execution context. The registry is intentionally tiny:
    if a needed primitive is missing, the trace FAILS LOUDLY -- never a
    silently skipped step."""

    def __init__(self):
        self.state = None
        self.now = 1000.0
        self.last_reason = None

    # -- steps -------------------------------------------------------------
    def fresh_state(self, args):
        mode = cg.GuardMode(args.get("mode", "checkpoint"))
        self.state = cg.GuardState(mode=mode)
        self.state.taper_index = args.get(
            "taper_index", cg.TAPER_LADDER.index(mode))
        self.state.topic_label = args.get("topic_label", "")
        if "prompt_budget_limit" in args:
            self.state.prompt_budget_limit = args["prompt_budget_limit"]
        self.now = 1000.0

    def clean_days(self, args):
        for _ in range(int(args.get("days", 1))):
            cg.schmitt_step(self.state, breach=False)

    def schmitt_step(self, args):
        cg.schmitt_step(self.state, breach=bool(args.get("breach")))

    def accrue_many(self, args):
        for _ in range(int(args.get("n", 1))):
            cg.accrue_debt(self.state)

    def open_thread(self, args):
        ok, reason, _ = cg.open_thread(self.state, args["thread_id"],
                                       args["site"], self.now)
        if not ok:
            raise AssertionError(f"open_thread({args['thread_id']}) "
                                 f"refused: {reason}")

    def open_thread_expect_refused(self, args):
        ok, reason, _ = cg.open_thread(self.state, args["thread_id"],
                                       args["site"], self.now)
        if ok:
            raise AssertionError(
                f"invariant broken: open_thread({args['thread_id']}) "
                f"was ALLOWED (expected refusal {args['reason']})")
        if reason != args["reason"]:
            raise AssertionError(
                f"refused with {reason}, expected {args['reason']}")

    def dispose_thread(self, args):
        events = cg.dispose_thread(self.state, args["thread_id"],
                                   args["disposition"], self.now)
        if not events:
            raise AssertionError(f"dispose had no effect on "
                                 f"{args['thread_id']} (already disposed?)")

    def set_mode(self, args):
        self.state.mode = cg.GuardMode(args["mode"])

    def send_n(self, args):
        for i in range(int(args.get("n", 1))):
            d = cg.decide(self.state, self.now + i * 0.5, in_scope=True)
            if d.action != cg.GuardAction.SEND:
                raise AssertionError(
                    f"send_n step {i}: expected clean send, got "
                    f"{d.action.value} ({d.reason})")

    def decide_expect(self, args):
        verdict = args.get("sidecar_verdict")
        in_scope = args.get("in_scope")
        d = cg.decide(self.state, self.now, in_scope=in_scope,
                      sidecar_verdict=verdict)
        self.last_reason = d.reason
        expect_action = args["action"]
        if d.action.value != expect_action:
            raise AssertionError(
                f"invariant broken: decide -> {d.action.value} "
                f"(expected {expect_action}); reason={d.reason}")
        if "reason" in args and d.reason != args["reason"]:
            raise AssertionError(
                f"reason mismatch: {d.reason} (expected {args['reason']})")

    def wait_past_cooldown(self, args):
        self.now += self.state.burst.cooldown_s + 1.0

    # -- asserts -----------------------------------------------------------
    def assert_field(self, args):
        getters = {
            "taper_index": lambda s: s.taper_index,
            "clean_streak": lambda s: s.clean_streak,
            "debt_value": lambda s: s.debt.value,
            "debt_frozen": lambda s: s.mode in s.debt_cfg.freeze_under,
            "mode": lambda s: s.mode.value,
            "pivots_used_today": lambda s: s.pivots_used_today,
        }
        field = args["field"]
        if field not in getters:
            raise AssertionError(f"unknown field in assert: {field}")
        got = getters[field](self.state)
        op, want = args["op"], args["value"]
        ok = {"eq": got == want, "le": got <= want,
              "lt": got < want, "ge": got >= want}[op]
        if not ok:
            raise AssertionError(
                f"invariant broken: {field}={got!r} {op} {want!r}")


class TestCounterexamples(unittest.TestCase):
    """Every trace must PASS (the invariant survives the attack)."""

    @classmethod
    def setUpClass(cls):
        with open(FIXTURE, encoding="utf-8") as fh:
            cls.spec = json.load(fh)
        cls.invariants = cls.spec["invariants"]

    def test_fixture_has_attack_stories(self):
        for inv in self.invariants:
            self.assertTrue(inv.get("attack_story"),
                            f"{inv['id']} missing attack story -- an "
                            f"attack without a story is not adversarial")

    def test_all_traces_hold(self):
        failures = []
        for inv in self.invariants:
            rp = Replay()
            try:
                for step in inv["steps"]:
                    fn = getattr(rp, step["fn"], None)
                    self.assertIsNotNone(
                        fn, f"{inv['id']}: unknown step {step['fn']}")
                    fn(step.get("args", {}))
            except AssertionError as exc:
                failures.append(f"{inv['id']} {inv['name']}: {exc}")
        self.assertEqual(failures, [],
                         "counterexample traces BROKE the guard:\n" +
                         "\n".join(failures))

    def test_each_invariant_is_distinct(self):
        names = [i["name"] for i in self.invariants]
        self.assertEqual(len(names), len(set(names)),
                         "duplicate invariant names in fixture")


if __name__ == "__main__":
    unittest.main()
