# Chaos drills (D-086) — fault injection as a ritual

Chaos engineering for a single-machine commitment device: failure paths
that are never exercised are assumed-working fiction. Run the drill set
monthly, after `dhriti backup`. Every drill asserts EXPECTED behavior from
the design laws; a drill that passes when it should fail is a bug.

Each drill prints PASS/FAIL and exits non-zero on FAIL. They are
semi-automated by design: the human reads the outputs, the script checks
the cheap facts.

## Drill 1 — dead daemon mid-session (RECOVERED path)
Kill the daemon while a session is ACTIVE, restart, expect RECOVERED.

## Drill 2 — policy TTL lapse (D-062)
Stop the daemon, keep browsing with a fresh policy: the extension must
degrade to LOCAL deterministic governors (guard keeps burst toll; content
decisions unavailable). Not bricked, not open.

## Drill 3 — WAL sidecar quarantine (D-052 / D-064)
Corrupt-shape a sidecar file: quarantine must fire. Renaming (lock shape)
must NOT quarantine (locked is not corrupt).

## Drill 4 — token revocation (bridge honesty)
Rotate the bridge token, run one old-token request: expect 401 and a
`bridge_token_rejected` event, rate-limited.

## Drill 5 — E2 canary (D-081)
Run e2_canary_check.ps1. Expect "alive". Then delete the hosts entry and
re-run: expect "tampered". This proves the check can fail.
