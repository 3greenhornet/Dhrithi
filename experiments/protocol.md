# Experiment protocol — N-of-1 conditions (dossier section 10)

**Three questions, never conflated (D-022):**

- **A — environment:** does access restriction change what is
  reachable? (blocker / OS allowlist / restricted desktop / delayed
  relaxation / phone in another room)
- **B — reconstruction:** can Dhriti reconstruct what happened?
  (ActivityWatch vs Sysmon vs browser/IDE events; completeness,
  lineage, gaps)
- **C — execution:** which intervention improves execution?
  (restriction alone vs + launcher vs + IF–THEN vs + bounded research)

A successful block is not a successful outcome.

## Conditions

See `conditions.json` (machine-readable, used by
`dhriti session start --condition <id>` to tag sessions).

```
baseline  -> observe only
A         -> restriction only
B         -> + workspace launcher (ignite.ps1)
C         -> + IF-THEN obstacle plan
D         -> + bounded research pass
E (opt.)  -> + external accountability / environment change
```

## Rules

1. **Baseline first.** Several comparable sessions, observation on,
   nothing new enforced.
2. **Comparable tasks only.** A "read one chapter" session and a
   "implement an endpoint" session are not comparable data points.
3. **Repeat and vary order** where practical; note carry-over
   (dossier: account for deadlines, sleep, environment).
4. **Tag every session**: `dhriti session start --condition C ...`
5. **Compute measures cold**: `python analysis/measures.py --db ...`
   in the weekly review, never mid-session.
6. **One change per condition.** If B differs from A by two things,
   the comparison is void.

## Measures

Primary: meaningful task progress / accepted milestones (quality
assessed separately, cold).

Secondary: time to first meaningful action, milestone completion,
artifact quality, branch count/duration, return-to-task rate and
latency, false positives, missed detours, break-glass frequency,
interruptions/recovery, offline time, sustained outcomes after novelty
fades.

Anti-measure: screen-time reduction alone. Do not report it as
success.
