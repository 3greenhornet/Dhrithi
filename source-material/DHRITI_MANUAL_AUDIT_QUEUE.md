# DHRITI — Manual Audit Queue

Use this as a working checklist. Record the exact release/commit, environment, test steps, measurements, source paths and results. A README feature claim is not proof.

## A. Highest-priority controlled experiments

### 1. Focuser — source audit and Windows trial
- [ ] Record current release tag, commit SHA and release artifact hashes.
- [ ] Read the licence and check dependencies/embedded components.
- [ ] Inspect installer, scheduled task, service, elevation and persistence code.
- [ ] Find the actual website blocking mechanism and actual desktop app restriction mechanism.
- [ ] Determine whether app blocking is process termination or true launch prevention.
- [ ] Inspect browser native messaging and permission scope.
- [ ] Inspect policy/lock implementation and how a user can change or remove it.
- [ ] Inspect restart, sleep, hibernate, shutdown and recovery handling.
- [ ] Investigate Defender detection report and current status; never disable Defender for the test.
- [ ] Build from source in a VM/standard-user test account and compare to release artifacts.
- [ ] Measure CPU, RAM, disk and event/log growth.
- [ ] Produce a report: run / wrap / fork / adapt / study / reject.

### 2. FocusMe vs Cold Turkey
- [ ] Identify exact versions and trial/plan limitations.
- [ ] Test app allowlist with IDE, terminal, browser and PDF reader.
- [ ] Test scheduled block and locked/enforced mode.
- [ ] Test whether a running block can be stopped, weakened or uninstalled.
- [ ] Test already-open tabs, another browser, portable browser, VPN and alternate DNS.
- [ ] Test sleep, hibernate, reboot and offline conditions.
- [ ] Inspect supported CLI/plan import or API; automate only documented interfaces.
- [ ] Record what is observed vs what is merely advertised.

### 3. Plucky / Pluckeye
- [ ] Read official docs for delay, lockdelays, future queue and app/user/host rules.
- [ ] Test only in disposable configuration, starting with a short delay.
- [ ] Add an allow rule and inspect the delayed state.
- [ ] Attempt to shorten the delay and inspect expected behavior.
- [ ] Test restart, service failure, uninstall and admin boundary.
- [ ] Determine what status can be queried programmatically.
- [ ] Record whether a Dhriti adapter is possible without unsupported UI automation.

### 4. Safe Exam Browser
- [ ] Download current Windows version from official source.
- [ ] Inspect SEB configuration tool and sample configuration.
- [ ] Test kiosk desktop in disposable standard Windows account/VM.
- [ ] Launch VS Code, terminal, browser, PDF reader as permitted apps.
- [ ] Test ALT+TAB, Windows key, Task Manager, Explorer, Ctrl+Alt+Del and app exit.
- [ ] Test admitted app filesystem/network access; document boundary.
- [ ] Inspect source/licence of each binary/module, especially security module.
- [ ] Determine whether external apps and browser are stable enough for a coding workspace.

## B. Observation stack

### 5. ActivityWatch vs Focusd vs minimal native observer
- [ ] Verify exact Focusd repository URL, maintainer, licence and latest commit.
- [ ] Run ActivityWatch with only needed watchers.
- [ ] Verify browser title/URL fields, foreground app fields, timestamps and local API.
- [ ] Compare data gaps, polling cadence and CPU/RAM/disk impact.
- [ ] Test multiple monitors, virtual desktops, multiple Windows accounts and browser profiles.
- [ ] Choose one primary observer; don't duplicate overlapping histories without reason.

### 6. Sysmon Modular
- [ ] Install Sysmon in a disposable environment.
- [ ] Start with narrow Process Create/Terminate, DNS and Network Connect events.
- [ ] Include process GUID/parent GUID correlation.
- [ ] Compare event logs against actual process launches.
- [ ] Measure log volume over one workday.
- [ ] Review Sysmon Modular config and choose only relevant rules.
- [ ] Avoid verbose research profile continuously unless storage cost is justified.

### 7. Screenpipe
- [ ] Check current licence and what is open-source vs commercial/source-available.
- [ ] Run 60–90 minutes with minimum capture sources.
- [ ] Measure CPU, RAM, GPU use (if any), disk write rate and database growth.
- [ ] Inspect OCR/accessibility, app-switch events, query API and export schema.
- [ ] Compare its additional value against ActivityWatch + Sysmon + browser/IDE events.
- [ ] Decide whether to keep as optional Research tier only.

## C. Offline analysis and model research

### 8. PM4Py proof of concept
- [ ] Create synthetic CSV with `case_id`, `activity`, `timestamp`, `source`.
- [ ] Include a direct work path, legitimate research path and avoidance branch path.
- [ ] Import log and generate directly-follows graph/process variants.
- [ ] Check whether discovered graph matches the intended trace.
- [ ] Export one real anonymized/personal session and manually validate it.
- [ ] Record package version, runtime, dependencies and output artifact.

### 9. Task-aware semantic models
- [ ] Build manually labelled examples before selecting a model.
- [ ] Include necessary dependency research, related-but-unnecessary tutorials, unrelated topics, setup, offline work and ambiguous events.
- [ ] Compare deterministic rules vs MiniLM vs BGE/Qwen embedding vs EmbeddingGemma 2 (if supported).
- [ ] Measure precision/recall, false-block cost, latency, RAM and model size.
- [ ] Test same content under different task profiles.
- [ ] Do not turn similarity scores directly into policy without a validated calibration.

## D. Cross-domain exploration

### 10. Industrial interlocks / formal methods
- [ ] Translate contract lifecycle into states, transitions and invariants.
- [ ] Model emergency override, policy relaxation, arming failure and reboot in TLA+.
- [ ] Model-check finite state space with TLC.
- [ ] Map “maintenance bypass” to Dhriti recovery/emergency design.

### 11. JITAI / HeartSteps methodology
- [ ] Read original protocol/paper rather than relying only on app repo.
- [ ] Define decision points and proximal outcomes for Dhriti.
- [ ] Decide which optional intervention can be randomized without changing core safety restrictions.
- [ ] Plan for carry-over effects and comparable task sessions.

### 12. Browser interface inversions
- [ ] Try Purpose Mode / Unhook / Intentional YouTube.
- [ ] Record exactly which UI elements are removed and which site functions remain.
- [ ] Test task-specific research profile rather than global website block.
- [ ] Check extension licence, maintenance and content-script breakage.

## E. Result template — use for every candidate

```text
PROJECT / VERSION / COMMIT:
ENVIRONMENT (Windows version, account type, hardware):
CLAIMED CAPABILITY:
SOURCE FILES / CONFIG LOCATIONS:
ACTUAL MECHANISM OBSERVED:
CLI / API / IPC:
PRIVILEGES / SERVICE / DRIVER:
LICENCE / COMPONENT EXCEPTIONS:
CPU / RAM / STORAGE MEASUREMENTS:
TEST STEPS:
EXPECTED RESULT:
ACTUAL RESULT:
BYPASSES / FAILURE MODES:
WHAT CAN BE REUSED:
WHAT MUST BE PERSONALIZED:
INTEGRATION OPTIONS: run / wrap / fork / adapt / study / reject
CONFIDENCE: verified / partially verified / unverified
NEXT TEST:
```
