# Documentation log

The "does the code match the docs" register (roadmap Phase 0b). Every
divergence found between the documentation and the source is named
here and either fixed in the named release or recorded as a decision
in `docs/DECISIONS_PROPOSED.md`. History is preserved; errors are
named, never silently overwritten.

## Part 7 — the v0.7.0 audit (addendum spec, Parts 3 and 4)

Scope: the uploaded addendum ("v0.6.0 — PARTS 3 AND 4") was audited
item by item against the tree as v0.7.0 was built. The addendum's own
"sequencing" section is superseded by history: v0.6.0 shipped Parts
1+2 of the earlier spec; the addendum's Parts 3+4 ship as v0.7.0
(the version number documents the scope).

Divergences found, and their resolutions:

1. **Spec self-dating.** The addendum titled itself "completes
   v0.6.0" while Parts 1+2 of the base spec had already shipped as
   v0.6.0. Resolution: released as v0.7.0; the CHANGELOG states the
   scope mapping.
2. **`dhriti digest --confrontation` vs a standalone command.** The
   addendum specifies the confrontation file under
   `dhriti digest --confrontation`; the tree also wires a standalone
   `dhriti confrontation` (same generator, same event). Resolution:
   both exist; `digest --confrontation` delegates. Recorded, not
   deduplicated.
3. **Specimen 002's raw transcript.** The addendum codes "the
   11-turn AI conversation from earlier in this conversation" — the
   conversation itself was never pasted into the repository record.
   Resolution: the coding is reconstructed from the documented
   analysis (counts, changepoint pair, four verbatim quotes) and
   marked as such in the turns file and findings; the four documented
   counts recompute exactly. The verbatim transcript remains the
   operator's to paste.
4. **Brave-filter rule support.** The addendum says unsupported
   syntax is "regex, script injection"; the first implementation
   also rejected CSS ID selectors (`##element`). Resolution: fixed —
   ID selectors are supported CSS; regex (`/.../`), rewrite options,
   `:inject`/`:style`/`:remove`, and uBO `-ext-` syntax are the
   honest unsupported set (test names the split).
5. **Health staleness window.** The spec's selector-staleness
   aggregation ("last 7 days") was first implemented against
   SQLite's wall clock, so a replayed record aggregated against the
   real now. Resolution: fixed — the cutoff comes from the clock the
   ledger runs on.
6. **Topic-lock lexical half.** First implementation used Jaccard
   over full token sets; a long on-topic continuation ("the JWT test
   still fails on refresh") scored below the 0.65 threshold against
   its own topic. Resolution: fixed — topic coverage (the topic is
   the anchor) with a light stem and 4+-char prefix matching;
   documented in the module.
7. **Five-view coverage lines.** The addendum requires a "coverage
   missing" section per view; the L-4 wording in View 3 predates
   L-9. Resolution: the View 3 coverage line now names the L-9
   exception precisely (prompt-only, session-bound, off by default).
8. **`_ask` under captured stdin.** Interactive prompts crashed under
   piped/headless runs (including the test harness) instead of
   taking the stated default. Resolution: fixed — EOF/OSError falls
   back to the default; prompts without defaults return empty and
   their callers decide.

Decisions opened by this audit: D-073..D-080 in
`docs/DECISIONS_PROPOSED.md`.

## Part 7 acceptance criteria (per the user's discipline rule)

- [x] Every addendum Part 3/Part 4 item is either built, gated
      default-off, or refused on principle (Part 5 §5.4's refusals
      stand; no new refusals were needed).
- [x] No "deferred" / "not in this release" items remain from the
      addendum's scope.
- [x] The suite is green; the CHANGELOG states the honest counts and
      the difference from the addendum's targets.
