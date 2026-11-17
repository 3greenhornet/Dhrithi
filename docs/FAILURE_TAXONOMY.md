# Failure taxonomy

What "went wrong" means, so a result artifact can classify it and the
risk register can consume it (plan Part 4, process gaps). One failure,
one code. If a failure fits two codes, it is two failures.

| Code | Class | Meaning | Who consumes it |
|---|---|---|---|
| `tool_incompatibility` | Environment | The tool cannot do what the plan assumed on this machine/OS/toolchain (e.g. CLI flag absent, MSVC-only build) | Phase gate + `VERSION_PINS.md` |
| `observation_gap` | Telemetry | Something happened and no sensor saw it (tab-level URL lost, watcher suspended, timestamps missing) | Aftermath `telemetry_quality`, Phase 2 gaps list |
| `classification_error` | Decision | The deterministic policy judged wrongly (false positive on a legitimate dependency; false negative on a branch) | Cold review + the labeling gate; never patched in-session |
| `enforcement_bypass` | Boundary | A known bypass was used or a boundary was weaker than assumed (CT-17 rename, token probe, E1 removed) | Evasion matrix + `ENFORCEMENT_LEVELS.md` |
| `user_error` | Operation | The operator (you) fed the system wrong input (wrong contract, wrong command) | Nothing — write it down, laugh, move on |
| `design_flaw` | Product | The mechanism itself is wrong (a check that cannot work as specified) | `RESOLUTIONS.md` row + decision register entry |
| `avoidance_metabolized` | Loop | The system itself became the distraction (meta-recursion: tuning Dhriti instead of working; fixing suppression selectors mid-session) | Builder clause + digest honesty; R-001 made visible |

Two rules:

1. **A failure without a code is an anecdote.** Result artifacts end
   with a `failures:` list, each row `code — one sentence — evidence`.
2. **`avoidance_metabolized` is a first-class outcome, not a joke.**
   Specimen 001 documents the builder proposing the guardrail software
   *inside* the loop it was escaping. Any week where Dhriti work
   exceeded main-belief work while targets were unmet is logged under
   this code, and the digest carries it to the one human who reads it.
