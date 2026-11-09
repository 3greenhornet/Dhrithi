# TRACEABILITY — every input item, where it went

The promise: **nothing from your materials is missed.** If a row says
"documented only", that is a deliberate decision, not an omission —
your own decision register asked for it (D-005: audit before adopt).

## 1. Original PDF (PROJECT DHRITHI_ORIGINAL.pdf)

| PDF section | Content | Where it lives |
|---|---|---|
| 1.1–1.10 | Origin story, Born Sexy Yesterday, nice-guy pattern, media's cheated script, proxy progression, audience vs stage, avoidance loop, ten patterns, behavioral addiction, brain limits | Philosophy distilled into `README.md` (Why) + enforcement targets; the ten patterns are what the loop log + aftermath make visible; no code needed — this is the "why" layer |
| 2.1–2.2 | Name, meaning, product definition, target population | `dhriti/__init__.py` docstring, README |
| 2.3 | Six founding principles | `constants.PRINCIPLES`; each mapped below |
| 2.4–2.5 | Wall Principle | `extension/` (no responses), `policy.extension_rules` (no reason strings), CLI copy discipline, `blocked.html` (own contract only) |
| 2.6 | What Dhriti is not | README "What this is not" |
| 3.1–3.9 | Day-window model, corrections, escape hatches, three resolutions, day-close, easy-contract loophole, honest residual | `day_window.py` + `daemon.py`; RESOLUTIONS R1, R2, R10; all §3.4 escape hatches tested in `tests/test_daemon_integration.py` |
| 4 | Intent Lock starter audit + comparison table | `extension/` is the successor; comparison preserved in `extension/INSTALL.md` lineage note |
| 5.1–5.7 | Cold-state ritual, contract fields, hierarchy, identity anchor, sealed contract, tamper-evident | `contract.py`, `cli.py ritual`, DB triggers (`db.py`), RESOLUTIONS R9 |
| 6.1–6.4 | Proof-of-work, vision workflow, no universal counter, per-task progress | `evidence.py` (3 classes), `integrations/vision-proof/`, RESOLUTIONS R7 |
| 7 | Break-glass + costs + what it is not | `break_glass.py` (60s delay, typed reason, cooldown, declared penalties) |
| 8.1–8.3 | Aftermath, loop log vs aftermath, cold review | `aftermath.py` (facts vs interpretation, identity line), `ledger.py`, `dhriti report --scope week` |
| 9 | Bootcamp, 30-day rules, taper, graduation | `bootcamp.py`, RESOLUTIONS R6 |

Six principles → mechanisms:

1. Commitment precedes temptation → contracts seal only in cold state;
   policy snapshot frozen at session seal (`policy.build_snapshot`)
2. No in-the-moment negotiation → binary session states; no pause
   state exists in `state_machine.py`
3. Discomfort anticipated → no comfort features anywhere; the toll
   exists (break-glass) but costs
4. Execution outranks analysis → evidence required to end SUCCESS;
   manual claims rejected as proof
5. Visible consequences → hash-chained ledger, aftermath report,
   anchors
6. Sustained enforcement → bootcamp container; taper only from
   evidence

## 2. Master Dossier (DHRITI_MASTER_DOSSIER.md)

| Dossier section | Where it lives |
|---|---|
| 1 intent/constraints | README, config defaults |
| 2.1 strengths | all preserved (see rows below) |
| 2.2 contradiction table | `docs/RESOLUTIONS.md` R1–R8 (one per row) |
| 2.3 corrected recommendations | honored: Focuser/FocusMe/Plucky/SEB/ActivityWatch etc. are all audit-gated placeholders, none adopted from READMEs |
| 3.1 capability table | `dhriti/adapters/` — every capability from the table has an adapter or a documented lead |
| 3.2 architectural separation | stable core (`dhriti/`) vs replaceable adapters (`adapters/`) vs offline layer (`analysis/`) |
| 3.3 E1–E4 | `docs/ENFORCEMENT_LEVELS.md`, `models.EnforcementLevel` |
| 3.4 work states + ARMING gate | `state_machine.py`, `models.ActivityClass`, arming gate in `adapters/base.py` |
| 3.5 closed/bounded/open modes | `models.WorkMode`, `policy.py` |
| 4 inversion catalogue | catalog preserved in spirit across integrations: interlocks→TLA+ + arming gate; Sysmon→observer; PM4Py→`analysis/`; SEB→`integrations/windows/assigned-access.md`; Plucky delay→TLA+ `RelaxationIsDelayed`; JITAI→`experiments/`; Beeminder/Focusmate→documented leads (below) |
| 5 audits | `integrations/enforcement-audit/` maps your Manual Audit Queue; every tool from §5 has a config slot + setup guide or an explicit "lead only" note |
| 6 initiation/profiles/dependency/finite research | `launcher/`, `profiles.py`, `research_pass.py` |
| 7 event schema/provenance/offline | `ledger.py` implements the exact schema; `analysis/` is the offline pipeline |
| 8 model strategy + control engineering | no LLM in enforcement (D-014 honored); hysteresis/cooldown in break-glass + research expiry; `analysis/labels/` for the labeling-first rule; unvalidated 0.40/0.65/0.60 thresholds NOT implemented |
| 9 research snapshot | `docs/RESEARCH_BASE.md` (citations carried over verbatim) |
| 10 experiment design | `experiments/protocol.md` + `conditions.json` + `analysis/measures.py` |
| 11 tiers + capability manifests | `configs/tiers/`, `Adapter.manifest()` |

## 3. Decision register (D-001 … D-023)

| ID | Status in this build |
|---|---|
| D-001 personal purpose | README: experiment, no marketing claims |
| D-002 source preservation | `source-material/` byte-identical copies |
| D-003 verbatim chat | **OPEN** — place your ChatGPT export in `source-material/` |
| D-004 mechanism search | integrations organized by capability, not product |
| D-005 no blocker from scratch | E1 is ours; E2/E3 external = audit-gated placeholders |
| D-006 Focuser | placeholder adapter, disabled pending audit |
| D-007 Plucky | placeholder adapter, black-box only |
| D-008 SEB | documented as E3 pattern (`assigned-access.md` + audit queue) |
| D-009 observation | ActivityWatch = the one light observer; sysmon/screenpipe opt-in |
| D-010 PM4Py | `analysis/sequence.py` (pure) + `pm4py_poc.py` (optional install) |
| D-011 Screenpipe | placeholder, trial-first discipline in SETUP |
| D-012 workspace launcher | `launcher/ignite.ps1` + profiles |
| D-013 task profiles + dependency graphs | `profiles.py`, `research_pass.py` |
| D-014 no LLM in enforcement | zero model calls in the enforcement path; vision = disabled placeholder |
| D-015 data capture local | everything local; raw data out of Git (`.gitignore`) |
| D-016 no accidental upload | core makes zero network calls; only loopback bridge |
| D-017 evidence classes | `models.EvidenceClass`, `evidence.py` |
| D-018 day release contradiction | RESOLUTIONS R1 |
| D-019 emergency path | break-glass always reachable (TLA+ invariant `EmergencyAlwaysPossible`) |
| D-020 formal verification | `formal/DhritiLifecycle.tla` + tests |
| D-021 hardware modularity | tier configs + capability manifests |
| D-022 experiment separation | `experiments/` three-question protocol |
| D-023 narrow first build | this build IS the narrow build: core + E1 + placeholders |

## 4. Manual Audit Queue → integrations

| Queue item | Integration |
|---|---|
| A1 Focuser audit | `enforcement-audit/README.md` (adapter slot) |
| A2 FocusMe vs Cold Turkey | adapter slots + result template |
| A3 Plucky | adapter slot + result template |
| A4 Safe Exam Browser | E3 pattern doc + result template |
| B5 observation comparison | `activitywatch/SETUP.md`, `sysmon/SETUP.md` |
| B6 Sysmon | narrow config shipped |
| B7 Screenpipe | trial-first placeholder |
| C8 PM4Py PoC | `analysis/` (done, pure-Python + optional real PM4Py) |
| C9 semantic models | `analysis/labels/LABELING_GUIDE.md` (labels before models) |
| D10 TLA+ | `formal/` (spec written; TLC run is your manual step) |
| D11 JITAI | `experiments/protocol.md` |
| D12 browser interface inversions | Purpose Mode/Unhook documented as leads in `docs/RESEARCH_BASE.md` |

## 5. Source register (45 leads)

All 45 rows preserved in `source-material/DHRITI_SOURCE_REGISTER.csv`.
Rows that became code/adapters: 5 (Purpose Mode→lead), 6 (Focuser),
7 (Plucky), 8–9 (SEB), 10–12 (commercial), 18 (ActivityWatch), 19–21
(Sysmon/Screenpipe), 23 (WXT — deliberately not used in v1: plain MV3,
no build step), 29–30 (Portmaster→E2 lead), 33 (PM4Py), 34 (TLA+), 36
(HeartSteps→methodology only), 38–39 (Beeminder/Focusmate→optional
leads), 41–43 (embedding models→labeling-first rule blocks them for
now). Rows 14–17 (Windows policies) → `integrations/windows/`.

## Known deliberate exclusions (not missed — decided)

- **Mobile (Nudge, AddictionBuster):** register rows 27–28; E-tier
  mobile enforcement is out of scope for the Lite tier; revisit when
  phone diversion shows up in your data.
- **Router/OpenWrt:** documented lead only (row 31); do not buy
  hardware before the need is proven (dossier 5.5).
- **WXT framework:** plain MV3 chosen for v1 (no build step, nothing
  to install); WXT remains the adapter-framework candidate later
  (dossier 5.3 says don't rewrite for fashion).
- **OPA:** dossier 5.6 says investigate only when complexity requires;
  the policy engine is 200 lines of deterministic Python — OPA would
  be runtime weight.

## 2026-11-03 docking — implementation plan v2.0 + Specimen 001

New source material (plan v2.0, four parts + embedded gap research;
Specimen 001 raw transcript). Full decision-level record:
`docs/DECISIONS_PROPOSED.md`.

| Material item | Where it lives |
|---|---|
| D-024 surface suppression (feeds, autoplay, related, AI-chat follow-ups) | `extension/suppress.js` + `surface_suppressed`/`blocked_tabs_closed` events + `suppress_surfaces` policy flag |
| D-025 bridge hardening (client observation, anomaly) | `bridge_token_rejected` rate-limited event; `dhriti token rotate` (cold-state rotation; per-session rotation deferred to Tauri build — documented limit) |
| D-029/D-031 competence substitution | aftermath exchange block + `dhriti review` questions `competence_source`, `faking_it` |
| D-030 main-belief contract group | `contract.py` (required, unit-validated) + ritual prompts + demo/tests |
| D-019 emergency path | `break_glass.emergency()` + `emergency_exception` event, distinct from the toll |
| Plan §4.10/R-007 journal mode | `db.resolve_journal_mode` (DELETE on Windows), `_open_with_recovery` (quarantine stale WAL/SHM) |
| Plan "under-utilized mechanisms" table (parking lot, declared thinking, research ratio, surveillance comfort, evidence quality) | parking lot wired (`dhriti park`), surveillance comfort + evidence quality in `dhriti review`, research passes already wired (v0.1), declared-thinking deferred (needs the classifier era — no UNKNOWN enforcement exists to neutralize in Lite) |
| Plan "graduation meta-metric" ("wall or choice?") | review question `wall_or_choice`; answer pattern feeds taper review |
| Plan process gaps (setup checklist, failure taxonomy, version pins) | `integrations/DAY_ONE_CHECKLIST.md`, `docs/FAILURE_TAXONOMY.md`, `docs/VERSION_PINS.md` |
| Plan appendix research (Cold Turkey CLI thinness, watchdog, fastembed fragility, HVCI bypass, pm4py-mcp) | recorded in `docs/DECISIONS_PROPOSED.md` NOT-DONE/deferred list + `VERSION_PINS.md` + FAILURE_MODES remains the runtime-side ledger; the bake-off items stay audit-gated (D-005/D-006) |
| Specimen 001 (the transcript) | `analysis/specimens/` — coded events, summary, findings; `ai_suggestion_offered`/`ai_affordance_tail` vocabulary addition; builder clause (R-001) + digest (minimal E4) as its direct product |
| 12 recognition edge-case mechanisms (plan Part 4 §1.7) | implemented subset: #1 dependency declaration, #6 essential-tool declaration, #7 unreliable-evidence mark, #8 blocked-tab closure, #11 surveillance comfort review, #12 evidence quality review; #3/#4/#5/#9/#10 belong to the classifier/watchdog era (Phase 5+ of the plan) and are documented as deferred |

Deliberately NOT docked: the Rust/Tauri rewrite (the plan's Phase 5
target stack stays a future decision — the Python core is the Lite
tier and the plan's own D-023 keeps it first), per-session token
rotation, in-session semantic anything (D-014), and the Chrome
version floor (record-only; we never treat browser policy as the sole
barrier).
