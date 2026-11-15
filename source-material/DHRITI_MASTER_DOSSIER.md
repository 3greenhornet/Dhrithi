# DHRITI — Research, Architecture and Planning Master Dossier

**Version:** 0.1 (research consolidation)  
**Snapshot date:** 30 October 2026  
**Purpose:** Preserve the current research direction, design decisions, hypotheses, alternatives, source leads, unresolved questions and manual audit work so future work does not restart from scratch.  
**Status:** Research baseline / decision preparation. Not a build-ready technical specification.

---

## 0. Read this first: what this archive does and does not preserve

This bundle contains:

1. `PROJECT_DHRITHI_ORIGINAL_UNMODIFIED.pdf` — byte-for-byte copy of the supplied 95-page source PDF.
2. This master dossier — a consolidated, traceable research and design record of the work discussed in the conversation.
3. `DHRITI_SOURCE_REGISTER.csv` — links and manual verification tasks.
4. `DHRITI_DECISION_REGISTER.csv` — current recommendations, confidence and unresolved decisions.
5. `DHRITI_MANUAL_AUDIT_QUEUE.md` — concrete outside-chat investigation instructions.
6. `CHAT_TRANSCRIPT_PRESERVATION.md` — instructions for attaching a verbatim ChatGPT export.

**Important transcript limitation:** this dossier is not a word-for-word transcript of the entire chat UI. It preserves the substantive findings, candidate mechanisms, reasoning, corrections, decisions and next actions available in the current conversation context. To satisfy a literal “not lose a word” requirement, export the conversation from ChatGPT and place the raw export in this bundle. Do not replace the original PDF or raw transcript with a summary. The raw sources and this dossier serve different purposes.

### Provenance labels used throughout

- **[PDF]** Directly described in the original Project Dhrithi PDF.
- **[WEB-2026]** Found in web research performed for this conversation, snapshot date above. Verify live status before acting on release-sensitive details.
- **[INFERENCE]** A design conclusion or proposed inversion derived from the sources; not a claim made by the source itself.
- **[UNVERIFIED]** Candidate capability or integration that must be tested in source, documentation or a controlled environment.
- **[DECISION]** Current recommended direction, still subject to the manual audit gates.

---

# 1. Project intent and constraints

## 1.1 What Dhriti is trying to do

Dhriti is a personal execution and self-regulation experiment, primarily for its creator, not a commercial product or a public productivity brand. It aims to externalize precommitments and shape the computing environment so that ordinary impulses cannot casually redirect a person away from chosen work.

The intended operating loop is:

1. **Cold-state intention:** define an obligation, outcome, next physical action, permitted resources, evidence and exit conditions before the period of temptation.
2. **Environment preparation:** prepare the relevant workspace and activate restrictions selected in advance.
3. **Execution:** make the chosen work the easiest available activity, while retaining bounded paths for legitimate dependencies and emergencies.
4. **Observation:** record what actually happened, with event provenance.
5. **Evaluation:** compare commitment, activity, evidence and outcome; distinguish observed facts from interpretations.
6. **Adaptation:** change future contracts based on accumulated evidence, not momentary bargaining during an active commitment.

The core is not “an AI that tells me to focus.” It is a system combining precommitment, environmental restrictions, task initiation, evidence capture and longitudinal investigation.

## 1.2 Key philosophy from the original PDF [PDF]

- The **Audience vs Stage** metaphor distinguishes passive absorption/discussion/planning from producing an artifact or meaningful work.
- The **Avoidance Loop**: obligation → difficult first action → plausible detour → justification → execution displaced → regret/analysis → repeat.
- The **Wall Principle**: during strict enforcement, avoid conversational engagement surfaces, explanations, personality, argument and in-the-moment negotiation.
- **Commitment precedes temptation**: contracts are written in a cold state and sealed before active enforcement.
- **Observation / inference / enforcement are separate**: the contract is authoritative; an uncertain classifier cannot invent or escalate policy.
- **Evidence is task-specific**: failed tests, debugging, notes, drafts and other genuine attempts may count; elapsed time alone is not proof.
- **Tamper-evident, not unbreakable**: record interruption and bypass honestly; do not claim the owner cannot disable software on their own machine.
- **Graduation**: the long-term aim is to make the tool less necessary, not create permanent dependency.

## 1.3 Personal-project constraints clarified by the user

- Personal experimentation is the primary purpose; no commercial positioning or marketing requirements.
- The user is comfortable with personal activity data being captured for the experiment. Do not over-optimize the architecture for public-facing privacy assurances.
- Data collection should nevertheless be purposeful, inspectable and locally controlled. Personal tolerance for recording does not imply every sensor is useful or every third-party upload is acceptable.
- CPU, RAM, GPU and storage are constrained. The system should demonstrate mechanisms on modest hardware first, then allow higher-capability modules to be added later without rewriting the core.
- Ambitious or difficult mechanisms are acceptable if the mechanism is worth testing. Use smaller substitutes or simulations where the full system is too heavy.
- Reusing or inverting an existing mechanism is preferred over rebuilding a specialised capability poorly.
- Manual investigation outside the chat is explicitly welcome. Search results and assistant summaries are not substitutes for reading source code, running a project, inspecting issues, testing configuration and measuring actual resource use.
- The user wants a durable record so future work does not repeat searches or lose why a technology was considered.

---

# 2. Audit of the original 95-page PDF

## 2.1 Strengths to preserve

1. Cold-state commitment and sealing.
2. Deterministic restrictions that do not depend on AI availability.
3. Separate observation, inference and enforcement.
4. Task-specific proof and explicit provenance.
5. Honest handling of missing telemetry, interruption and bypass.
6. A parking/deferred mechanism for unrelated curiosity, provided it remains low-friction and does not become a new engagement loop.
7. Dynamic, bounded research exceptions tied to an actual obstacle.
8. Manual labeling and false-positive testing before strict semantic decisions.
9. A local event ledger and modular adapters.
10. Evidence-based review and possible graduation.

## 2.2 Contradictions to resolve in a v2 specification

| Topic | Conflicting descriptions in the PDF | Required resolution |
|---|---|---|
| Day release | Fixed end time; unlock when task is complete; remain locked beyond day-close if incomplete | Define one fixed maximum release rule plus any explicitly precommitted early-release condition. Do not allow accidental indefinite extension. |
| Session vs day | Session is sometimes the success/failure unit; elsewhere the whole day-window is the enforcement boundary | Define commitment period as policy container; task/work blocks are children unless the user chooses otherwise. |
| Wall vs intervention | Wall forbids messages/checkpoints; detector proposes return-to-task prompts and dispute flow | Define strict-mode UI and permitted system surfaces. Silent block should not mean essential recovery UI is absent. |
| Network proxy | Described in early architecture; rejected for v1 later | Remove from initial build unless a specific later experiment justifies it. |
| Privacy/API | Some sections say API opt-in; another says API by default | For personal experiment, make data routing explicit per provider and per source. Avoid accidental uploads. Local-first remains a simple default, but user may deliberately enable a remote experiment. |
| Graduation | Manifesto says no taper; architecture proposes evidence-based taper | Keep graduation as a long-term experiment, not a prevalidated 30/60/90-day guarantee. |
| Proof | Screenshot/vision workflow is sometimes treated as verification | Evidence classes must remain distinct: observed, user-submitted, and machine-checked. A model description is not independent proof. |
| Enforcement | Browser blocks, OS app controls, network filtering and tamper resistance are treated as one wall | Specify separate capabilities and explicit enforcement levels. |

## 2.3 Previous assistant recommendations corrected or qualified

- **Focuser:** very promising fit, but do not adopt solely from its README. A Windows release had a Defender machine-learning detection report; this is not proof of malware, but warrants source/build/release verification and a controlled test. Do not disable Defender to install it.
- **Digital Habits: Blocker:** useful research-oriented design reference (Focus Spaces, stop-early/override and scheduling), but its Windows enforcement should not be mistaken for strong OS-level lockdown. Verify repository licensing before copying code.
- **FocusMe / Cold Turkey / Freedom:** use as commercial black-box benchmarks or personal backends, not automatically as dependencies. Verify documented CLI/API integration and actual bypass behavior.
- **Plucky/Pluckeye:** promising delayed-access-relaxation mechanism, but proprietary. Evaluate as an installed backend, not something to fork. Test the CLI, delay semantics, administrative boundaries and recovery.
- **ActivityWatch:** promising observation provider; do not run overlapping trackers without a clear need. Compare its current API and browser watcher with a minimal native observer.
- **Tauri 2 + Rust + SQLite + WXT:** reasonable target architecture, but not a reason to rewrite an existing working prototype immediately. Use only after the component audit proves what is missing.
- **FastEmbed / MiniLM / BGE / Qwen embeddings / EmbeddingGemma 2:** candidates for experiments, not committed model decisions. Benchmark against Dhriti-specific labels. Embedding similarity is not a measure of motivation or procrastination.
- **Screenshot → vision model → text evaluator:** optional experiment only; it cannot establish authenticity, effort or quality on its own.
- **freelm:** the PDF's Rust-style use of the package was conceptual, not a verified Rust integration. Keep model routing behind a provider abstraction; do not make external API availability a core dependency.
- **Sysmon:** valuable process and system-event telemetry, not a complete view of foreground attention or webpage content.
- **Safe Exam Browser:** promising kiosk/workspace inversion, but its permitted applications are not thereby fully network-contained. A restricted desktop is not the same as whole-device application/network isolation.

---

# 3. Revised mental model and architecture

## 3.1 Do not organise the system around products

Organise the specification around capabilities. Products and repositories are replaceable providers.

| Capability | Responsibility | Candidate providers / implementation |
|---|---|---|
| Commitment authority | Contract, cold-state seal, review schedule | Custom Dhriti core |
| Workspace ignition | Open right project, files, terminal, work profile | Custom PowerShell first; later Rust/Tauri |
| Website restriction | Block selected websites/URLs | Focuser, FocusMe, Cold Turkey, Plucky, Chrome policies, extension |
| Application restriction | Prevent or close selected applications | AppLocker/App Control/Assigned Access; FocusMe/Cold Turkey; Focuser audit |
| Network restriction | Filter network by application/domain/time | Plucky, Portmaster, Windows Filtering Platform, router |
| Restricted desktop | Kiosk/allowlisted environment | Safe Exam Browser, Assigned Access |
| Activity observation | Window/process/browser events | ActivityWatch, Sysmon, Focusd, Screenpipe, custom small observer |
| Task evidence | Save/test/terminal/Git/document events | VS Code Extension API, Git, shell hooks, manual submission |
| Event lineage | Connect parent/child navigation and obstacle chains | Custom Dhriti event model |
| Historical analysis | Discover repeated routes and bottlenecks | PM4Py, SQL, Python statistical analysis |
| Semantic analysis | Interpret ambiguous content relative to task/dependencies | Rules, FastEmbed, Qwen/EmbeddingGemma, optional LLM |
| Formal policy testing | Check lifecycle invariants | TLA+/TLC, property-based tests, integration tests |
| Intervention research | Compare mechanisms and timing | N-of-1 / micro-randomized methods |

## 3.2 Architectural separation

**Stable core:** contracts, schedule/state machine, policy authority, normalized events, capability registry, evidence schema and experiment metadata.

**Replaceable adapters:** enforcement providers, activity observers, IDE/browser connectors, model providers and evidence providers.

**Offline research layer:** reconstruct event sequences, process mining, manual labels, statistics and model experiments. It must not sit in the real-time critical enforcement path.

Suggested flow:

```text
Cold-state contract
        |
        v
Policy snapshot + workspace plan
        |
        v
Capability check / enforcement arming
        |
        v
Active commitment  <---- event adapters (browser / OS / IDE / network)
        |                         |
        v                         v
Deterministic policy        normalized event ledger
        |                         |
        v                         v
Restriction backend        offline reconstruction
        |                         |
        v                         v
Completion / interruption   PM4Py + statistics + manual labels
        |                         |
        +-----------> cold review / next contract
```

## 3.3 Enforcement levels must be explicit

- **E1 — Browser-level:** extension and browser policies. Does not control other browsers/apps.
- **E2 — Application/network controls:** per-app firewall, process restriction, hosts/DNS or OS policies. Each mechanism has a specific boundary.
- **E3 — Restricted user/workspace:** separate standard account, kiosk/restricted desktop or managed policy administered outside the active user context.
- **E4 — External authority:** trusted person holds administrative credentials or network/router control; materially changes the user's ability to relax restrictions.

No level is “unbreakable” when the person retains full administrative control of the machine. Record which level is active and which bypass routes remain.

## 3.4 Work states and session lifecycle

Avoid mixing activity states with authority states.

Suggested lifecycle:

```text
DRAFT -> SEALED -> ARMING -> ACTIVE
                         |       |
                         |       +--> SUCCESS
                         |       +--> INCOMPLETE
                         |       +--> BREAK_GLASS
                         |       +--> INTERRUPTED -> RECOVERY / REVIEW
                         +--> ARMING_FAILED
```

Within ACTIVE, observations may classify activity as `ON_TASK`, `PERMITTED_RESEARCH`, `OFFLINE`, `UNKNOWN` or `UNCLASSIFIED`. These are observations, not new authorities.

An `ARMING` gate is important: do not represent a session as restricted until each required backend confirms its actual state. Unsupported or unavailable capabilities must be disclosed in the experiment record.

## 3.5 Closed-world vs bounded-research modes

- **Closed-world mode:** explicit allowlist, deterministic. Good for known work environments and strict sessions.
- **Bounded-research mode:** predeclared research sources, dependency chain, finite resource allowance and expiry/return conditions.
- **Open exploration mode:** allowed only when explicitly selected in a cold-state contract; should not silently become the default during a strict production task.

Do not collapse all three into a single semantic score.

---

# 4. Research and mechanism inversion across domains

The search strategy must not be limited to products marketed as focus/procrastination tools. Search for underlying mechanisms in unrelated domains, then test whether their mechanism maps onto Dhriti.

## 4.1 Inversion catalogue

| Original domain / resource | Original problem | Mechanism to borrow or invert for Dhriti | Fit / caution |
|---|---|---|---|
| Industrial safety / trapped-key interlocks | Prevent unsafe machine sequences | Arming, interlocks, controlled reset, maintenance bypass, safe-state transitions | Strong conceptual fit; implement as software state/authorization, not physical hardware |
| Cybersecurity / Sysmon / SIEM | Detect and reconstruct suspicious activity | Process provenance, parent-child events, timeline correlation, configuration tamper observations | Strong observation fit; cannot infer motive or foreground attention alone |
| Business process mining / PM4Py | Discover and compare organizational workflows | Discover personal avoidance routes, sequence variants, conformance to intended workflow | Very strong offline research fit |
| Digital forensics / Screenpipe | Reconstruct computer use and context | Searchable historical view of task/diversion sequence | Rich but potentially high CPU/RAM/disk; test short session first |
| Exam lockdown / Safe Exam Browser | Restrict exam environment | Repurpose kiosk/restricted desktop as work environment | Useful workspace isolation; not full network containment |
| Network security / Portmaster / Plucky / WFP | Restrict application traffic | Enforce per-application access and delayed relaxation | Clear boundaries; not content understanding or app launch control |
| DevOps/GitOps / OPA | Prevent unsafe/unauthorized production changes | Versioned sealed policy, validation, controlled relaxation and audit | Strong policy-design fit; OPA may be unnecessary runtime weight |
| Formal methods / TLA+ | Find concurrency/state-machine flaws | Model session states, emergency route, reboots, policy changes and adapter failure | High value; development-time only |
| Digital health / HeartSteps / JITAI | Select intervention based on context and test effects | Randomize optional start/return aids at defined decision points | Strong experimental methodology; do not copy health app stack |
| Behavioural economics / Beeminder | Precommitment with delayed pledge reduction | Delayed access-expanding changes; optional external milestones | Useful concept; financial commitment is optional and not necessary |
| Parental controls / Family Safety | Separate organiser and restricted user | Separate administrator and standard work account | Externalized authority; test OS edition/support and recovery |
| Recommendation-system design | Keep presenting next content | Invert into finite approved research set and suppress recommendation surfaces | Strong for rabbit holes; site adapters can break |
| Build systems / DAGs / workflow engines | Resolve task dependencies | Task → obstacle → dependency → source → finding → return | Strong alternative to global semantic similarity |
| Control engineering | Stabilize systems under noisy signals | Hysteresis, debounce, cooldown, sensor-failure detection, fail-safe states | Strong for avoiding oscillating interventions |
| Human factors / aviation | Manage cognitive load and alarm fatigue | Minimal interface, predictable controls, explicit failure states | Avoid creating a new engagement surface |
| Physical environment / body doubling | Create social/contextual commitment | Compare workspace, library, coworking and scheduled body-doubling | Low software cost; useful experimental condition |
| Router administration / OpenWrt | Time/device network access | Restrict entire device or selected devices during windows | Covers multiple devices on Wi-Fi; alternate networks remain |

## 4.2 Concrete inversions to test

### Safe Exam Browser -> work kiosk

- Inspect Windows kiosk desktop, command interception, permitted external applications, process configuration and quit controls.
- Test in disposable standard Windows account/VM.
- Determine whether it can reliably host VS Code, terminal, a browser and PDF reader.
- Explicitly test internet/filesystem access from admitted processes.
- It is a restricted desktop mechanism, not a complete network sandbox.

### Sysmon -> behavioural provenance graph

- Install/configure only the event types needed for a sample.
- Capture process creation/termination, parent process, command line and selected network/DNS events.
- Use Process GUID / parent GUID to correlate process lifetimes, not PID alone.
- Join with ActivityWatch/browser/IDE events to reconstruct `IDE -> browser -> search -> video -> IDE`.
- Avoid high-volume research configurations until storage impact measured.

### PM4Py -> avoidance-process discovery

- Export a synthetic event log with a `case_id` per commitment/session.
- Use event names such as `contract_sealed`, `workspace_opened`, `test_failed`, `browser_search`, `tutorial_opened`, `branch_opened`, `code_changed`, `test_rerun`, `milestone_completed`.
- Discover directly-follows graphs and process variants.
- Compare intended/expected sequences against observed ones.
- Keep this offline; do not run PM4Py in real-time enforcement.

### Screenpipe -> searchable activity history

- Run one 60–90-minute sample with only necessary capture sources.
- Measure CPU, RAM, disk growth and database size on actual hardware.
- Inspect OCR/accessibility/search capabilities and retention/export.
- Compare incremental value against ActivityWatch + Sysmon + browser/IDE events.
- Commercial License / source-available terms: inspect before copying or redistributing.

### Plucky -> delayed access-expanding policy changes

- Test only in a disposable configuration at first.
- Verify delay semantics, delayed rule changes, attempts to reduce delay, status/CLI output and restart behavior.
- Proprietary; evaluate as a black-box backend, not a fork target.

### Portmaster -> per-application network restriction

- Inspect WFP integration, service/API, app identification, rule lifecycle and interactions with VPN software.
- Determine whether an external controller exists and is stable.
- Do not confuse network restriction with process launch prevention or semantic web filtering.

### Digital health/JITAI -> intervention experiment

- Define decision points (e.g. contract start, first obstacle, first branch, return failure).
- Randomize only supplementary interventions while keeping required safety restrictions stable.
- Compare workspace launch, IF–THEN plan, bounded research pass and accountability/environment conditions.
- Measure meaningful task progress and artifact quality, not only time online.

### DevOps/GitOps -> sealed policy artefact

- Contract produces versioned immutable policy snapshot.
- Tightening may apply immediately if precommitted.
- Relaxation is delayed or requires separately authorized approval.
- Emergency path is always available and separately logged.
- Validate policy before activating a session.

---

# 5. Existing technologies, repositories and products to audit

## 5.1 Enforcement / restricted environment

### Focuser
- URL: https://github.com/aadeshrao123/Focuser
- Reported stack: Rust, Tauri 2, SQLite, WXT/TypeScript, native messaging, CLI/background service.
- Why it matters: unusually close architectural match; potential reuse instead of building blocker core.
- Audit: Windows service model, app closure vs actual launch prevention, locked list, scheduled task/elevation, restart/sleep recovery, extension disable, multiple browsers, hosts-file modification, CLI/API, SQLite ownership, event integrity, tests, license, release provenance, Defender detection discussion.
- Caution: an earlier Windows release was reported to trigger Microsoft Defender machine-learning detection. Not proof of malware; do not disable Defender. Verify current source/release/build/attestation and test in VM/standard account.
- Decision: top open-source candidate, not yet selected.

### Plucky / Pluckeye
- URL: https://docs.pluckeye.net/
- Why: delayed changes that increase access; rule-based network controls.
- Audit: delay, lockdelays, future queue, rule syntax, per-app/user/host support, admin boundary, CLI and scheduled changes, fail-open/fail-closed behaviour, removal/recovery.
- Caution: proprietary; not a forkable open-source foundation.
- Decision: black-box mechanism experiment.

### Safe Exam Browser (SEB)
- URLs: https://safeexambrowser.org/ ; https://github.com/SafeExamBrowser/seb-win-refactoring
- Why: kiosk/restricted Windows desktop, own desktop, admitted applications.
- Audit: SEB configuration tool, Windows kiosk implementation, admitted processes, shell/desktop management, process controls, service/dependencies, exit/quit model, licensing of each component.
- Caution: allowed applications are not necessarily prevented from accessing all files/network. Its security module may have different source/licensing status from the refactoring repo.
- Decision: high-priority manual experiment.

### FocusMe
- URL: https://focusme.com/windows/
- Why: Enforced Mode, cannot casually stop/loosen active plan, app/site blocking, schedules and CLI plan operations.
- Audit: actual CLI, plan file format, elevation/service behaviour, safe recovery, process/app controls, offline state, reboot and sleep, licensing/cost, logs.
- Decision: strongest commercial trial candidate, claims need hands-on test.

### Cold Turkey
- URL: https://getcoldturkey.com/
- Why: locked website/app blocks, Frozen Turkey, Micromanager app allowlisting, Writer mode, CLI operations.
- Audit: Micromanager with coding environment, CLI block activation, restrictions across browsers, sleep/reboot, bypass tests, licence/cost.
- Decision: commercial benchmark and possible personal backend.

### Freedom
- URL: https://freedom.to/
- Why: cross-device sessions and Locked Mode.
- Audit: Windows lock boundary, upcoming vs active session changes, CLI/API, cross-device synchronization and failure handling.
- Decision: secondary commercial benchmark.

### Digital Habits: Blocker
- URL: https://github.com/ (find official Centre for Digital Habits repository; source referred to in conversation)
- Why: Focus Spaces, stop-early/override challenge, research-oriented scheduling and attention interventions.
- Audit: exact Windows mechanisms, process watcher permissions, browser extension coverage, tests, licence of each repo, release cadence.
- Decision: design reference; do not assume Windows hard enforcement.

### Windows native policies
- Assigned Access: https://learn.microsoft.com/windows/configuration/assigned-access/
- App Control for Business / WDAC: https://learn.microsoft.com/windows/security/application-security/application-control/app-control-for-business/
- AppLocker: https://learn.microsoft.com/windows/security/application-security/application-control/app-control-for-business/applocker/
- Chrome enterprise policies: https://chromeenterprise.google/policies/
- Audit: Windows edition support, policy deployment, standard-user behaviour, recovery, allowlist dependencies, browser managed profile, admin boundary.

## 5.2 Observation / telemetry

### ActivityWatch
- URL: https://github.com/ActivityWatch/activitywatch
- Why: local-first activity watcher ecosystem and API.
- Audit: current browser watcher fields, local API, event granularity, retention, extension behaviour, current release, CPU/RAM, licence (MPL-2.0 noted in PDF; re-check repo).
- Decision: first observation integration to compare with minimal observer.

### Sysmon and Sysmon Modular
- URLs: https://learn.microsoft.com/sysinternals/downloads/sysmon ; https://github.com/olafhartong/sysmon-modular
- Why: process creation/termination, parent process, command line, GUID correlation, selected DNS/network events.
- Audit: event IDs, config filters, log volume, event forwarding, Windows version, storage and permission needs.
- Decision: use only a small custom profile; do not run verbose research config continuously.

### Focusd
- URL: https://github.com/ (search repository named Focusd; exact repo link needs manual verification)
- Why: lightweight Windows Go foreground application and browser-title observer with SQLite.
- Audit: exact repository/release/licence, supported browsers, polling overhead, schema and API.
- Decision: compare as lightweight alternative to ActivityWatch.

### Screenpipe
- URL: https://github.com/screenpipe/screenpipe
- Docs: https://docs.screenpi.pe/
- Why: screen history, OCR/accessibility data, application switching, searchable timeline and APIs/MCP.
- Audit: current capture modes, CPU/RAM/disk per mode, database schema, retention, export, commercial/source-available licence, API stability.
- Decision: optional rich observation module; short controlled trial first.

## 5.3 Browser and attention interface

### WXT
- URLs: https://wxt.dev/ ; https://github.com/wxt-dev/wxt
- Why: extension framework for TypeScript and Manifest V3.
- Audit: latest release, browser support, Native Messaging integration and tests.
- Decision: possible formal browser adapter framework; don't rewrite working prototype only for framework preference.

### Purpose Mode
- URL: https://github.com/hankhplee/purpose-mode
- Why: suppresses infinite scroll, autoplay, recommendation sidebars and other attention-capturing UI while leaving the site usable.
- Audit: current supported sites, feature selectors, study details, licence and extension compatibility.
- Decision: high-value adaptation for bounded research mode.

### Unhook / Unhook NG / Intentional YouTube
- URLs: https://unhookextension.com/ ; https://github.com/TheArchons/unhookng ; https://github.com/gabrielgustavoandrade/intentional-youtube
- Why: remove recommendations/Shorts, constrain YouTube navigation, reduce unbounded feed pathways.
- Audit: source availability/licence, supported Chrome versions, features, maintenance and whether an adapter is possible.
- Decision: use/compare existing extensions before creating a Dhriti YouTube adapter.

## 5.4 Mobile mechanisms

### Nudge
- URL: https://github.com/astraedus/nudge
- Why: Android app delays, feature-level blocking, accessibility-based detection.
- Audit: current build, Android permission model, detection reliability after app UI changes, battery use, licence.
- Decision: experiment only if phone diversion is a material route.

### AddictionBuster
- URL: https://github.com/corlite/AddictionBuster
- Why: app-opening friction, challenges, temporary access and return to home screen.
- Audit: current release vs source state, accessibility/overlay behaviour, background restrictions, battery and licence.
- Decision: alternative mobile intervention to compare with Nudge.

## 5.5 Network security

### Portmaster
- URL: https://github.com/safing/portmaster
- Docs: https://docs.safing.io/
- Why: per-app network visibility and control using Windows Filtering Platform integration.
- Audit: app rule API, daemon/service, WFP driver, VPN compatibility, rule lifecycle, permissions, licence (GPL-3.0 noted), fail-open/closed behaviour.
- Decision: potential network enforcement provider; not a website semantic filter or app-launch blocker.

### OpenWrt
- URL: https://openwrt.org/docs/guide-user/firewall/firewall_configuration
- Why: device/time-based network restrictions at router level.
- Audit: current router compatibility, time rules, DHCP reservation/device identity, admin boundary, mobile hotspot bypass.
- Decision: optional multi-device environmental control; do not buy hardware solely for this before proving need.

### Mullvad / fail-closed principle
- URL: https://github.com/mullvad/mullvadvpn-app
- Why: study atomic firewall transitions and fail-closed network behaviour.
- Decision: borrow reliability principles; do not make VPN a dependency unless separately required.

## 5.6 Process mining, formal methods and research

### PM4Py
- URL: https://github.com/process-intelligence-solutions/pm4py
- Why: event log import, process discovery, directly-follows graphs, variants and conformance.
- Audit: build a synthetic event log, discover a graph, inspect data model, version and licence.
- Decision: high-priority offline analytics experiment.

### HeartSteps
- URLs: https://github.com/kpwhri/heartsteps ; https://github.com/klasnja/HeartStepsV1
- Why: JITAI decision points, intervention randomization, micro-randomized trial methodology and dataset.
- Audit: read papers/protocol, decision-point eligibility, treatment randomization, proximal outcomes, carry-over effects. Do not copy its mobile health stack.
- Decision: borrow experiment design, not product architecture.

### TLA+ / TLC
- URLs: https://github.com/tlaplus/tlaplus ; https://docs.tlapl.us/
- Why: model-check state machine, emergency paths, crash/reboot, concurrency, policy transitions and invariants.
- Decision: high-value development-time verification; negligible runtime impact.

### Open Policy Agent (OPA)
- URL: https://github.com/open-policy-agent/opa
- Why: declarative policy separation and policy tests.
- Decision: investigate policy-as-code; do not install as runtime dependency until policy complexity requires it.

### Beeminder
- URL: https://api.beeminder.com/
- Why: commitment devices, delayed reduction of pledges (Akrasia Horizon), API datapoints.
- Decision: optional external accountability; not necessary and not a reason to introduce financial penalties.

### Focusmate
- URL: https://www.focusmate.com/
- Why: body doubling / scheduled social commitment.
- Decision: trial as an intervention condition rather than build a platform.

---

# 6. The missing mechanisms: initiation, dependencies and task profiles

## 6.1 Access restriction is not sufficient

The sequence “distractions blocked → work starts” is an unproven assumption. The user can remain idle, stare at an IDE, reorganize files, keep planning or hit an actual skill gap.

Separate at least these failure classes as hypotheses:

1. Attention diversion.
2. Initiation friction.
3. Task ambiguity.
4. Capability/knowledge gap.
5. Environmental/physical constraint.
6. Deliberate change of priority or commitment.

Do not diagnose a psychological cause from telemetry. Match interventions to observed bottlenecks.

## 6.2 Workspace ignition (custom Dhriti feature)

Build a small task launcher that opens the actual project, relevant files, terminal in the correct directory, permitted browser profile and first command. Start with PowerShell scripts; move to Rust/Tauri only after the workflow proves useful.

Cold-state plan fields:

- Desired outcome.
- Smallest physical first action.
- Workspace and relevant files.
- First command or operation.
- Expected obstacle.
- IF–THEN response to the obstacle.
- Research fallback and bounded allowance.
- Return condition.
- Evidence type and milestone.

Example:

```text
Outcome: Implement registration endpoint.
First action: Open RegistrationController and run existing tests.
Obstacle: Validation test fails.
IF validation test fails THEN inspect the first failing assertion and reproduce it.
Research fallback: Spring Security documentation for the exact failing behaviour.
Return condition: Return to controller/service and rerun test.
Evidence: changed code + test result + note for unresolved issue.
```

The 10/15/20-minute values are personal experimental parameters, not universal scientific thresholds.

## 6.3 Task profiles

A global semantic anchor is too simplistic. Same application/site may be useful in one task and distracting in another.

Initial profiles:

- Coding: IDE, terminal, Git, compiler docs, bounded technical research.
- Study: course PDFs, notes, lectures, worked problems and recall attempts.
- Research: papers, repositories, search, selected video/AI tools and research artifact.
- Writing: editor, source material and references.

Start with the two or three profiles actually used most. Profiles should be authored personally; don't spend weeks designing a universal taxonomy.

## 6.4 Dependency graph and bounded research

Represent work as `primary outcome -> obstacle/requirement -> dependency -> permitted resource -> finding/evidence -> return to task`.

A research pass should have explicit scope, expiry and return condition. It can be triggered by a declared dependency or an observed obstacle, not merely a high similarity score.

Example: registration endpoint -> missing JWT validation knowledge -> Spring Security JWT documentation -> relevant notes -> back to implementation.

Use DAG/build-system/workflow concepts. A task is a dependency network, not one embedding vector.

## 6.5 Finite research environment

Invert recommendation systems: instead of infinite next-content generation, allow a finite set of sources/resources for a defined research objective. Suppress infinite scroll, autoplay, Shorts and recommendation surfaces where possible using existing tools such as Purpose Mode/Unhook. A finite source set plus a research artifact may be more dependable than universal semantic content classification.

---

# 7. Event data, provenance and offline research

## 7.1 Personal data capture position

The user explicitly accepts personal activity capture for this experiment. Retain useful local raw traces for longitudinal research, rather than deleting almost everything immediately after each session.

Capture only sources that answer a question or support an experiment. Avoid high-volume keystroke capture by default; structured application/IDE/terminal/browser events are usually more useful and less noisy.

Data may include (when the relevant adapter is deliberately enabled):

- Browser URL, title, timestamp, navigation parent, redirects.
- Search query and originating event.
- YouTube video identity and playback position; captions only where legally/technically available and useful.
- AI tool/site, conversation identifiers, timestamps and optionally selected prompt/response content.
- Windows process, parent process, window title, foreground transitions, idle state.
- VS Code workspace, active file, save, terminal/task/test events.
- Terminal commands and selected output.
- Git branch/diff statistics/commit events.
- Contract, policy version, adapter status, intervention, override and return events.

The user is comfortable with capture; avoid accidental external data transfer and accidental public repository commits. Keep personal traces, API keys and backups outside Git. Use synthetic example data in the public repository.

## 7.2 Suggested normalized event schema

```text
event_id
occurred_at_utc
monotonic_offset_ms
session_id
case_id
source_adapter
source_version
event_type
parent_event_id
process_instance_id
observed_payload
raw_payload_reference
inference_payload
model_id_or_rule_version
policy_version
action_taken
telemetry_quality
```

Keep observed and inferred data separate. Use process GUIDs or stable adapter instance IDs where available; do not rely on reusable PIDs alone. Record missing telemetry as `UNKNOWN`, not as evidence of inactivity or failure.

## 7.3 Evidence classes

- **Observed:** file saved, test launched, process foregrounded, page navigated.
- **Submitted:** a draft, note, screenshot or manual explanation was submitted.
- **Machine-checked:** specified test passed, artifact exists, a command returned a defined exit code.

Do not treat these as equivalent. A screenshot does not prove time spent, authenticity or quality. A model summarizing a screenshot does not independently verify it. A passing test does not prove the entire task is correct.

## 7.4 Offline analysis should be a first-class capability

Use an offline pipeline:

1. Reconstruct event sequence and parent-child lineage.
2. Manually label a sample of sessions.
3. Use PM4Py for process discovery and variants.
4. Use SQL/Python statistical analysis for timing, frequency and outcomes.
5. Optionally ask local models to propose interpretations, but keep model outputs distinct from manual labels.
6. Review hypotheses in cold state; only selected changes affect future contracts.

Example possible finding (illustrative only): “On five of seven coding sessions, the first extended diversion followed a failed test run; four began with an architecture-related search.” Treat as a hypothesis, not a diagnosis.

---

# 8. Model and semantic analysis strategy

## 8.1 Never make an LLM part of critical enforcement

If model, ONNX runtime, API, quota or internet fails, deterministic policy still functions. AI analysis is optional and non-authoritative.

## 8.2 Candidate model experiments

- `all-MiniLM-L6-v2`: lightweight baseline.
- BGE-small/base family: benchmark alternative.
- Qwen3 embedding family: stronger embedding candidate; measure size/latency.
- EmbeddingGemma 2: 2026 model candidate; verify model card, licence, supported runtime, quantization and actual local memory/latency before selecting.
- BGE reranker / cross-encoder: only if ambiguous cases justify the extra latency/resource cost.
- Small local generative classifier or provider API: only after evidence that embeddings/rules are insufficient.

Benchmark against labelled Dhriti examples, not general STS/retrieval claims. Labels should describe activity relationship: direct execution, necessary dependency research, related nonessential exploration, repeated tutorial consumption, unrelated branching, setup, offline/rest, unknown.

Similarity threshold values in the PDF (0.40/0.65/0.60) are unvalidated and should not be carried into production.

## 8.3 Control-engineering principles for detector stability

- **Hysteresis:** require meaningful evidence to switch state; don't toggle on every small score change.
- **Debouncing:** ignore one-off transient events.
- **Cooldown:** avoid repeated interventions in a short period.
- **Saturation:** cap restriction escalation.
- **Sensor fault detection:** distinguish adapter failure from observed absence of activity.
- **Fail-safe:** deterministic precommitted restrictions continue if optional analysis fails.

A disagreement with a classifier is not additional evidence that the classifier was correct. Explicitly test for self-confirming loops.

---

# 9. Research evidence snapshot (30 October 2026)

These are sources and conclusions already identified. They do not validate the complete Dhriti architecture.

## 9.1 Digital disconnection and procrastination

**Klingelhoefer, Gilbert & Meier, Scientific Reports (29 May 2026), “Digital disconnection as a self-regulatory strategy against procrastination.”** Two-week experience-sampling study, N=237 young adults, T=12,408 situational observations. Digital disconnection was associated with slightly lower procrastination within the same person/situation (reported beta approximately -0.07); prior-situation carry-over was small. Observational association, not a randomized causal demonstration. Supports testing temporary disconnection, not claiming blocking guarantees better work.

- https://www.nature.com/articles/s41598-026-46218-1
- https://pubmed.ncbi.nlm.nih.gov/42215558/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13234400/

## 9.2 Digital behaviour-change intervention scoping review

**JMIR (2026), “Digital Behavior Change Interventions for Digital Overuse: Scoping Review of Current Approaches and Emerging AI-Enabled Systems.”** 32 studies included. 84% targeted smartphones; 81% targeted total usage time rather than differentiating activities; AI/ML interventions remained limited; many studies short-term and follow-up limited. Identifies an opportunity for activity-specific, theory-driven and longitudinal work, but does not prove Dhriti's approach.

- https://www.jmir.org/2026/1/e101150
- https://pubmed.ncbi.nlm.nih.gov/42778172/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13646779/

## 9.3 Generative AI vs human conversational procrastination intervention

**2026 randomized pilot.** 62 university students analysed, three-session intervention; no significant group × time interaction (p=.117). 43.1% reported at least one unwanted negative effect at post-assessment. This argues against assuming that conversational AI is an automatically effective or harmless procrastination intervention. It does not test Dhriti-style blocking.

- https://pmc.ncbi.nlm.nih.gov/articles/PMC13402774/
- https://pubmed.ncbi.nlm.nih.gov/42516921/
- https://journals.sagepub.com/doi/10.1177/20552076261450336

## 9.4 MCII / implementation intentions

The prior research pass identified a February 2026 small undergraduate study (81 participants, seven-day intervention) comparing MCII with positive thinking and reporting improved task initiation/willingness. Re-verify the exact paper, effect sizes, outcome measures and limitations before relying on it. More generally, if–then implementation intentions have a substantial broader meta-analytic literature; avoid transferring pooled effects directly to this personal design.

- Search lead: https://scholar.google.com/scholar?q=2026+mental+contrasting+implementation+intentions+81+undergraduates+task+initiation

## 9.5 Purpose Mode field study

Carnegie Mellon research/open-source extension suppressing attention-capturing features such as infinite scroll, autoplay and recommendation sidebars while retaining the underlying website. A two-week field study with 29 participants reported lower self-reported distraction and reduced time on targeted websites. Small field study; not definitive long-term evidence.

- https://github.com/hankhplee/purpose-mode

## 9.6 Other earlier research leads requiring source-level re-verification

- 2021 systematic review of digital self-control interventions: restrictions/awareness interventions vary; evidence limitations include small samples and short studies.
- 2024 large university-student randomized digital intervention study (n≈2,209): single-session advice/feedback did not show a marked difference in primary self-reported procrastination outcomes.
- 2025 pilot chatbot-supported procrastination intervention (75 completers): favourable results in some measures; not a test of automated content blocking.
- 2026 replication of precommitment deadline manipulation: negligible effect for the specific manipulation tested; not equivalent to an entire self-binding system.

These are leads from the conversation's earlier research, not complete literature reviews. Retrieve original papers and exact citations before using them in a formal research write-up.

---

# 10. Personal experiment design

## 10.1 Separate three questions

**Experiment A — Does access restriction change the environment?** Compare blocker, OS allowlist, restricted desktop, delayed relaxation, physical phone separation and network restrictions.

**Experiment B — Can Dhriti reconstruct what happened?** Compare ActivityWatch, Sysmon, browser events, IDE events and optional Screenpipe. Evaluate event completeness and lineage.

**Experiment C — Which intervention improves execution?** Compare restriction alone with workspace launcher, IF–THEN obstacle plan, bounded research pass and optional body doubling/environment change.

Do not conflate a successful block with an improved outcome.

## 10.2 Initial N-of-1 conditions

1. **Baseline:** several comparable work sessions with observation but no new restriction.
2. **A — Restriction only:** existing blocker, no custom detector.
3. **B — Restriction + workspace launcher:** open real project, files, terminal and first command.
4. **C — Restriction + IF–THEN plan:** identify likely obstacle and planned response.
5. **D — Best prior combination + bounded research:** permit task dependencies via a limited route.
6. **Optional E — external accountability / physical environment:** body doubling, library or coworking condition.

Repeat comparable sessions and vary order where practical. Account for carry-over, task difficulty, deadlines, sleep/energy and environment. Do not compare unlike tasks as if they were equivalent.

## 10.3 Measures

Primary: meaningful task progress / accepted milestones, with quality assessed separately.

Secondary:
- Time to first meaningful action.
- Milestone completion.
- Artifact quality / correctness.
- Task-context time.
- Branch count and branch duration.
- Return-to-task rate and latency.
- False-positive interventions and missed known detours.
- Break-glass / bypass frequency and reason.
- Interruptions, missing telemetry and recovery.
- Offline time (separate from work and failure).
- Sustained outcomes after novelty fades.

Do not use screen-time reduction as the sole success measure.

---

# 11. Hardware-aware, plug-in architecture

Keep the stable core small. Higher capability should enrich observation and analysis, not force a rewrite.

## 11.1 Reference tiers

| Tier | Components | Goal |
|---|---|---|
| Lite | Contract/state core, SQLite, WXT or managed browser policy, one light observer, PowerShell launcher, deterministic rules | Demonstrate commitment loop on modest hardware |
| Standard | Lite + Sysmon filtered profile, IDE/terminal event adapter, local small embeddings, PM4Py offline | Richer sequence reconstruction and evaluation |
| Research | Standard + selected Screenpipe capture, larger/quantized models, more event sources and multimodal experiments | Richer personal behaviour research |
| Externalized enforcement | Separate standard account/admin authority, Assigned Access/App Control, optional router/second device | Stronger restriction boundary, not a model/hardware tier |

## 11.2 Capability manifest (proposed)

```yaml
provider: sysmon
role: observation
capabilities:
  - process_creation
  - process_termination
  - parent_process
  - network_connections
  - dns_queries
requirements:
  administrator: true
resource_class: low_to_moderate
fallback: activitywatch_partial
```

Each provider should declare version, supported OS, permission requirements, capabilities, event schema, resource class, health/heartbeat, failure semantics, fallback and licence. The core must never assume a capability exists merely because a plugin is configured.

## 11.3 Data storage separation

- SQLite: normalized events, contracts, state, links and metadata.
- JSONL: larger raw event payloads where useful.
- CSV/Parquet: offline analysis exports.
- Separate folder: screenshots/audio/video if deliberately enabled.
- Separate model folder: model weights/checkpoints.

Keep personal databases and secrets out of public Git. Add synthetic traces and reproducible test data to the repository.

---

# 12. Recommended revised roadmap

This roadmap includes research gates. A phase is complete only when its exit criterion is met.

## Phase 0 — Archive and freeze decisions

Deliverables:
- This research dossier and source register.
- Original PDF preserved unchanged.
- Verbatim chat export added when available.
- Decision register and manual audit log.
- Explicit personal environment: Windows edition/version, browser(s), devices, hardware, disk budget and current blocker tools.

Exit criterion: no critical requirement is merely implied; contradictions in Section 2.2 are resolved.

## Phase 1 — Manual mechanism bake-off

Test in disposable/standard-user environment:
- FocusMe vs Cold Turkey (actual restriction, CLI, recovery, offline, sleep/reboot).
- Focuser source/release audit and controlled trial.
- Plucky delayed relaxation test.
- Safe Exam Browser restricted desktop test.

Exit criterion: choose a primary enforcement backend and document exact supported/bypassable boundaries.

## Phase 2 — Baseline observation

Use ActivityWatch or Focusd plus selected Sysmon events and browser observations. Keep capture narrow enough to measure. Establish baseline on comparable work sessions.

Exit criterion: reconstruct a useful session timeline and identify gaps; do not yet claim semantic detection.

## Phase 3 — Personal workspace ignition

PowerShell launcher initially. Prepare IDE/project/terminal/browser profile/start command and contract metadata.

Exit criterion: reduces friction without causing incorrect workspace restoration or hiding essential tools.

## Phase 4 — Event model and process-mining proof

Implement normalized event model, parent/child lineage and synthetic event fixtures. Export to PM4Py and discover process graph/variants.

Exit criterion: useful, manually validated explanation of at least one recurring pattern.

## Phase 5 — First Dhriti core vertical slice

Only now decide whether the existing enforcement provider is wrapped or whether Tauri/Rust core is needed. Implement contract, arming checks, session lifecycle, event capture, evidence submission, interruption recovery and aftermath.

Exit criterion: end-to-end session works and records exact backend capabilities and failures.

## Phase 6 — Task profiles, dependency graph and bounded research

Implement two or three personal task profiles and a bounded research/dependency chain. Test legitimate research vs unrelated branching.

Exit criterion: false restrictions are acceptable for the selected personal use, and return-to-task behaviour is measurable.

## Phase 7 — Semantic experiment

Create labelled dataset; benchmark rules vs embeddings; test local CPU inference, latency and memory. Add reranker/classifier only if metrics improve enough to justify complexity.

Exit criterion: clear measurable improvement over deterministic baseline, not merely plausible model output.

## Phase 8 — Advanced enforcement and adaptation research

Add restricted Windows user, AppLocker/Assigned Access/App Control audit, router/phone constraints, optional human accountability and JITAI-style interventions. Formalize state machine in TLA+ if lifecycle complexity warrants.

Exit criterion: controlled fault/recovery and personal outcome improvement over the baseline.

---

# 13. Manual audit plan and evidence requirements

Do not return from repository investigation with a README summary alone. For every candidate, collect:

1. Current repository URL and exact commit/release tested.
2. Licence file and component-level exceptions.
3. Windows installer/package or exact build instructions.
4. Source file paths implementing the claimed mechanism.
5. Configuration format and CLI/API contract.
6. Required privileges, services, drivers and scheduled tasks.
7. Failure behaviour: kill process, disable extension, sleep, hibernate, reboot, offline, clock change, account switch.
8. CPU/RAM/disk measurements on the actual laptop.
9. Security warnings/Defender findings and reproducible evidence.
10. Known issue threads and maintainer response.
11. Whether it can be run as a black box, wrapped, forked, copied or only studied.
12. Smallest reproducible experiment and observed result.

Suggested report format:

```text
PROJECT / VERSION / COMMIT:
CLAIMED CAPABILITY:
SOURCE FILES:
ACTUAL MECHANISM:
CONFIG / CLI / API:
PRIVILEGES / DEPENDENCIES:
LICENCE:
RESOURCE MEASUREMENTS:
TESTS PERFORMED:
FAILURES / BYPASSES:
WHAT CAN BE REUSED:
WHAT MUST BE CUSTOM:
RECOMMENDATION: run / wrap / fork / adapt / study / reject
CONFIDENCE: verified / partially verified / unverified
```

---

# 14. Key unresolved decisions

1. Which Windows edition/version and browser(s) are the first target?
2. What actual laptop resource budget and free disk space can be allocated to capture and models?
3. Which enforcement backend wins the bake-off: FocusMe, Cold Turkey, Focuser, Plucky, Safe Exam Browser + policy, or a combination?
4. Is an external administrator/accountability partner available for a stronger enforcement experiment, or is self-administered local enforcement the only acceptable setup?
5. How many personal devices need to be covered: laptop only, phone, tablet, other computers, router?
6. What are the initial two or three task profiles?
7. What is the chosen fixed daily window and how should incomplete tasks release? This is a personal experiment setting, not a universal optimum.
8. Which data categories will be retained: URL/title/process only, page text, AI content, screenshots/OCR, terminal output?
9. What is the storage retention period and backup policy for the personal dataset?
10. Which work artifacts can be machine-checked, and which are necessarily self-submitted?
11. Which intervention conditions should be compared first?
12. What constitutes a meaningful milestone for each task profile?
13. How should genuine priority changes, emergencies, accessibility needs, illness/fatigue and system maintenance be handled?
14. Does the system need a user-facing silent wall, or is a minimal status/recovery display permitted? Decide explicitly.
15. Is the goal a personal system that is effective for you, or also a publishable research prototype? Current priority is personal experiment; public repo is documentation/code sharing, not marketing.

---

# 15. Guardrails against this becoming another avoidance project

The research itself can become an elaborate form of preparation. The archive is intended to prevent repeated research, not justify indefinite research.

Use these rules:

- Every new research item must identify a capability gap, a decision it could change, or a testable hypothesis.
- Stop searching a domain when the shortlist is sufficient for a controlled comparison.
- Do not add a model unless deterministic rules or an existing tool demonstrably fail on a meaningful case.
- Do not build a generic abstraction until a second real provider needs it; keep interfaces narrow and evidence-driven.
- A manual investigation must produce an artifact: configuration, test result, source-path note, measurement or rejection reason.
- Every phase has a small working demonstration and exit criterion.
- Keep the public Git repository separate from personal raw data.
- If a feature creates more maintenance than experimental value, remove or disable it.

---

# 16. Source index and research leads

See `DHRITI_SOURCE_REGISTER.csv` for a machine-readable register. Primary links grouped by area:

**2026 evidence**
- Digital disconnection study: https://www.nature.com/articles/s41598-026-46218-1
- 2026 digital behaviour-change scoping review: https://www.jmir.org/2026/1/e101150
- 2026 GenAI vs human procrastination intervention pilot: https://pmc.ncbi.nlm.nih.gov/articles/PMC13402774/
- MCII study search lead: https://scholar.google.com/scholar?q=2026+mental+contrasting+implementation+intentions+81+undergraduates+task+initiation

**Enforcement and access control**
- Focuser: https://github.com/aadeshrao123/Focuser
- Plucky docs: https://docs.pluckeye.net/
- Safe Exam Browser: https://www.safeexambrowser.org/
- SEB Windows source: https://github.com/SafeExamBrowser/seb-win-refactoring
- FocusMe: https://focusme.com/windows/
- Cold Turkey: https://getcoldturkey.com/
- Freedom: https://freedom.to/
- Windows Assigned Access: https://learn.microsoft.com/windows/configuration/assigned-access/
- App Control for Business: https://learn.microsoft.com/windows/security/application-security/application-control/app-control-for-business/
- Chrome policies: https://chromeenterprise.google/policies/

**Observation and analysis**
- ActivityWatch: https://github.com/ActivityWatch/activitywatch
- Sysmon: https://learn.microsoft.com/sysinternals/downloads/sysmon
- Sysmon Modular: https://github.com/olafhartong/sysmon-modular
- Screenpipe: https://github.com/screenpipe/screenpipe
- PM4Py: https://github.com/process-intelligence-solutions/pm4py
- Focusd: exact repository link to verify manually

**Attention / mobile**
- Purpose Mode: https://github.com/hankhplee/purpose-mode
- Unhook: https://unhookextension.com/
- Unhook NG: https://github.com/TheArchons/unhookng
- Intentional YouTube: https://github.com/gabrielgustavoandrade/intentional-youtube
- Nudge: https://github.com/astraedus/nudge
- AddictionBuster: https://github.com/corlite/AddictionBuster
- Digital Habits research repo: exact canonical repository/licence to verify manually

**Network and systems**
- Portmaster: https://github.com/safing/portmaster
- Portmaster docs: https://docs.safing.io/
- OpenWrt firewall docs: https://openwrt.org/docs/guide-user/firewall/firewall_configuration
- Mullvad VPN app: https://github.com/mullvad/mullvadvpn-app
- Windows service Rust crate: https://crates.io/crates/windows-service

**Policy, formal methods and behaviour research**
- OPA: https://github.com/open-policy-agent/opa
- TLA+: https://github.com/tlaplus/tlaplus
- TLA+ docs: https://docs.tlapl.us/
- HeartSteps: https://github.com/kpwhri/heartsteps
- HeartSteps dataset: https://github.com/klasnja/HeartStepsV1
- Beeminder API: https://api.beeminder.com/
- Focusmate: https://www.focusmate.com/
- AWARE framework: https://www.awareframework.com/

---

# 17. Final current recommendation

Move from open-ended research to **Phase 0 archive + Phase 1 manual mechanism bake-off**.

The most important work is no longer to discover another focus app. It is to determine whether existing products already provide reliable restriction and what precise capability gaps remain. In parallel, capture a real baseline and test the workspace launcher / first-action plan.

The likely durable architecture is a small Dhriti core with replaceable enforcement, observation, inference and evidence providers; an offline PM4Py/statistical research layer; and personal task/dependency models that are hand-built because they are specific to the user's actual working patterns.

Do not start a rewrite until the manual audit records prove that the selected existing mechanisms cannot meet the requirement.
