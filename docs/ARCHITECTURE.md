# ARCHITECTURE

```
                        COLD STATE                    HOT STATE (window)
                 ┌─────────────────────┐        ┌──────────────────────────┐
                 │ dhriti ritual       │        │ dhriti daemon            │
                 │ (contract wizard)   │        │  tick every 5s:          │
                 │ dhriti bootcamp     │──seal─▶│  heartbeat / day open /  │
                 │ dhriti research - N │        │  evaluate window / expiry│
                 └─────────────────────┘        └──────────┬───────────────┘
                        │                                  │
              contract (immutable,                        policy snapshot
              hash-chained row)                           (frozen at seal)
                                                          │
        ┌─────────────────────────────────────────────────┼───────────────┐
        │                     ADAPTERS (replaceable)      ▼               │
        │  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
        │  │ E1 extension_    │  │ E2 hosts_file    │  │ observation   │ │
        │  │    bridge (LIVE) │  │   (manual apply) │  │ activitywatch │ │
        │  │  Dhriti Wall ←───│──│─ focusme/...     │  │ sysmon/pipe   │ │
        │  │  MV3 extension   │  │  (audit-gated    │  │ (opt-in)      │ │
        │  └────────┬─────────┘  │  placeholders)   │  └───────┬───────┘ │
        │           │ loopback   └────────┬─────────┘          │         │
        └───────────┼─────────────────────┼────────────────────┼─────────┘
                    ▼                     ▼                    ▼
             ┌──────────────────────────────────────────────────────┐
             │  LEDGER (SQLite, append-only, SHA-256 hash chain)    │
             │  normalized event schema · observed ≠ inferred       │
             └──────────────────────────────────────────────────────┘
                    │                                     │
                    ▼                                     ▼
          ┌──────────────────┐              ┌─────────────────────────┐
          │ dhriti report /  │  cold again  │ analysis/ (offline)     │
          │ review (facts vs │◀─────────────│ sequence · measures ·   │
          │ interpretation)  │              │ labels · PM4Py (opt.)   │
          └──────────────────┘              └─────────────────────────┘
```

## Stable core (never swapped casually)

| Module | Responsibility |
|---|---|
| `models.py` + `state_machine.py` | the only lifecycle authority |
| `contract.py` | cold-state writer, seal, immutability |
| `day_window.py` | the enforcement boundary math (R1 resolution) |
| `session.py` | atomic work units, 4 terminal states |
| `break_glass.py` | the toll (delay, reason, cooldown, declared penalty) |
| `evidence.py` | three evidence classes + deterministic verdicts |
| `policy.py` | versioned snapshots, deterministic rules, taper scaling |
| `research_pass.py` | bounded research (finite sources + expiry) |
| `ledger.py` | normalized events + hash chain + anchors |
| `bootcamp.py` | commitment container + evidence-based taper |
| `aftermath.py` | reports: contract vs reality, facts vs inference |
| `daemon.py` | the loop + recovery + arming orchestration |
| `bridge.py` | loopback token-auth API for the extension |

## Replaceable adapters

`adapters/base.py` defines the contract: `probe → arm → status`, with
`ExternalCommandAdapter` as the audit-gated placeholder pattern. Add
a provider by writing ~50 lines; nothing else changes.

## Flows worth knowing

**Session start (the arming gate):** `DRAFT → SEALED → ARMING →
arm_all(required) → ACTIVE` — or `ARMING_FAILED` with a disclosed
reason. A session is never represented as restricted until every
required backend confirms its actual state.

**Recovery:** at daemon boot, anything left ARMING/ACTIVE becomes
INTERRUPTED; days left OPEN past window_end become RECOVERED. The
chain stays intact; the aftermath reports the gap.

**Extension fail-safe:** policy carries `expires_at`. Daemon dead +
policy fresh → keep enforcing. Daemon dead + policy expired → unlock
(a dead daemon can never lock you out forever). No policy → dormant.
