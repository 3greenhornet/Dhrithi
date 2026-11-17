# Decision register batch — D-071 to D-089

Paste-ready rows in the house format. Each has a test or a drill that
keeps it honest. Existing decisions referenced: D-014 (no LLM in
enforcement), D-043 (P-codes as reference vocabulary), D-053/54 (topic
lock, completion line), D-057 (burst detection), D-062 (TTL lapse),
D-024/032 (surface suppression, chips as rec surface).

| ID | Decision | Rationale | Test / check |
|---|---|---|---|
| D-071 | A held or collapse-sealed response becomes a parking-lot item (kind: question) with sparked-by lineage; reveal only at cold state after the recall step | Enforcement output must land in an EXISTING bounded pipeline, not a new lane; reuse recall-before-reveal | `/guard/park` handler; disposal counters in digest |
| D-072 | Rate governor: >= 3 sends in 10 min -> hold-to-send toll (10 s), lingering 10 min; timestamps only, site-agnostic | L-4-pure half of the guard; covers sites with no adapter and survives DOM rot | `test_three_sends_in_window_toll`, `test_window_expiry_clears` |
| D-073 | Length governor: assistant responses beyond a structural char cap collapse their tail behind an expand-toll | P-11/P-16 are structural patterns; fight structure with structure, not semantics | extension `lengthGovernor`; cap is config |
| D-074 | Two-axis verdict: about-ness (embedding) + do-ing-ness (dialogue acts -> P-codes); P-codes become the LIVE verdict vocabulary shared with cold mining | Embeddings miss adjacent-topic leaps; springboarding is a functional pattern | `test_leap_overrides_adjacency`, `TestVerdictFusion` |
| D-075 | Raw text lives ONLY in the sidecar TTL store, architecturally outside the hash chain; ledger keeps {hash, verdict, action, latency, counts}; purge on schedule | Append-only chain + "delete raw from time to time" are only compatible if content never enters the chain | `test_no_hash_chain_columns`, `test_purge_expired_only` |
| D-076 | Mode -> guard-aggressiveness mapping table (FULL: park-only; REDUCED: hold+toll; CHECKPOINT: collapse-seal; ADVISORY: card-only) | Reuses the existing taper modes as the guard's dial; nothing new to seal | `TestModeFloor` |
| D-077 | Adapter blindness is fail-visible: probe at arm-time, DOM canary mid-session, `guard_adapter_blind` / `guard_dom_canary_missing` events, digest flag | A guard that goes blind silently is worse than no guard | `probe()` + `checkCanary()`; `/guard/adapter_health` |
| D-078 | Taper transitions use a Schmitt trigger: one breach tightens immediately; down_days clean streak to relax | Prevents stage chattering day-to-day | `TestSchmitt` |
| D-079 | Divergence debt: bounded accrual on holds/parks, daily decay, accrual FROZEN under FULL_LOCK (anti-windup) | Long locks must not accumulate unbounded rebound pressure | `TestDebtAntiWindup` |
| D-080 | Sensor cross-check: ActivityWatch browser-minutes with zero extension nav events => `guard_sensor_conflict` (other-browser or blind adapter) | Two weak observers catch the named E1 hole; disagreement is a signal, not noise | `TestSensorConflict` |
| D-081 | E2-tamper canary: a hosts entry that must only ever resolve to the blackhole; weekly check emits `guard_e2_canary_missing` on tamper; DOM canary per adapter | The hosts block can be silently deleted; silence becomes an event | `TestCanary`, `scripts/e2_canary_check.ps1` |
| D-082 | Thread interlock: a new chat thread requires the previous thread's disposal (parked / completed / abandoned); pivot budget per mode (0 / 1 / logged) | Trapped-key applied to springboarding; the key to thread N+1 is the disposal of thread N | `TestThreadInterlock` |
| D-083 | Conformance view: the contract encodes the day's normative model; stdlib deviation check always, PM4Py token replay optional (offline) | Aims the already-named tool at the already-built artefact | `dhriti conform`; `render_conformance_md` |
| D-084 | Witness verification goes CT-style: witness stores anchors only; any day provable in-chain by segment recomputation without content trust | E4 stops being trust-based; anchors already exist every 100 events | `TestAnchorProof` (align `event_hash` seam with ledger.py) |
| D-085 | Digest tracks the park:break ratio (near-miss pyramid); falling parks with steady breaks flags "routed around" | Leading indicator no single event shows; shame-safe framing (near-miss, not failure) | `TestParkBreakRatio` |
| D-086 | Chaos drills as a monthly ritual: dead-daemon, TTL lapse, sidecar quarantine, token revocation, canary tamper | Untested failure paths are assumed-working fiction; pairs with TLA+ counterexample fixtures | `scripts/DRILLS.md`, `chaos_drills.*` |
| D-087 | Hosts-file block lists get a bypass audit: flag non-blackhole IPs, www gaps, punycode/homoglyph entries, trailing-dot and duplicate-conflict anomalies; hard findings emit `guard_e2_block_bypass_risk` | The CVE-2026-17923 lesson generalized: exact-match lists are routed around by name variants; the canary proves ONE hostname, not that the list still means what it said | `canary.audit_hosts_entries`; `test_v1_1_additions` |
| D-088 | External blocker CLIs are probed, not trusted: audit-gated arming, MACHINE_CHECKED evidence from exit codes, rename-bypass canary on the documented service image names (`ServiceHub.*`, `CTMsgHost*`); missing services under an active block emit `guard_stack_bypass_risk` | Cold Turkey v4.9 CLI facts + public rename-bypass record; D-005 (delegate, verify); fail-visible, same logic as D-077 applied to the external stack | `external_cli_probe.audit_gate`; `test_v1_1_additions` |
| D-089 | Guard invariants get adversarial fixtures: each trace has a stated invariant, an attack story from the user's side, and steps+asserts; the runner is generic so real TLC counterexamples can be pasted in later | Closes the golden-path-only gap (audit Note-2) for the guard, in the discipline of D-020; an attack without a story is not adversarial | `fixtures/tla_counterexamples.json` (G-1..G-8); `tests/test_counterexamples.py` |

## Law amendments bundled with this batch

- **L-9 scope note**: semantic topic-lock's consent valve is extended to
  response suppression (collapse-seal) and to the sidecar sensor. Still
  off by default; still cold-state consent; the arming emits
  `guard_sidecar_armed`.
- **Proposed L-10** (draft): "Content may be measured for scope, never
  graded for quality; suppression may hide, never punish." With a test:
  the sidecar verdict schema carries no quality dimension
  (`TestVerdictFusion` + `test_malicious_payload_failsafe`).
- **L-8 remains spec'd-not-tested** in the house table — closing it is
  still owed and is NOT claimed by this kit.

## Explicitly refused by this batch (inversion-catalogue entries)

- Streak counters / praise lines in the guard card (fails L-2).
- Unbounded debt (fails L-5).
- Motivational copy in the hold card (fails L-1).
- Sidecar autonomous denial (fails the D-014 reading; escalation-only).
- Canary *temptation* objects (manufacturing traps for oneself fails the
  shame-safety spirit even when it passes the lint).

## Batch addition — D-090 (post-batch, serendipity as measurement)

| ID | Decision | Rationale | Test / check |
|---|---|---|---|
| D-090 | Serendipity machinery (Thompson/UCB1/MMR/entropy slot) enters as measurement instrumentation inside the D-071 reveal container, not engagement optimization: reward = resolution (promote/release), ignored = failure, hook-back = harm; bandit chooses WHICH item only — never WHEN or HOW MANY (fixed cold-state budget); propensity logged per arm-pull for off-policy analysis; disarmed in Phase 0, frozen in Phase 2; stdlib formulas in-tree, non-stdlib recommender tooling rejected (L-8) | Platform exploration math inverts cleanly: bait -> probe; adaptivity inside an N=1 experiment is an adaptive confounder unless propensities are logged; variable-ratio reveal streams are a slot machine unless caged by the D-071 container | `dhriti_reveal_policy_reference.py` behavior checks [1]-[5] (buried-item surfacing, MMR curation 0.78->0.26, learning r, budget ceiling, ledger lines) |
