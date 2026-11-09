# DHRITI

**A local-first commitment-enforcement experiment.** An externalized
will for people who know exactly what they should do and cannot make
themselves do it. Not a coach. Not a therapist. Not a habit tracker.

> Dhriti (Sanskrit धृति — to hold, to bear, to sustain): the mental
> faculty that holds the line when an impulse tries to break it.

The consciousness writes the contract, cold. The tool enforces it,
silently. The mind obeys or breaks glass. That is the whole product.

---

## What this repository is

The v1 ("Lite tier") build of the design carried in
`source-material/` — the 95-page Project Dhriti knowledge dump, the
research dossier, the decision register, the source register and the
manual audit queue — **docked with the implementation plan v2.0 and
Specimen 001** (the raw avoidance-loop transcript of 2026-11-03; see
`analysis/specimens/`). Every item from those materials is either
**implemented here**, **a deliberate audit-gated placeholder**, or
**explicitly excluded with a reason** — the full mapping is
`docs/TRACEABILITY.md`, the v2.1 docking record is
`docs/DECISIONS_PROPOSED.md`.

| Piece | Status |
|---|---|
| Core (contracts, state machine, day-window, break-glass + emergency path, proof, ledger, bootcamp/taper, reports) | **implemented + 116 passing tests**, pure Python stdlib, zero dependencies |
| Cold-state surfaces (main-belief contracts D-030, parking lot, six-question review + conditional leisure question, weekly digest) | **implemented** — the mirror half of the system |
| The behavioral-reference batch (stage ratio D-046, declared leisure D-047, evening observation D-048 ‹off›, earned evening D-049 ‹off›, design laws L-1..L-6) | **implemented (v0.3.0)** — the specimen's own vocabulary |
| E1 enforcement (MV3 extension "Dhriti Wall": domain blocking + **surface suppression D-024 incl. Google AI Mode D-044** + tab closure at arming) | **implemented**; one manual step: paste the bridge token |
| E2 (hosts DNS block) | generator live; apply/remove = one admin PowerShell script |
| Observation (ActivityWatch / Sysmon / Screenpipe) | real clients + narrow config shipped; disabled until you install (guides included) |
| External backends (FocusMe, Cold Turkey, Plucky, Focuser) | config-driven placeholder adapters, refused until your audit passes (your rule, D-005/D-006) |
| Analysis (process mining, N-of-1 measures, labeling, **specimen coding**) | implemented in pure Python; PM4Py optional |
| Formal model (TLA+) | spec written; TLC run is your manual step |
| Vision-model proof | **disabled placeholder** — needs your API key; can never be the sole proof |

## Quick start

```bash
cd dhriti/

# 1. initialize a home (~/.dhriti by default; DHRITI_HOME overrides)
python3 -m dhriti.cli init

# 2. write today's contract — cold, before the window (interactive)
python3 -m dhriti.cli ritual

# 3. start the enforcement daemon (the wall's keeper, 10:00–21:00 IST by default)
python3 -m dhriti.cli daemon

# in another shell, inside the window:
python3 -m dhriti.cli session start --task "reverse the array" \
    --evidence-spec '[{"kind":"command"}]'
python3 -m dhriti.cli proof command --command "python3 reverse_array.py"
python3 -m dhriti.cli session end --outcome success

# evening, cold:
python3 -m dhriti.cli report            # aftermath: MD + HTML in ~/.dhriti/reports/
python3 -m dhriti.cli review            # the six questions (competence source, wall-or-choice, ...)
python3 -m dhriti.cli digest            # weekly facts + chain head -> send to your human
python3 -m dhriti.cli verify            # ledger hash chain check
```

Mid-session, when curiosity fires: `dhriti park "why does X"` — one
line, deferred to the cold review, back to work. When rest is
chosen, own it: `dhriti declare leisure --activity "one episode"
--minutes 45` — a label, not a permission; the aftermath shows
declared rest next to drift. When a real dependency appears:
`dhriti declare dependency --what "..."` then a bounded
`dhriti research start`. Emergency (D-019):
`dhriti break-glass --emergency --reason "..."` — immediate, typed,
logged as its own event.

The wall itself: load `extension/` unpacked in Chrome after pasting
the token — `extension/INSTALL.md`, one manual step.

**Windows note:** `pip install tzdata` once, so IST resolves correctly
(the core degrades to a fixed offset otherwise and records it).

## The day model in one paragraph

The bootcamp (30/60/90 days) is the container. Each day, between
10:00 and 21:00 local, the wall is up: you are on stage or offline,
never in the audience. The only requirement is that *something* is
written as the day's contract before the window starts — the software
does not judge the goal, it enforces the window. Finish early and the
day stays locked until day_close (20:00). Meet your targets and it
releases at day_close. Miss them and everything still releases at
21:00 — bounded, never indefinite. There is no pause, no snooze, no
"five more minutes". There are exactly three ways a session ends:
**success** (accepted proof), **incomplete** (no proof), or
**break-glass** (a 60-second toll, a typed reason, a cooldown, your
own declared penalty — recorded, never auto-executed).

## Principles and laws, enforced by code

The six founding principles (commitment precedes temptation; no
in-the-moment negotiation; discomfort is anticipated; execution
outranks analysis; commitments have visible consequences; enforcement
over a sustained period) are stated in `constants.PRINCIPLES`. Since
v0.3 they are backed by **design laws** — `docs/DESIGN_LAWS.md` —
each with its test: the Wall Principle (L-1), shame-safety (L-2),
configuration immutability (L-3), structure-aware/content-blind
(L-4), bounded release (L-5), cold-state consent for scope changes
(L-6).

And above all, the **Wall Principle**: the software does not respond,
explain, or engage. The only voice on the wall page is your own
contract line. Being boring is the function.

## Honest limits (by design, not by accident)

- **Tamper-evident, not tamper-proof.** You own the machine; you can
  kill anything. Every bypass is recorded, nothing is pretended away.
  `docs/FAILURE_MODES.md` lists all 24 known failure modes and their
  behaviors.
- **No AI in the enforcement path** (D-014). Deterministic rules only.
  Semantic models wait behind a labeling-first gate
  (`analysis/labels/`).
- **Restriction ≠ initiation.** The launcher exists because blocked
  distractions do not start work (dossier 6.1). Both are experiments
  A and C in `experiments/protocol.md`.
- The evidence base (`docs/RESEARCH_BASE.md`) justifies testing, not
  believing.

## Repository map

```
dhriti/            the Python core (pure stdlib; `python3 -m dhriti.cli …`)
├── stage_ratio.py the subject's own metric (D-046)
├── leisure.py     declared rest vs drift (D-047)
tests/             116 unittest cases — the fail-proof claim lives here
extension/         Dhriti Wall (MV3) + native-host alternative
launcher/          workspace ignition (PowerShell) + profile example
analysis/          sequence mining, measures, labeling guide, PM4Py PoC,
│                   specimens + the pattern taxonomy (P-01..P-10)
formal/            TLA+ lifecycle model (+ how to run TLC)
experiments/       N-of-1 protocol + machine-readable conditions
integrations/      every manual step: setup guides, audit templates, Windows policies
configs/tiers/     lite / standard / research overlays (dossier 11.1)
docs/              DESIGN_LAWS · RESOLUTIONS · TRACEABILITY · ARCHITECTURE ·
│                   SCHEMAS · ENFORCEMENT_LEVELS · FAILURE_MODES · RESEARCH_BASE · REFINEMENT
source-material/   your five input files, unchanged (D-002)
examples/demo/     a fully simulated day — run it, read its report
CHANGELOG.md       every version, what changed and why
```

## Verify the claims yourself

```bash
python3 -m unittest discover -s tests        # 116 tests
python3 examples/demo/run_demo.py           # simulated day + report artifacts
python3 analysis/specimens/code_specimen.py \
  analysis/specimens/specimen_001_turns.json \
  --out-dir analysis/specimens/SPECIMEN_001  # recode the baseline specimen
```

## What Dhriti is not

Not a universal productivity tool. Not for casual users. Not a coach,
therapist, or friend. It does not negotiate, explain, validate,
analyze, diagnose, or treat. It does not claim to be tamper-proof, to
cure ADHD or addiction, or to change anything by itself. It is a
radical personal experiment in making the gap between *what you said
you'd do* and *what you did* impossible to hide — first from yourself,
then from the one human who cares whether you actually grow.

---

Status: v0.3.0, Lite tier, research baseline — decisions remain open
in `docs/RESOLUTIONS.md` and `docs/REFINEMENT.md` (docking procedure
for your refined material). Version history: `CHANGELOG.md`.
