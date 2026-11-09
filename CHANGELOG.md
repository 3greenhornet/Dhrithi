# Changelog

Every version below is reproducible: the repository carries the full
test suite, and each release line states the decision-register rows
(`docs/DECISIONS_PROPOSED.md`) it implements. Formats follow the
project's own rules — facts and dates, no spin.

## v0.3.0 — 2026-11-03 — the behavioral-reference batch

**The question this release answers:** *"did you consider the
procrastination attempt as a behavioral reference for understanding
the user's behaviours?"* The v0.2.1 re-audit answered it honestly
(yes structurally, no behaviorally) and proposed D-046..D-052. This
release implements all seven rows — the specimen's own vocabulary,
mechanisms and laws — while keeping every scope-widening switch
default-OFF (law L-6: cold-state consent).

### Added — mechanisms (Specimen 001, in the subject's words)

- **D-046 — the stage ratio.** His own metric ("i too am a audience
  for 90% of time"), computed deterministically: audience share of
  observed navigation, whole-day, printed in the aftermath next to his
  endorsed band (20–30% audience). Counts, not minutes; no verdict —
  the reader computes the distance (law L-2). New module
  `dhriti/stage_ratio.py`; aftermath "Stage ratio" block; digest
  stage-ratio line; standalone per-day measure in `analysis/measures.py`.
- **D-047 — declared leisure.** `dhriti declare leisure --activity
  "..." --minutes 45`: one-way, typed, bounded (1..240), session-free.
  A label, never a permission — it unblocks nothing. The aftermath
  shows **declared rest** next to **drift** (undeclared consumption)
  side by side; the cold review gains a conditional seventh question
  (`leisure_honored`), asked only when a declaration exists for the
  day. New module `dhriti/leisure.py`, new `leisure_declaration`
  table, new `leisure_declared` ledger event.
- **D-048 — evening observation (default OFF).** Enforcement ends at
  `window_end` and always will; observation previously ended with it —
  the evening hole is where and when the founding specimen happened.
  With `observation_evening.enabled` (a cold-state consent under the
  `surveillance_comfort` question), category observation continues to
  `day_end` (config `observation_evening.day_end`, default 23:59):
  observation adapters keep polling, an `evening_observation_active`
  marker is recorded once per day, and the aftermath's consumption
  facts now cover the **whole local day** with a window/evening split.
  Counts only (D-014 absolute).
- **D-049 — the earned evening (default OFF).** The specimen's own
  protocol, generalized from the builder clause: "no video, no
  explanation, no philosophical question to an AI, until one practice
  problem is compiled or 25 minutes are spent coding." With
  `earned_evening.enabled`, on a closed day whose targets were NOT
  met, the configured consumption categories stay blocked after
  `window_end` **until day_end** — bounded, never indefinite (D-018).
  Days that met their targets release to an open evening: consumption
  is earned by evidence, not by the clock. The bridge serves the
  earned-evening policy (contract line only, per the Wall Principle),
  `earned_evening_applied` is logged once per day, and break-glass
  remains the honest exit.

### Added — laws (docs/DESIGN_LAWS.md, new)

- **L-2 shame-safety (D-052)** — the whole law, not the partial
  convention: no generated praise, no shame, no comparative framing
  (streaks/percentiles/ranks), errors are first-class proof, identity
  lines are the user's own words only.
- **L-3 configuration immutability (D-050)** — config/profile edits
  are cold-state acts. The daemon fingerprints what it loaded;
  a config/profile file that changes on disk **while it runs** is
  recorded as `config_drift_detected` (telemetry DEGRADED) and is
  never hot-loaded. The fingerprint ships in `daemon_started`.
- L-1 (Wall Principle), L-4 (structure-aware, content-blind),
  L-5 (bounded release), L-6 (cold-state consent for scope changes)
  are stated alongside, each naming its test.

### Added — tests (82 → 116, all green)

- `tests/test_stage_ratio.py` — classification, band math,
  whole-day window/evening split, MISSING ≠ on-stage, drift split,
  aftermath + digest blocks.
- `tests/test_leisure.py` — declaration validation and bounds,
  label-not-permission event wording, note never enters the chain,
  aftermath declared-rest-vs-drift block, conditional question.
- `tests/test_earned_evening.py` — default-off, unmet-targets
  blocking (google.com stays reachable, contract line only,
  bounded `expires_at`), once-per-day event, met-targets earn an
  open evening, day_end ceiling, evening observation markers and
  whole-day facts.
- `tests/test_design_laws.py` — the laws' teeth: every extension
  surface and generated report is linted against the forbidden
  praise/shame/comparison phrase list; the wall page may not contain
  links, buttons, or forms; no `chrome.notifications`; config drift
  recorded once, never applied.

### Changed

- `dhriti/aftermath.py` — consumption facts cover the whole local day
  (session-scoped → day-scoped query) with the where-split; two new
  blocks (stage ratio, declared rest vs drift) in MD and HTML.
- `dhriti/review.py` — `build_digest` gains `config` (timezone-correct
  day bounds) and two new sections: stage ratio + top consumption
  categories (D-051), declared rest vs drift; `REVIEW_QUESTIONS` gains
  the conditional `leisure_honored`.
- `dhriti/daemon.py` — earned-evening policy provider; evening
  observation (adapter polling + marker + disarm exception); config
  fingerprint and drift check; `evening` block in the published
  status.
- `dhriti/cli.py` — `declare leisure` subcommand; the review asks the
  seventh question only when it applies; digest passes config.
- `dhriti/constants.py` — new config groups `stage_ratio`,
  `observation_evening`, `earned_evening` (the latter two default
  OFF; enabling each is a cold-state act).
- `dhriti/db.py` — new `leisure_declaration` table + index (additive;
  existing databases migrate in place).
- `analysis/measures.py` — stage-ratio-by-day table and summary
  fields (standalone, no package import, canonical copy noted).
- `examples/demo/run_demo.py` — the simulated day now includes a
  declared rest window, one in-window rest navigation and one evening
  drift navigation, so the shipped demo exercises the new blocks.
- `dhriti/__init__.py`, `pyproject.toml`, `extension/manifest.json` —
  version 0.3.0.

### Deliberately unchanged

- D-048/D-049 stay **default OFF** — enabling either is the builder's
  cold-state act (law L-6). The session that built them does not get
  to switch them on.
- No in-session semantics, no classifier, no content reading, no
  notifications, no streaks (D-014, L-1, L-2, L-4 — unchanged and
  now law).
- The six fixed review questions are not reworded; the seventh is
  strictly conditional.

## v0.2.1 — 2026-11-03 — the procrastination attempt, re-audited

Correction batch from the full re-audit of Specimen 001 (question:
*"did you consider the procrastination attempt as a reference for
understanding the subject's behavior?"*). Nine findings; the record
corrected, two mechanisms shipped, seven decisions proposed.

### Fixed — errors of fact

- **M-01/D-044 — the platform was misidentified.** The specimen is a
  Google **AI Mode** conversation (`google.com`, `udm=50`), not a
  ChatGPT export. That surface had no suppression rule (the rules
  targeted chatgpt.com/claude.ai/gemini while the founding surface
  ran free) and can never be category-blocked (blocking google.com
  blocks search). `extension/suppress.js` now scopes AI Mode by URL
  parameter (`isAIMode()`, `activeRules()`, `AIMODE_RULES`:
  `aimode-followups`, `aimode-related-qs`), suppressing the
  springboard surfaces, never the chat itself, never the entry link.
  Selectors are honestly marked day-one candidates under the
  stale-selector convention.
- **M-09 — the second capture is a duplicate.** `transcript.txt` is
  the same conversation as `procrastination attempt1.pdf` (122,769 vs
  122,770 chars, 100% mutual anchor coverage, 612 anchors). The
  specimen findings file now records this — history preserved, errors
  named — and the coder's rule: diff captures, file as one specimen.

### Added

- **M-02/D-045 — the behavioral pattern taxonomy** the subject
  requested twice inside the specimen and never received:
  `analysis/labels/BEHAVIORAL_PATTERNS.md`, P-01..P-10 in his own
  wording, the engine (P-10 drives P-01/P-07), and the rules of use:
  named cold only, never predictive, self-application is evidence,
  one taxonomy no forks.
- `docs/DECISIONS_PROPOSED.md` — rows D-044..D-052 in the register's
  own format; D-046..D-052 proposed (implemented in v0.3.0 above).

### Files touched

`extension/suppress.js`, `analysis/labels/BEHAVIORAL_PATTERNS.md`
(new), `analysis/specimens/SPECIMEN_001/SPECIMEN_001_FINDINGS.md`
(correction section appended), `docs/DECISIONS_PROPOSED.md`. Python
suite unchanged: 82 tests, all green.

## v0.2.0 — 2026-11-03 — plan v2.0 + Specimen 001 docked

The build that docked the implementation plan v2.0 (decisions
D-001..D-031) and the raw avoidance-loop transcript (Specimen 001).
Tests 62 → 82.

### Added

- **Surface suppression D-024 (G-02/G-03/G-17)** — `extension/
  suppress.js`: YouTube feed/Shorts/related/endscreen, Reddit feed,
  X timeline/who-to-follow/trending, Google related/people-also-ask,
  AI-chat follow-up suggestions; `surface_suppressed` events; blocked
  tabs closed at arming (`blocked_tabs_closed`).
- **The mail slot D-033 (G-08)** — `dhriti park`, parking-lot table,
  cold dispositions.
- **The mirror's questions D-030/D-031/D-037 (G-05/G-06/G-07)** —
  main-belief contract group (validated as a unit), the exchange
  block in the aftermath, the six-question cold review.
- **The emergency path D-019/D-036 (G-09)** —
  `break-glass --emergency`: immediate, typed, its own event, no
  cooldown, distinct in reports.
- **The dead man's switch D-034 (G-10)** — `dhriti digest`: weekly
  facts + chain head; absence is the signal (minimal E4).
- **The builder clause D-035 (G-11)** — R-001 made mechanical,
  default OFF; `builder_clause_applied`; `avoidance_metabolized`
  failure code.
- **Correctness G-01 (R-007)** — journal mode DELETE on Windows,
  stale WAL/SHM quarantined (`*.corrupt-<ts>`), never deleted.
- Twelve new event types (four from the specimen), the specimen coder
  (`code_specimen.py`) + Specimen 001 coded with findings, process
  docs (`VERSION_PINS`, `DAY_ONE_CHECKLIST`, `FAILURE_TAXONOMY`,
  `DECISIONS_PROPOSED`), decisions D-032..D-043.

## v0.1.0 — 2026-11-02 — Lite tier baseline

First build from the dossier: contracts, day window, state machine,
sessions, evidence model (errors-as-proof), break-glass with toll and
cooldown, hash-chained ledger with anchors, bootcamp + evidence-based
taper, MV3 extension wall, adapter registry (ActivityWatch/Sysmon/
Screenpipe observation; external-blocker placeholders behind the
D-005/D-006 audit gate), research passes, launcher, TLA+ spec, N-of-1
measures, 62 tests.
