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

*§1.3 Sovereign Interstitial & Bounded Alerts Amendment (v0.7.0+):*
A surface, interstitial, or sticky overlay may state neutral factual context
regarding today's declared targets, relevance score, or a held attempt, offering
bounded sovereign actions: [Back to Target], [Add as Today's Topic / Pivot], or
[Park for 20:00]. It never lectures, shames, or congratulates. Bounded desktop
notifications (maximum 3/day) are permitted strictly for: day-open ritual reminders,
overdue commitments, or daemon health alerts.

*Tests:* `tests/test_design_laws.py` — the wall page carries no links,
no buttons, no forms; no surface text contains engagement phrases.

## L-2. Honest metrics (was Shame-safety, D-052)

Pattern P-10 is the affective engine the build exists to disarm: "the
compiler exposes you as a beginner; the audience seat is safe." A tool
that shames repels the user back to the audience; a tool that praises
feeds the validation loop (P-05). Therefore, in every surface:

1. **No generated praise or validation** — no "great job", no
   congratulations, no pride, no confetti or cheering animations.
   Achievement facts (accepted evidence, targets met) are stated as
   facts or not at all.
2. **No moralizing shame** — no "lazy", no "you failed", no
   disappointment language. Gaps are shown as neutral observed facts
   with timestamps.
3. **No competitive framing or gamification** — no streaks as badges of
   moral worth, no percentiles, no ranks, no levels, no virtual currency,
   no tomato icons (zero Pomodoro gamification). Streak is presented
   solely as a neutral completion fact: run days count and past run record.
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

## L-4r. Semantic Intelligence & Relational Input Inspection (v0.7.0+ Revision)

Dhriti rejects blind decision-making. Ambient background observation remains
structural and non-invasive, but **declared-input inspection** (search query parameters,
AI chat prompts, address-bar text, and rendered visual media) is explicitly permitted
and actively performed on-device.

The decision engine is **content-aware and relational**: it computes semantic similarity
between what the operator types and what the operator promised to study today. A query
is never blocked based on dumb keyword absence; it is judged by whether it serves
the active target. All semantic processing is strictly local (vector embeddings via
FastEmbed / ONNX and local LLM reasoning via Ollama) with zero remote transmission.
Raw text resides exclusively in a temporary 14-day local TTL store; the permanent
audit ledger records only hashes, scores, and timestamps.

*Tests:* `tests/test_v070_additions.py`, `tests/test_topic_gate.py`.

## L-5. Bounded release (D-018)

Every lock has a ceiling: the day releases unconditionally at
window_end; the earned evening (D-049) ends at day_end; break-glass
cooldowns expire; research passes expire; decompression zones expire
at 90 minutes. Nothing in this system may block indefinitely — an
unbounded lock is a bug, not a feature.

*Tests:* day-window transitions; `tests/test_earned_evening.py`
(expires_at == day_end, policy goes dormant past it).

## L-6. Asymmetric consent for scope changes

1. **Weakening requires cold-state consent:** Anything that weakens
   restrictions, disables guards, widens allowlists, or lowers friction
   defaults OFF and is enabled ONLY by a cold-state act (config edit,
   next daemon start, post-day review): the builder clause (D-035),
   evening observation (D-048), earned evening (D-049).
2. **Strengthening is allowed hot:** The user may voluntarily strengthen
   protection in the heat of the moment (e.g. engaging Lockdown, deep
   guard, or tightening allowlists). This is framed calmly and
   authoritatively as an ordinary daily operational act — never as a
   panicky, shameful, or crisis-driven "SOS" button.
3. **§6.3 Declared Pivot (Hot Bounded Pivot):** Hot weakening is permitted
   strictly as a declared pivot when priorities shift (e.g. pivoting to an
   urgent aptitude drill). The operator enters a brief reason (≥15 chars);
   the system enforces a 30-second deliberate pause (capped at 3 pivots/day),
   unlocking the new target in the sticky overlay without breaking the contract.
   Never permitted for adult or entertainment categories.

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

v0.6.0 addition: the parking lot resurfacing surfaces items only
after the earned-evening moment; the parking lot never pushes during
a session (the evening block requires `targets_met`, and the
review surfacing is a cold-state command).

---

## L-8. Bounded, not optimized (v0.6.0)

The conversation is bounded, not optimized — any in-session mechanism
must bound the interaction, never optimize it (no engagement
maximization, no "smarter" recommendations, no pacing). The
curation_choice conditional question is the only L-8 mechanism in
v0.6.0's scope; the topic-lock and completion-detector mechanisms
arrive with their own consent gates in later versions, bounded by
this law. A mechanism that makes the bounded thing more engaging is a
violation even if it is "helpful."

*Tests:* `tests/test_design_laws.py` (surface lint); the parking and
mirror surfaces carry no affordances.

---

## L-9r. Local On-Device Input Analysis & Continuous Learning (v0.7.0+ Revision)

All text the operator inputs into a browser (search queries, address-bar
navigations, AI chat prompts) and non-allowlisted rendered visual media
may be inspected and classified on-device.

1. **Active by default during study:** When a contract is active, semantic
   inspection is armed so the operator is never blocked blindly by dumb
   heuristics.
2. **Local vector reasoning:** FastEmbed embeddings (~15ms) and local
   Ollama LLM adjudication evaluate semantic relevance against today's
   declared targets.
3. **Continuous self-learning loop:** Clicking "This was actually study"
   absorbs the vector into `vec_safe_anchors` in `guard_content.sqlite3`.
   The system permanently learns without the operator maintaining keyword lists.
4. **Zero external transmission:** Processing is strictly on-device. Raw
   queries are purged after 14 days (TTL store).

*Tests:* `tests/test_v070_additions.py`, `tests/test_vidura_mechanisms.py`.

---

## L-11. Topic observation over generic screen time (v0.7.0+)

Tracking generic "screen time" is an anti-pattern: it conflates
demanding compilation, active coding, and research with passive
entertainment scrolling, producing meaningless guilt. Dhriti decomposes
time into domain and topic segments (Stage vs Audience, core topic vs
drift). Time is displayed as honest, neutral topic-segment distributions
(hours per domain, topic clusters), never moralized totals.

*§11.2 Declared Learning as Stage Work:*
Any video, playlist, or document declared as an active learning target
in today's contract (with accepted completion recall) is formally classified
as **Stage (Active Output/Productive Work)** rather than passive "Audience"
consumption. Undeclared video remains Audience.

*Tests:* `tests/test_dashboard_bridge.py` (topic time histogram facts).

---

## How to use these laws

When adding any surface (page, report, message, notification-shaped
thing — see L-1 before adding one of those), run the law checks
against it:

1. Does it speak in anything but the user's own words? (L-1)
2. Does it praise, shame, or compare? (L-2)
3. Does it make blind, crude decisions instead of on-device semantic relevance? (L-4r)
4. Can it lock or watch beyond its declared bound? (L-5)
5. Did changing it require a hot reload? (L-3)
6. Is it on by default when it widens scope? (L-6)

One "yes" is a rewrite. The laws are short so that they can be
remembered in the moment they are about to be broken.
