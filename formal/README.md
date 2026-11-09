# Formal specification (dossier 5.6 / audit item 10)

`DhritiLifecycle.tla` models the session/day state machine exactly as
implemented in `dhriti/models.py` + `dhriti/state_machine.py`, plus the
three industrial-interlock behaviours the dossier borrows:

- **arming gate** — no ACTIVE without a sealed policy and a successful
  arm (`NoActiveWithoutSealed`),
- **emergency path** — break-glass reachable from every ACTIVE state
  (`EmergencyAlwaysPossible`), the "maintenance bypass" of the
  industrial interlock pattern,
- **delayed relaxation** — loosening a policy never applies on the
  same step it is requested (`RelaxationIsDelayed`), the trapped-key /
  delayed-access pattern from Plucky,
- **bounded day release** — `DayReleaseIsBounded`, the D-018
  resolution.

## Running the model checker (manual step)

TLA+ model checking is development-time only. You need Java 8+:

```
# download once:
#   https://github.com/tlaplus/tlaplus/releases  (tla2tools.jar)
java -cp tla2tools.jar tlc2.TLC DhritiLifecycle.tla
```

Expected result: no invariant violations across the finite state space.
If TLC reports a violation, the Python state machine is wrong, not the
spec — fix `dhriti/state_machine.py` first, then re-run both.

The same invariants are covered behaviorally by `tests/` (62 unittest
cases), so the Python side is protected even before you run TLC.
