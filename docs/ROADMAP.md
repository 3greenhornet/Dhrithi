# Roadmap

The implementation plan, phased. v0.7.0 (§4.22) restructures Phase 0
into 0a/0b — the bug-fix pass and the source-vs-docs audit are
different disciplines and were previously conflated under one "Phase
0" label. Each phase below states its checklist; the release
checklist (Part 5 §5.1 of the dossier) applies per phase.

## Phase 0a — the eight audit bugs (DONE, v0.4.0)

- [x] Bug 1: week report crash on evidence grouping
- [x] Bug 2: seven test files missing `import unittest`
- [x] Bug 3: `make_daemon` stale service handles
- [x] Bug 4: bootcamp `evidence_summary` counted all history
- [x] Bug 5: second concurrent ACTIVE session allowed
- [x] Bug 6: `surface_rule_stale` promised, never emitted
- [x] Bug 7: builder clause vs allowlist precedence
- [x] Bug 8: WAL-quarantine test passed trivially

Shipped as v0.4.0 ("the stabilization and operator batch"). Every
item above names its test in the v0.4.0 CHANGELOG entry.

## Phase 0b — the source-vs-docs audit (DONE, v0.7.0)

The "does the code match the docs" pass. Every divergence found goes
in `docs/DOCUMENTATION_LOG.md`; each is either fixed in the release
or recorded as a decision (`docs/DECISIONS_PROPOSED.md`).

- [x] Audit the v0.6.0 surface against the addendum spec (Parts 3/4)
- [x] Divergences named in DOCUMENTATION_LOG Part 7
- [x] Decisions recorded (D-073.. in DECISIONS_PROPOSED.md)

## Phase 1 — the restoration batch (DONE, v0.6.0)

- [x] Bugs A–D (health probe, identity_line, seal --date, workspace
      resolution)
- [x] D-030 group restored; the ten fixed review questions
- [x] Parking lot resurfacing; mechanisms 2/4/5/10

## Phase 2 — the mirror and the additions (DONE, v0.7.0)

- [x] Saved-content mirror (schema v6, one-per-day surfacing,
      recall-before-reveal, default off)
- [x] Life mirror, declared bounds, search-escape detector
- [x] Re-save, abandonment ritual, declared re-entry,
      progress-not-opened, count on the wall
- [x] Confrontation file; break-glass friction ladder; stack
      integration; Kael mechanisms; operator toolkit completion
- [x] Specimen 002 + conversation mining (--patterns)
- [x] Semantic topic-lock (L-9); FSRS shadow mode + gates

## Phase 3 — the rituals (DONE, v0.7.0)

- [x] Witness Protocol, One True Thing, Compost, Absence Test,
      Physical Register, Broken Contract Ceremony, 6-Month Letter,
      Voice Archive, 90-Day Archive, Quiet Hour, Debrief, Confession
- [x] Meta-Commitment (off by default), Wall Silence, Five Aftermath
      Views, Health Honesty Boundaries, Complexity Budget, Identity
      Revision, User-Probe Named Patterns, Dhriti Lite

## Phase 4 — running it (NEXT)

The honest next step (the velocity acknowledgment, Part 5 §5.5 of the
addendum): stop adding mechanisms; run the system for 30 days;
report what broke. The correct answer to "what's next" after v0.7.0
is "ask the operator to run it," not "here is v0.8.0."

- [ ] 30 days of real operation, digests generated weekly
- [ ] The failure modes that appear go in docs/FAILURE_MODES.md
- [ ] Gate 1/2/3 data accumulates (mirror, active learning, FSRS
      shadow) — gates open when the data justifies it, cold
