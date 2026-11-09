# Failure modes and what the system does about each

The fail-proof claim is bounded and honest: **every known failure
either recovers, degrades safely, or is recorded.** Nothing is
pretended away.

| # | Failure | Behavior | Test |
|---|---|---|---|
| 1 | daemon killed mid-session (SIGKILL) | next boot: session → INTERRUPTED → honest terminal state; day → RECOVERED if window passed; chain intact | `test_dead_daemon_sessions_recovered`, `test_dead_daemon_day_is_recovered` |
| 2 | daemon stopped cleanly during window | logged `daemon_stopping`; day stays recorded; next daemon resumes; gap visible in aftermath | — |
| 3 | two daemons started | lockfile with live-PID check; second start refuses | — |
| 4 | clock jumps / DST / timezone oddity | all persistence in UTC; monotonic offsets recorded per event; local windows resolved via zoneinfo with fixed-offset fallback (R11) | `test_window_resolution` |
| 5 | DB row edited by owner (triggers dropped) | hash chain verification fails at the first bad seq | `test_row_edit_detected`, `test_row_deletion_detected` |
| 6 | whole DB replaced by owner | undetectable locally — anchors exist to be copied off-machine; the review pack prints the head hash | `test_anchors_written` |
| 7 | extension removed mid-day | no browser events arrive → adapter status discloses "extension not seen recently" | adapter `status()` |
| 8 | bridge unreachable from extension | cached policy enforces until TTL; then unlocks (never locked out forever by a dead daemon) | extension logic (documented in INSTALL.md) |
| 9 | required adapter fails to arm | session ARMING_FAILED with disclosed reason; never silently ACTIVE | `test_arming_gate_blocks_active_without_required_adapter` |
| 10 | observation adapter dies | event recorded with telemetry_quality=DEGRADED; enforcement unaffected (deterministic policy, no observers needed) | — |
| 11 | missing telemetry | recorded as MISSING — never interpreted as inactivity | `test_missing_telemetry_is_unknown_not_inactivity` |
| 12 | break-glass delay bypassed | bypass recorded (`honored_delay=0` + ledger event); cooldown still applies | `test_delay_bypass_is_recorded_not_faked` |
| 13 | break-glass spam / restart loop | cooldown blocks new sessions and new breaks | `test_cooldown_blocks_new_break_and_sessions` |
| 14 | easy contract (finish at 10:05, scroll all day) | day stays locked until day_close; early release only with targets met | `test_early_finish_does_not_release_before_day_close` |
| 15 | no contract written at all | day stays NO_CONTRACT, closes INCOMPLETE at window_end | `test_no_contract_day_closes_incomplete_at_end` |
| 16 | research pass never closed | expires automatically; sources stop being allowed | `test_pass_expiry_removes_allowance` |
| 17 | proof: command not found / timeout | recorded with error detail; not crashed; verdict honest | `test_command_not_found_is_recorded_not_crashed` |
| 18 | config with start >= day_close | refused at window resolution with a clear error | `resolve_window` validation |
| 19 | attempt to edit sealed contract / events via SQL | triggers abort the statement | `test_sealed_contract_survives_direct_sql_update`, `test_append_only_triggers_fire_through_api` |
| 20 | corrupt SQLite | `PRAGMA integrity_check` surfaces in `dhriti verify` | — |
| 21 | bogus JSON posted to bridge | 400; oversized bodies refused | handler bounds |
| 22 | wrong/missing bridge token | 401 | `test_bridge...` (unauthorized fetch) |
| 23 | clock set backwards to dodge cooldown | cooldown compares stored ISO instants — a backwards clock makes the cooldown *longer*, not shorter | cooldown logic |
| 24 | event flood from extension | queue capped at 200; body size capped; ingest reports real count + errors | `background.js`, handler |

## The residual (accepted, documented)

A determined owner can always: drop the DB, kill processes, use
another device. Dhriti is **tamper-evident, not tamper-proof** — by
design and by honest statement (dossier 2.7). The one full solution
the dossier names is another human who cares; the software's job is
making the gap between said and did impossible to hide from that
person (PDF 3.8).
