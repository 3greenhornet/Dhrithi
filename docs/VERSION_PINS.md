# Version pins

Reproducibility register (plan Part 4, "process gaps": the plan pinned
Tauri and fastembed but nothing else). Every tool version used in any
phase is recorded here when first used. Unpinned = unrecorded = not
science.

| Tool / component | Version in use | Pinned at | Notes |
|---|---|---|---|
| Python core (this repo) | 3.12 (stdlib only) | v0.2.0 | zero pip dependencies by design |
| SQLite | bundled CPython | v0.2.0 | journal mode DELETE on Windows (R-007) |
| Dhriti Wall extension | 0.7.0 (MV3) | v0.7.0 | Chrome/Edge/Brave; suppression rules v1 |
| Chrome | NOT PINNED — record yours | — | CVE-2026-17923 floor: ≥ 151.0.7922.72 for URLBlocklist use (we do not rely on it as sole barrier) |
| Windows | NOT PINNED — record edition/build | — | AppLocker availability depends on Pro+ |
| ActivityWatch | NOT INSTALLED | — | heartbeat fix PR #561 required; 10-min zero-duration test before any baseline (R-004) |
| Sysmon | NOT INSTALLED | — | tuned profile; pin config commit SHA here when chosen |
| Cold Turkey | NOT INSTALLED | — | CLI = 4.9+; CT-14/CT-17 results land in `integrations/enforcement-audit/` |
| FocusMe / Plucky / Focuser | NOT INSTALLED | — | audit-gated placeholders (D-005/D-006/D-007) |
| Tauri 2 / Rust core | NOT BUILT (Phase 5 decision) | — | pin `tauri` ≥ 2.11.5 (origin-resolution fixes); no wildcard `remote.urls`, no `withGlobalTauri` |
| fastembed-rs / ONNX Runtime | NOT BUILT (Phase 7) | — | MSVC toolchain required; `ORT_DYLIB_PATH` pinned at build; AVX check against the laptop |
| PM4Py | optional (analysis) | — | offline only, never in the enforcement path |

Rule: an experiment result that depends on an unpinned tool is marked
`telemetry_quality: UNKNOWN` in its result artifact.
