# Design laws

The constitution of this codebase. Principles (README) say what Dhriti
is for; **laws** are what every current and future surface is tested
against. A mechanism that cannot obey these is not shipped — it is
rewritten or refused. Each law names its test, because in this project
a claim without a test is a hope.

Origin note: laws L-1 and L-2 existed as conventions from v0.1. Laws
L-3 through L-6 were proposed by the Specimen-001 re-audit (v0.2.1,
decisions D-050/D-052) and made mechanical in v0.3.0. The specimen is
the evidence for every one of them.

---

## L-1. The Wall Principle (never respond, explain, or engage)

The software does not argue, persuade, console, or entertain — during
a session. The only voice on any enforcement surface is the user's own
contract line, written cold. Specimen 001 proof: the AI's eloquent
refusals ("Your mind is incredibly artistic...") were consumed as
content; even a moralistic refusal is an affordance. **No Dhriti
surface may end an interaction by proposing the next one.**

*Tests:* `tests/test_design_laws.py` — the wall page carries no links,
no buttons, no forms; no surface text contains engagement phrases.

## L-2. Shame-safety (D-052)

Pattern P-10 is the affective engine the build exists to disarm: "the
compiler exposes you as a beginner; the audience seat is safe." A tool
that shames repels the user back to the audience; a tool that praises
feeds the validation loop (P-05). Therefore, in every surface:

1. **No generated praise** — no "great job", no congratulations, no
   pride. Achievement facts (accepted evidence, targets met) are
   stated as facts or not at all.
2. **No shame** — no "lazy", no "you failed", no disappointment
   language. Gaps are shown as observed facts with timestamps.
3. **No comparative framing** — no streaks, percentiles, ranks,
   "better/worse than". The only reference band in the system is the
   user's own endorsed band (D-046), and the software computes the
   distance for no one — the reader does.
4. **Errors are first-class proof** — a documented failed attempt with
   a non-zero exit is accepted evidence when the contract says so
   (`accept_nonzero_exit`). "Let it error, fix one line, compile
   again" is the specimen's own instruction.
5. **Identity lines are the user's words only** — the aftermath quotes
   the contract; it never authors a sentence about the user.

*Tests:* `tests/test_design_laws.py` lints every extension surface and
the generated aftermath/digest output against the forbidden-phrase
list. New surfaces must be added to that list — the law is the test.

## L-3. Configuration immutability (D-050)

Config and profile edits are **cold-state acts**. The daemon loads
them once at start and never hot-reloads: an edit on disk takes effect
at the next daemon start. A config/profile file that changes while the
daemon runs is recorded as `config_drift_detected` (telemetry
DEGRADED) — visible, never applied. The specimen documents tool/config
choice as avoidance ("language choice is just another audience
chair"); making the reconfiguration of the guardrail itself visible in
the record is the countermeasure.

*Tests:* `tests/test_design_laws.py::TestConfigImmutability`.

## L-4. Structure-aware, content-blind (D-014, absolute)

Nothing in the enforcement or observation path reads page content,
chat text, or window titles as semantic input. All signals are
deterministic structural counts (domains, categories, event types).
The behavioral pattern taxonomy (P-01..P-10) is reference vocabulary
for cold-state coding — naming a pattern hot is itself P-02, and the
software never does it. No classifier, no model, no prediction.

*Tests:* the policy engine and all adapters are deterministic by
construction; `analysis/labels/BEHAVIORAL_PATTERNS.md` carries the
cold-only rule.

## L-5. Bounded release (D-018)

Every lock has a ceiling: the day releases unconditionally at
window_end; the earned evening (D-049) ends at day_end; break-glass
cooldowns expire; research passes expire. Nothing in this system may
block indefinitely — an unbounded lock is a bug, not a feature.

*Tests:* day-window transitions; `tests/test_earned_evening.py`
(expires_at == day_end, policy goes dormant past it).

## L-6. Cold-state consent for scope changes

Anything that changes what the system **measures, locks, or watches**
defaults OFF and is enabled only by a cold-state act (config edit,
next daemon start): the builder clause (D-035), evening observation
(D-048 — a `surveillance_comfort` consent), the earned evening
(D-049). A session, a document, or an agent may propose; only the
builder, cold, confirms.

**Interaction with the allowlist (Phase 0, Bug 7):** the builder
clause never overrides the profile allowlist. If a domain is an
allowed work surface for the active profile (or the contract's
`allowed_tools`), the builder clause does not block it — blocking the
work surface that meets the day's targets would be self-defeating.
The override is recorded as `builder_clause_overridden_by_allowlist`,
never silent.

*Tests:* defaults in `dhriti/constants.py`; the v0.3 mechanisms all
assert OFF-by-default behavior in their test files; the allowlist
interaction is asserted in `tests/test_review.py` and
`tests/test_daemon_integration.py`.

---

## How to use these laws

When adding any surface (page, report, message, notification-shaped
thing — see L-1 before adding one of those), run the law checks
against it:

1. Does it speak in anything but the user's own words? (L-1)
2. Does it praise, shame, or compare? (L-2)
3. Does it read content rather than count structure? (L-4)
4. Can it lock or watch beyond its declared bound? (L-5)
5. Did changing it require a hot reload? (L-3)
6. Is it on by default when it widens scope? (L-6)

One "yes" is a rewrite. The laws are short so that they can be
remembered in the moment they are about to be broken.
