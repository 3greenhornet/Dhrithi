# MINING_AUDIT.md — what I used from your raw material, item by item

You asked: *did I actually use the ideas and resources you provided as
raw information — or the intentions behind them?* The honest answer is
**both, but at different layers — and v1 missed a few things that v1.1
now closes.** This file is the proof, item by item, so you can falsify
me: every claim has a file, a test, or a named refusal. Refusals are
also uses — your project's culture (reference §1.3 "considered, then
refused") treats a documented refusal as an asset.

The distinction that matters:

- **USED-AS-MECHANISM** — the thing itself was transplanted (trapped-key
  → thread interlock; Schmitt trigger → taper; anti-windup → debt).
- **USED-AS-INTENT** — the *purpose* was kept but the mechanism differs
  (Purpose Mode removes infinite scroll structurally → here, the length
  governor caps response length structurally; Scroll Debt's physical
  bypass cost → here, expand-with-toll).
- **REFUSED** — would break a law or the house architecture; recorded
  with the reason.
- **NOT-THIS-KIT** — belongs to another subsystem (Vidura, mirror,
  mobile) and was left untouched on purpose.

---

## 1. The intentions layer (the laws) — these bound every mechanism choice

| Your intention | How it bound the kit |
|---|---|
| L-1 Wall Principle | Hold card states facts and stops; no "next interaction" affordances; collapse-and-seal instead of blur (a blur invites squinting past the wall) |
| L-2 Shame-safety | Card lines are factual; no streaks, no praise; `test_card_lines_lint` enforces; canary *temptation* objects explicitly refused in `D_DECISIONS.md` |
| L-3 Config immutability | All knobs live in `DEFAULT_CONFIG` additions, sealed cold; runtime `GuardState` is state, not config |
| L-4 Content-blind | `chat_guard.py` accepts **no text** — only counters, timestamps, verdict codes; text never crosses the bridge; verified by module-level design + tests |
| L-5 Bounded release | Every budget/debt/toll has ceiling+expiry; `DebtIsBounded` and `NoSilentAllowOnBurst` counterexamples prove it adversarially |
| L-6 Cold-state consent | Sidecar off by default; arming emits `guard_sidecar_armed`; enablement order in `INTEGRATION_MAP.md` §10 |
| L-7 Faced record | Overrides recorded (`record_override`), honored delays recorded (`honored_delay: True`, your break-glass honesty), digest block shows the guard's failures with the same honesty as yours |
| L-8 bounded-not-optimized | Not claimed closed — flagged as still owed in `D_DECISIONS.md` (no kit credit taken) |
| L-9 valve | The entire sidecar exists under this valve: off by default, cold consent, escalate-not-decide |
| D-014 (no LLM in enforcement) | The sidecar is a SENSOR, not a judge: `decide()` bounds its power to the mode floor; `SidecarCannotUndercutDeterministicFloor` counterexample proves it |
| "The jolt is the intervention" (your pushback) | Collapse-and-seal and hold cards ARE the jolt — the response exists, is parked/sealed, and costs a toll to surface; frustration budget respected via ADVISORY default mode |
| "Escalate-not-decide" (agreed design) | Sidecar verdict can park/hold/collapse at the mode floor; silent denial is structurally impossible |

## 2. The mechanisms layer (the ideas, transplanted)

| Your raw mechanism (source in your reference) | Landed as | Proof |
|---|---|---|
| Trapped-key interlock (industrial safety, §20) | Thread interlock: disposal of thread N is the key to thread N+1; pivot budget per mode | `chat_guard.can_open_thread`, D-082, counterexample G-5 |
| Schmitt trigger (control engineering, §20) | Asymmetric taper: breach tightens immediately, down_days clean streak to relax | `chat_guard.schmitt_step`, D-078, G-1/G-2 |
| Anti-windup (control engineering) | Debt accrual freezes under FULL_LOCK | `chat_guard.accrue_debt`, D-079, G-4 |
| Sensor disagreement as signal (SIEM thinking, §20) | ActivityWatch browser-minutes vs extension nav events → `guard_sensor_conflict` | `guard_metrics.sensor_conflict`, `observer_crosscheck`, D-080 |
| Canary tokens (security, §20) | E2 DNS canary + per-adapter DOM canary + (v1.1) hosts-list bypass audit + (v1.1) Cold Turkey rename-bypass canary | `canary.py`, `external_cli_probe.py`, D-081/D-087/D-088 |
| Kill chain staging (security, §20) | urge→open→navigate→type→send→read attribution | `guard_metrics.kill_chain_attribution` |
| Process mining / conformance (PM4Py, §3/§20) | Contract-as-normative-model, token-replay intent; stdlib check default, PM4Py optional offline | `conform.py`, D-083 |
| CT-style witness verification (your CT-14/17 notes) | Witness stores anchors only; segment recomputation proves a day in-chain without content trust | `anchor_proof.py`, D-084, `TestAnchorProof` |
| Near-miss pyramid (safety) | park:break ratio in digest; falling parks + steady breaks = routed around | `guard_metrics.park_break_ratio`, D-085 |
| EDRR / novelty detection | Novel domain ≥ K → same-day reclassify queue event | `guard_metrics.novelty_domains`, D-086 family |
| Goal-gradient effect (behavioral) | "Pass budget: N remaining" factual line on hold cards | `chat_guard.budget_line` |
| Purpose Mode (CMU, §5) | Length governor: structural cap on response tail, expand-with-toll | `chatguard_content.js::lengthGovernor`, D-073 |
| Scroll Debt (§3.2) | Same bypass-cost logic as the expand toll | D-073 rationale |
| Grüning 10-second delay (§3.1) | Toll defaults (10 s hold; your 60 s break-glass already validated it) | `BurstConfig.toll_s`, D-072 |
| Lu et al. InterOut (§3.1) | Hold+toll+park over hard block; retrieval preserved under seal | D-071/D-076 design rationale |
| "Old Habits Die Hard" (ICML 2026, §3.2) | Topic-lock must be structural → transcript-diff as source of truth, not button interception | `chatguard_content.js` design note |
| "Alignment Drift … drift appears as continuity" (§3.5) | Running centroid from the pass's own earlier prompts as a drift anchor | `embedding_axis.running_centroid` |
| TalkMoves / MIDAS / DeBERTa (§3.2/§3.5) | Function axis model slot, `cltl/DialogAct` default, label→P-code mapping | `function_axis.py`, D-074 |
| Embedding candidates: MiniLM/BGE/Qwen3/EmbeddingGemma (§1.2) | Backend slot + `dhriti embed-eval` to pick on YOUR coded specimens, not MTEB | `embedding_axis.py`, INTEGRATION.md §7 |
| `context-drift-analyzer`/`topicality`/`causantic` (§3.5) | Intent captured locally; the DEPENDENCY refused (stdlib core stays clean) | `running_centroid` + this row |
| JITAI decision points (HeartSteps, §2.2) | Mode→aggressiveness mapping table (D-076) is a deterministic decision-point table; micro-randomization refused (violates determinism) | `MODE_POLICY` |
| Fastembed-rs caveats (§8: ORT_DYLIB_PATH pin, cache-to-datadir, corrupt-cache quarantine) | Recorded for the future Rust/Tauri port; Python sidecar unaffected (quarantine pattern already yours via D-064) | this row |
| Content TTL + purge ("delete from time to time") | Raw text lives ONLY in sidecar with `raw_text_days=14`; purge emits `guard_content_purged`; chain keeps {hash, verdict, action, latency} | `content_store.py`, `retention.py`, D-075, `test_no_hash_chain_columns` |
| Burst detector ≥3/10min (your live D-057) | Reused verbatim as the L-4-pure rate governor, timestamps only | `burst_toll_active`, D-072 |
| Parking lot machinery (your v0.6.0) | Guard output lands in the EXISTING bounded pipeline (D-071), sparked-by lineage preserved | `/guard/park` handler |
| Recall-before-reveal (your mirror) | Parked prompts surface at cold state after recall step | D-071 rationale |
| P-codes as reference vocabulary (your D-043) | P-codes become the LIVE verdict language shared with cold mining | `function_axis.map_model_label`, D-074 |
| MV3 constraints (30 s worker, alarms ≥0.5 min, §5) | Guard background uses its own 1-min alarm; content script self-polls; TTL-gated state | `chatguard_background.js` |
| ActivityWatch PR #561 + long-query 503 (§2) | **v1.1**: `aw_quality_hint` maps the zero-duration signature to SUSPECT, poll failure to MISSING | `observer_crosscheck.aw_quality_hint`, `test_v1_1_additions` |
| Sysmon Event 1 vs Security 4688 lineage (§2) | **v1.1**: `lineage_conflict()` records `guard_lineage_conflict` on disagreement; ProcessGuid-not-PID rule carried in the note | `observer_crosscheck.lineage_conflict` |
| Cold Turkey CLI v4.9 flags + rename bypass (§1) | **v1.1**: audit-gated CLI probe + bypass canary on `ServiceHub.*`/`CTMsgHost*` presence | `external_cli_probe.py`, D-088 |
| CVE-2026-17923 exact-match bypass (§5) | **v1.1**: `audit_hosts_entries` flags non-blackhole IPs, www gaps, punycode, trailing dots, conflicts → `guard_e2_block_bypass_risk` | `canary.py`, D-087 |
| TLA+ counterexample discipline (D-020, Note-2) | **v1.1**: 8 adversarial traces with attack stories, replayed by a generic runner | `fixtures/tla_counterexamples.json`, `tests/test_counterexamples.py`, D-089 |
| TL;DR: golden-day-only testing | Same as above — the guard now has an adversarial fixture set | as above |

## 3. Full-sweep disposition (everything else in your 1,260-line reference)

**REFUSED, with the reason (these refusals are load-bearing):**

- Screenpipe for the guard — a screen-OCR sensor would read content
  around the L-9 valve; the page-level sidecar already has exactly the
  content needed. Trial protocol unchanged (Phase 8, D-011).
- Beeminder / Focusmate in the enforcement path — external dependency
  in the loop violates local-first and D-014's spirit; named-hole
  honesty stays.
- freelm (API routing) — never critical path; the sidecar is
  local-only by contract.
- Native messaging — your D-025 already resolved HTTP-bridge-default;
  the guard rides the same bridge.
- Portmaster/WFP kernel filtering — wrong layer for chat; E2 hosts +
  canaries cover the DNS half.
- OPA, WXT, Electron, Next/React, FastAPI-in-enforcement — all re-
  refused for the same reasons your §1.3 records.
- Micro-randomization / bandits (JITAI's experiment half) — violates
  determinism; the deterministic mapping table keeps the intent.
- Streak counters, praise lines, motivational copy, temptation canaries
  — refused in `D_DECISIONS.md` (fails L-1/L-2/shame-safety spirit).

**NOT-THIS-KIT (owned by other subsystems, untouched on purpose):**
FSRS/SM-2 (Vidura), YouTube OAuth/mirror, Vidura ingest rules, the
stack adapters (NextDNS/Foqos/Unhook/Brave/AppLock — already v0.6.0),
SEB/WDAC/AppLocker/Chrome-policy guides (E3), SMS-gateway OTP
(break-glass tiers, v0.6.0), Android/iOS (named hole), Tauri/Rust port
(VERSION_PINS), Playwright E2E, SQLCipher, pm4py-mcp (Phase 8),
ENA/TNA/SPM/changepoint (cold analysis layer — the conformance view is
this kit's stdlib sibling), B-9..B-12 repo bugs (yours to fix in-repo),
Forgejo, OpenWrt, Nudge/AddictionBuster, AWARE.

**USED-AS-CONTEXT (calibration, shaping honesty rather than code):**
Klingelhoefer β≈-0.07 (observational → digest lines say "association"),
JMIR "81% total-time" (→ guard is activity-specific), GenAI pilot
43.1% unwanted effects (→ guard must stay escapable: override + park
always available), Kidman abandonment (→ advisory-first default),
Forman MI ≈0 (→ no motivational copy), "Study More Tomorrow" (→
precommitment humility in enablement order), Purpose Mode N=29
small-sample caution (→ structural cap is config, revisable cold).

**Named in your reference as existing already** (your repo, no kit
action needed): pre-send hold, 600 ms debounce hide, park button,
legitimate pivot declaration, prompt budget 15/pass, `/session/topic`,
chip suppression (D-032), selector staleness in health, `dhriti
reclassify`, Absence Test — the kit CONSUMES these rather than
rebuilding them.

## 4. What v1 missed and v1.1 closed (the audit's findings)

Being straight with you: v1 used the *core* of your pile (the guard
design, the mechanisms in §2 up to canaries) but under-mined three
corners — the observation-tools trivia (AW bugs, 4688 lineage), the
enforcement-tools facts (Cold Turkey CLI + rename bypass), and the
CVE note. Those were in your raw material with enough precision to
build from, and v1 left them as prose. v1.1 turns each into tested
code (rows marked **v1.1** in §2, decisions D-087/D-088/D-089, 28 new
tests, suite now 78/78 green). One wiring bug was also found and fixed
by auditing your real code (`ledger.append` → `Ledger.record` adapter,
`_send` helper, `BoundHandler` context pass-through — see
`INTEGRATION_MAP.md` §0).

## 5. How to falsify this audit

Pick any row in §2, open the named file, and check the claim; pick any
REFUSED row and check it against your laws; pick any NOT-THIS-KIT row
and check it belongs to another subsystem. If a row's "where" is wrong
or a refused item should have been used, that's a real gap — the same
standard your own audit culture applies (B-1..B-12 were found exactly
this way).
