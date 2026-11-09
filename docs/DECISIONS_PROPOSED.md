# Proposed decision register additions (v2.1)

Docked per `docs/REFINEMENT.md`: the refined material (implementation
plan v2.0 of 2026-11-03 + Specimen 001) produced these rows. They are
PROPOSED — the builder confirms, then they move into the authoritative
register. Existing decisions touched are listed first with their status
changes.

## Status changes to existing decisions

| ID | Change | Reason (evidence) |
|---|---|---|
| D-003 (verbatim chat preservation) | OPEN ACTION → **PARTIALLY CLOSED** | Specimen 001 (`procrastination attempt1.pdf`) is the first raw export; it is coded in `analysis/specimens/` and its lessons are wired into the build. More exports remain wanted. |
| D-005 (enforcement bake-off) | unchanged, still gates adapters | Cold Turkey CLI thinness (status-only, no lock reporting) is now recorded in the audit queue expectations — see plan Part 4 appendix. |
| D-018 (day-window semantics) | RESOLUTION CONFIRMED by code | The v0.1 resolution (start < day_close ≤ end; unconditional ceiling; early release only at day_close with targets met) is exactly the "precommitted bounded early-release" D-018 asks for. No change. |
| D-024 (surface suppression) | DECIDED → **IMPLEMENTED (E1)** | `extension/suppress.js` + `surface_suppressed` events + `suppress_surfaces` policy flag. Follow-up suggestions on AI chats are a first-class rule target (Specimen 001). |
| D-025 (bridge) | IMPLEMENTED with honest limits | Loopback HTTP + token + 401-probe logging (`bridge_token_rejected`). Per-session token rotation is NOT implemented (static config token; `dhriti token rotate` is a cold-state action) — full rotation belongs to the Tauri build. |
| D-030/D-031 (main belief / competence source) | DECIDED → **IMPLEMENTED** | Contract group required (validated as a unit); aftermath exchange block; six-question cold review incl. `competence_source` and `wall_or_choice`. |

## New decisions (proposed)

| ID | Topic | Position | Status | Implementation |
|---|---|---|---|---|
| D-032 | AI-chat springboard | Follow-up suggestions are a recommendation surface under D-024: hidden on AI chats during strict sessions; the conversation is bounded to the task. Enforcement watches STRUCTURE (turns without evidence events), never content. | PROPOSED (implemented) | `suppress.js` ai-followups rules; aftermath consumption facts |
| D-033 | Curiosity parking lot | The wall has a mail slot: mid-session curiosity is parked in one line (`curiosity_topic_parked`) and dispositioned cold (approved/dropped/explored). Replaces both silent suppression and following the branch. | PROPOSED (implemented) | `dhriti park`, parking_lot table, review dispositions |
| D-034 | Dead-man's-switch digest | A weekly one-page digest (facts + chain head) is sent to a named human. Absence of the digest is the tamper signal. Minimal E4, available now, no credentials stored. | PROPOSED (implemented) | `dhriti digest`, `build_digest`, `digest.recipient_label` |
| D-035 | Builder clause | Optional config: while the day's targets are unmet, configured builder domains (the Dhriti repo) are blocked. Building the tool is earned by meeting the day's target. Default OFF; enabling is a cold-state act. | PROPOSED (implemented, off) | `builder_clause_applied` event, policy extra_blocked_domains |
| D-036 | Emergency path | `emergency_exception`: immediate, typed, no toll, no cooldown, shown separately in the aftermath and digest. The pattern (not any single use) is reviewed cold. | PROPOSED (implemented) | `break_glass.emergency`, D-019 wiring |
| D-037 | Cold-review protocol | Six fixed questions incl. D-031 competence source and the graduation meta-metric ("wall or choice?"). Answers are SUBMITTED evidence, stored bootcamp-scoped; only question keys enter the chain. | PROPOSED (implemented) | `dhriti review`, cold_review table |
| D-038 | Evidence unreliable-mark | A cold-state flag on accepted-but-weak evidence; verdict unchanged, flag is the signal (recognition mechanism 7). | PROPOSED (implemented) | `dhriti proof mark-unreliable` |
| D-039 | Raw-capture format | Chat exports without timestamps are marked telemetry-quality UNKNOWN for duration analysis; future captures must preserve timestamps. | PROPOSED | Specimen 001 lesson; coder marks UNKNOWN |
| D-040 | Specimen archive | Saved AI-chat exports are baseline data (Phase 2, early). Each is hand-coded into the event vocabulary; a vocabulary that cannot express a specimen is wrong. | PROPOSED (implemented) | `analysis/specimens/`, `code_specimen.py` |
| D-041 | Journal mode | DELETE unconditionally on Windows; stale WAL/SHM quarantined (renamed `*.corrupt-<ts>`), never deleted; config override allowed. | PROPOSED (implemented) | `db.resolve_journal_mode`, `_open_with_recovery` |
| D-042 | Break-glass reason analytics | Reasons are contract-design feedback: recurring reasons (e.g. "needed docs that were blocked") mean the cold-state plan is missing something. The digest lists reasons verbatim; the cold review reads the pattern. | PROPOSED (implemented) | digest reasons block |
| D-043 | Blocked-tab closure at arming | When the wall arms, tabs already open on blocked domains are closed by the extension (plan ARMING check 5), counted as `blocked_tabs_closed`. | PROPOSED (implemented) | `closeBlockedTabs` in background.js |

## New decisions proposed in v0.2.1 (the procrastination-attempt re-audit)

The re-audit of Specimen 001 (question: "did you consider the
procrastination attempt as a behavioral reference?") found the specimen
was docked, but nine things in it were missed or under-derived. Rows
below; the addendum report (`DHRITI_v0.2.1_*.docx`) carries the full
M-register with severities.

| ID | Topic | Position | Status | Implementation |
|---|---|---|---|---|
| D-044 | AI Mode surface suppression | The founding specimen ran on Google AI Mode (`google.com`, `udm=50`) — a chat surface on a domain search needs. It can never be category-blocked; surface suppression is the only lever. Scope by URL parameter, suppress the springboard surfaces (follow-ups, related questions), never the chat itself, never the entry link. | PROPOSED → **IMPLEMENTED (v0.2.1 fix)** | `extension/suppress.js`: `isAIMode()`, `activeRules()`, `AIMODE_RULES` (`aimode-followups`, `aimode-related-qs`); selectors are day-one candidates under the stale-selector convention |
| D-045 | Behavioral pattern taxonomy | The subject's own requested artifact (specimen phase `pattern_collection`, requested twice) — delivered as a reference: P-01…P-10 (intellectualization → beginner-status shame avoidance) with the engine (P-10 drives P-01/P-07) and the "cold only, never predictive" rule. Naming a pattern hot is itself P-02. | PROPOSED → **IMPLEMENTED (reference)** | `analysis/labels/BEHAVIORAL_PATTERNS.md`; maps to labeling guide, review questions, digest reading |
| D-046 | Stage-ratio measure | The subject quantified himself in the specimen: "audience for 90% of time" vs. the 70–80/20–30 band he endorsed. That is his own metric and the project's natural primary measure — previously absent. Compute a deterministic daily ratio (evidence-bearing activity vs observed consumption, category-count based) with his reference band, in the aftermath and `analysis/measures.py`. Counts, never content (D-014). | PROPOSED → **IMPLEMENTED (v0.3.0)** | `dhriti/stage_ratio.py` (canonical); aftermath "Stage ratio" block; `measures.py` standalone copy; digest line |
| D-047 | Declared leisure | The specimen's sharpest distinction: chosen rest vs. drift ("if you are truly content being an audience member, then own it"). `dhriti declare leisure` (one-way, typed, bounded 1..240 min, session-free): declared time shows in the aftermath as **declared rest**; undeclared consumption shows as **drift**. The review asks whether declarations were honored (conditional 7th question, day scope only). Not a permission — a label. | PROPOSED → **IMPLEMENTED (v0.3.0)** | `dhriti/leisure.py`, `leisure_declaration` table, `declare leisure` CLI, aftermath block, `leisure_honored` question |
| D-048 | Observation beyond the window | Enforcement correctly ends at `window_end`; observation previously ended with it — the evening hole is unmeasured, which is how the founding specimen happened. Split: enforcement ends at `window_end`; category observation continues to `day_end` under the `surveillance_comfort` consent, config `observation_evening` (default OFF; enabling is the consent act). The hole becomes measured, not closed. | PROPOSED → **IMPLEMENTED (v0.3.0, default off)** | `resolve_observation_end`, `evening_observation_active` marker, observation adapters keep polling, whole-day consumption facts (window/evening split) |
| D-049 | Earned evening (general builder clause) | The specimen's own protocol, stated twice by its AI: "no meta-discussion until you have compiled one program today" / "treat media as an earned reward." The builder clause (D-035) is this pattern for one domain; generalized: configured consumption categories stay blocked after `window_end` **until day_end** on days whose targets were NOT met (bounded per D-018). Default OFF; enabling is a cold-state act, exactly like D-035. Days that met their targets release to an open evening. | PROPOSED → **IMPLEMENTED (v0.3.0, default off)** | `_earned_evening_policy`, `earned_evening_applied` event, `earned_evening` config group |
| D-050 | Configuration immutability | The specimen shows tool/config choice as avoidance ("what about C? or Python?" — "language choice is just another audience chair"). Profile/category edits must be cold-state acts that take effect at next daemon start, and the edit itself is builder-domain activity. This was true only by accident (profiles load once at daemon start). Now stated as law L-3 and made visible: the daemon fingerprints what it loaded, and a config/profile file that changes on disk while it runs is recorded as `config_drift_detected` — never hot-reloaded. | PROPOSED → **IMPLEMENTED (v0.3.0, law L-3)** | `docs/DESIGN_LAWS.md`, `Daemon._fingerprint`/`_check_config_drift`, fingerprint in `daemon_started`, `profiles.py` docstring |
| D-051 | Digest exchange line | The digest carries days/sessions/breaks/parking/review — but not the exchange itself. Now carries the stage-ratio line (D-046), top consumption categories, and the week's declared-rest and drift totals, so the E4 human sees the exchange weekly in the subject's own vocabulary. | PROPOSED → **IMPLEMENTED (v0.3.0)** | `build_digest` (stage ratio + declared rest vs drift sections) |
| D-052 | Shame-safety as a design law | Pattern P-10 is the affective engine: "the compiler exposes you as a beginner; the audience seat is safe." The build already honored it partially (errors-as-proof, `never generated praise, never shame`). Now stated as the whole law (L-2) so every future surface is tested against it: no comparative framing (streaks, percentiles), no eloquence (Wall Principle), errors are first-class proof, identity lines are the user's own words only. | PROPOSED → **IMPLEMENTED (v0.3.0, law L-2)** | `docs/DESIGN_LAWS.md`; `tests/test_design_laws.py` lints every extension surface and generated report against the forbidden-phrase list |

## Deliberately NOT done (and why — the anti-scope list)

- **Per-session bridge token rotation** (D-025 full form): needs a
  settings UI that does not exist in the Lite tier; the static token +
  cold rotation + 401 logging is the honest Lite boundary.
- **In-session classifier or content reading**: nothing in this build
  reads page content or chat text. All new signals are structural
  counts (D-014 remains absolute).
- **Checkpoint mode, notifications, streaks, badges beyond up/down**:
  the Wall Principle; Specimen 001 is the evidence for why eloquence
  (even eloquent refusal) feeds the loop.
- **Mobile coverage**: out of scope until the desktop loop is proven
  (D-028 unchanged); the review question `out_of_scope_device` keeps
  the hole visible instead of pretending it is closed.
