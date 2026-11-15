# RESOLUTIONS — every contradiction, one decided behavior

This file resolves the conflicts your own dossier flags (section 2.2)
plus the ones I found while building. Each entry: the conflict, the
resolution now implemented, and where to veto it. **Nothing here is
sacred — change any row, then change the named module to match.**

## R1 — Day release: fixed end vs completion unlock vs lock-past-close

**Conflict (PDF 3.2/3.6/3.7 vs dossier D-018):** fixed 21:00 end;
unlock when targets met; stay locked past day-close if incomplete.

**Resolution (implemented in `dhriti/day_window.py`):**
- `window_end` (21:00) = **unconditional ceiling**. Everything
  releases at window_end no matter what — an incomplete day can never
  lock you in indefinitely.
- `day_close` (20:00) = **earliest** early release, and only when
  targets are already met.
- Finishing early never releases before day_close (the easy-contract
  loophole stays closed).

## R2 — Session vs day as enforcement unit

**Conflict:** sessions are the success/failure unit in PDF §5–6; the
day-window is the enforcement boundary in PDF §3.

**Resolution:** bootcamp = policy container; day = enforcement
boundary; session = atomic work unit with the three (honest: four)
terminal states. Enforced in `state_machine.py`, `day_window.py`,
`session.py`.

## R3 — Wall vs intervention surfaces

**Conflict:** the Wall Principle forbids all messages; the detector
design proposes return-to-task prompts.

**Resolution:** during a session the only surfaces are: the CLI status
line (state/task/elapsed), and the wall page showing **your own
contract line**. No reason strings, no checkpoints, no "return to
task". WARN-level decisions exist only in the taper stages ≥ 3 you
yourself earn, and they log without speaking. `policy.py`
(`extension_rules`), `extension/blocked.html`.

## R4 — Network proxy in v1?

**Conflict:** early architecture mentions a network proxy; dossier
rejects it for v1.

**Resolution:** rejected. No proxy. E2 network control exists only as
the hosts-file generator (manual apply) and documented leads
(Portmaster/OpenWrt are source-register leads, not code).

## R5 — Privacy/API defaults

**Conflict:** "API opt-in" in one section, "API by default" in
another.

**Resolution:** local-first, zero network calls in the core. The only
listener is the loopback bridge (token-authenticated). External
providers (vision proof, AI tools) are disabled and require explicit
per-provider config. `bridge.py`, `integrations/vision-proof/`.

## R6 — Graduation: no taper vs evidence-based taper

**Conflict:** the manifesto says no taper/no mercy; the architecture
proposes evidence-based taper.

**Resolution:** taper is computed from evidence only (`bootcamp.py`:
compliance ≥ 0.80 AND proof ≥ 0.70 AND break-glass ≤ 1/week AND ≥ 30
days), never from the calendar, never guaranteed. Graduation remains
an experiment, not a promise. Thresholds are personal parameters in
config.

## R7 — Is a screenshot proof?

**Conflict:** PDF 6.2 sometimes treats the vision workflow as
verification.

**Resolution:** evidence classes are distinct and ordered
(`evidence.py`): MACHINE_CHECKED > OBSERVED > SUBMITTED. A screenshot
description is SUBMITTED — a claim with provenance. The vision
workflow is disabled by default and can never be the sole basis of a
MACHINE_CHECKED verdict.

## R8 — Enforcement: one wall or several capabilities?

**Conflict:** PDF treats browser blocks + OS controls + network +
tamper resistance as "the wall".

**Resolution:** explicit levels E1–E4 (`docs/ENFORCEMENT_LEVELS.md`),
each with named bypass routes. The daemon arms only what probes
INSTALLED and discloses the rest. Required-adapter failure = session
ARMING_FAILED, never silent.

## R9 — Penalty enforcement honesty (mine, added)

**Conflict:** PDF 7.2 says break-glass triggers a "pre-defined
penalty"; dossier 2.7 says the system must not claim to impose what it
merely logs.

**Resolution:** penalties are **declared** in the cold state and
recorded with the break; the system never executes them (no
destructive automation) and the aftermath shows them as *declared*.
`break_glass.py`.

## R10 — "90% of the day enforced" vs sleep/reality (mine, added)

**Conflict:** PDF 3.2 says 10:00–21:00 is ~90% of the waking day and
the user is "offline or on stage" for all of it.

**Resolution:** kept the window as configured default (10:00–21:00
IST) but the model records OFFLINE only from real observer events
(AFK), never assumes it. An 11-hour hard window with no contract
written closes INCOMPLETE — honest, not punitive. Configurable per
user.

## R11 — Zoneinfo on Windows (mine, added)

**Risk:** Python on Windows lacks the IANA tz database by default.

**Resolution:** `timeutil.local_tz()` degrades to a fixed-offset
fallback with the event recorded, instead of crashing the daemon.
README tells Windows users `pip install tzdata` for correct IST.

## Veto procedure

1. Edit the row above (or add one).
2. Change the named module + the covering test.
3. `python -m unittest discover -s tests` must stay green.
4. Note the change in your next cold review.
