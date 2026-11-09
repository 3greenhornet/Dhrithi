# START HERE

You asked for: the project built from your resources, fail-proof,
with well-made placeholders wherever something needs manual
download/integration. This is that build. Read this page, then you
are oriented.

## v0.4 — the stabilization and operator batch (one screen)

Phase 0 closed the eight bugs found in the base audit; the
operator QoL toolkit arrived (health, explain, backup,
journal, config, pre-commit lint, surface lint, golden-day
fixture, CI matrix). The base is now observable before
anything is added to it.

## v0.3 — the behavioral-reference batch (one screen)

You asked whether the procrastination attempt had been considered as
a behavioral reference. The honest answer was: structurally yes,
behaviorally no — so the specimen's own vocabulary became the
mechanisms (decisions D-046..D-052, all implemented, all tested):

1. **The stage ratio (D-046)** — your own metric ("audience for 90%
of time" vs. the 20–30% audience band you endorsed), computed daily
   from observed navigation, in the aftermath and the digest. Counts,
   not minutes; the number sits next to your band — you read the
   distance, the software never scores it.
2. **Declared leisure (D-047)** — `dhriti declare leisure --activity
   "..." --minutes 45`. Chosen rest is honest; undeclared drift is
   avoidance. The aftermath shows the two side by side; the review
   asks whether the declaration held (only when one exists).
3. **Evening observation (D-048, OFF by default)** — the evening hole
   (where the founding specimen actually happened) becomes measured:
   enable `observation_evening` cold and category observation runs to
   day_end. Counts only, no content, ever.
4. **The earned evening (D-049, OFF by default)** — your own protocol,
   generalized: on target-missed days the consumption categories stay
   blocked until day_end. Meet the day's targets and the evening is
   open — consumption earned by evidence, not by the clock.
5. **The laws (D-050/D-052)** — `docs/DESIGN_LAWS.md`: shame-safety
   (no praise, no shame, no streaks, errors are proof) and
   configuration immutability (no hot reload; on-disk drift is
   recorded). Both are enforced by `tests/test_design_laws.py`, which
   lints every surface.

Tests: 82 → 116, all green. The demo day now ends with a declared
rest and a drift navigation so you can see both blocks in a real
report (`examples/demo/run_demo.py`).

**The two evening switches are yours to flip, cold** — enabling either
is a config edit before the next daemon start (law L-6), not a
session's decision.

## v0.2 — what the 2026-11-03 material changed (one screen)

Your implementation plan v2.0 and the raw transcript (Specimen 001)
docked cleanly. The changes, in one list:

1. **Specimen 001 is the project's first data artifact** — coded in
   `analysis/specimens/`, findings in
   `SPECIMEN_001_FINDINGS.md`. The transcript is where Dhriti was
   conceived (turn 42: "a serious, rigid… one"); it is now also its
   first baseline. 52 turns, 100% of AI turns ended with a
   next-interaction affordance (even the refusals), 0 evidence
   events.
2. **Surface suppression (D-024)** — the extension now removes the
   springboard itself: YouTube feed/Shorts/related, Reddit/X feeds,
   Google related/also-ask, and AI-chat follow-up suggestions. The
   domain stays allowed; the slot-machine surface is gone.
3. **The wall got a mail slot** — `dhriti park "question"` parks a
   curiosity in one line; dispositions happen cold.
4. **The mirror got its questions** — `dhriti review` asks the six
   fixed questions (D-031 competence source, the graduation
   wall-or-choice metric, devices, evidence quality, capture
   comfort, faking-it).
5. **Contracts carry the main belief** (D-030: belief, metric,
   current state, substitutes, budget — validated as a unit) plus
   the IF–THEN obstacle plan and the emergency policy.
6. **Emergency path (D-019)** — `dhriti break-glass --emergency`:
   immediate, typed, its own event, no cooldown.
7. **Weekly digest** — `dhriti digest`: facts + chain head, meant
   for the one human who cares. Absence of the digest is the signal
   (minimal E4).
8. **Journal mode fixed per your R-007** — DELETE on Windows, stale
   WAL/SHM quarantined, never silently trusted.
9. **Builder clause (R-001, mechanical, OFF by default)** — while
   the day's targets are unmet, the Dhriti repo domains can be
   blocked. Building the tool is earned. See
   `builder_clause` in config + `docs/DECISIONS_PROPOSED.md`.
10. **Process docs** — `docs/VERSION_PINS.md`,
    `integrations/DAY_ONE_CHECKLIST.md`, `docs/FAILURE_TAXONOMY.md`,
    `docs/DECISIONS_PROPOSED.md` (D-032…D-043 proposed in your
    register format).

Tests: 62 → 82, all green. The simulated demo day runs end-to-end
on the new schema.

## 60-second orientation (still true)

1. **What works out of the box:** the entire core (ritual → day
   window → sessions → proof → break-glass → aftermath → bootcamp
   taper), the hash-chained ledger, the browser extension, the
   behavioral-reference batch (stage ratio, declared leisure, the
   laws), and the analysis tooling. Zero pip dependencies. Verified by
   116 tests + a fully simulated demo day (`examples/demo/`).
2. **What needs you (each has a guide, nothing is a silent stub):**

| Manual step | Guide | Then |
|---|---|---|
| Load the browser extension + paste token | `extension/INSTALL.md` | E1 wall is live |
| (optional) Apply hosts DNS block | `integrations/windows/hosts-block.ps1` | E2 active |
| (optional) Install ActivityWatch | `integrations/activitywatch/SETUP.md` | observation on |
| (optional) Sysmon narrow profile | `integrations/sysmon/SETUP.md` | process provenance |
| (after your audits) External blockers | `integrations/enforcement-audit/` | adapters armable |
| (optional) TLC model check | `formal/README.md` | invariants proven |
| (optional) PM4Py | `analysis/pm4py_poc.py` header | real process mining |
| (much later) Vision proof | `integrations/vision-proof/SETUP.md` | stays disabled until then |

3. **Your materials are preserved** unchanged in `source-material/`,
   and every single item from them is mapped in
   `docs/TRACEABILITY.md` — including the deliberate exclusions.

## Where your contradictions went

`docs/RESOLUTIONS.md` — eleven rows (the eight your dossier flagged,
plus three I added). Each names the module that implements it and the
veto procedure. Change any row; the code follows.

## First real day

```
python3 -m dhriti.cli init
python3 -m dhriti.cli bootcamp start --days 30
python3 -m dhriti.cli ritual          # cold, tonight or before 10:00
python3 -m dhriti.cli daemon          # from 10:00 the wall is up
```

Windows users: `py -m dhriti.cli …` and `pip install tzdata` once.

## When your refined material arrives

`docs/REFINEMENT.md` is the docking procedure — derived-from-what
table, update order, and the open items waiting on you (D-003
verbatim export — **partially closed by Specimen 001**, more wanted;
Focuser audit; day-window veto, …). The 2026-11-03 material docked
through it; see `docs/DECISIONS_PROPOSED.md` for the full record.
