# Enforcement levels (dossier 3.3) — and what each one honestly cannot do

No level is unbreakable while you hold administrative control of the
machine. The experiment record always knows which level is active and
which bypass routes remain.

| Level | Mechanism | Bypass routes that remain |
|---|---|---|
| **E1** browser | Dhriti Wall MV3 extension via the loopback bridge; optionally hardened by Chrome policy force-install | another browser; extension removed by admin (recorded, not prevented) |
| **E2** OS/network | hosts-file DNS block (manual admin apply); leads: AppLocker/WDAC, Portmaster, router rules | admin edits hosts; another DNS; VPN; portable browser |
| **E3** workspace | separate standard work account, Assigned Access / kiosk, managed policy administered outside your active context | your admin account (that is the point: friction you chose, escape you know) |
| **E4** external authority | a trusted person holds admin credentials or router control | social, not technical — the only level that materially changes the cost |

## What v1 ships

- **E1 is live** (extension + bridge, default in
  `enforcement.required_adapters`).
- **E2 ships as ready-but-manual**: the hosts adapter generates the
  block file; `integrations/windows/hosts-block.ps1` applies/removes
  it in an elevated shell. Adapter probe flips to INSTALLED only when
  the marker exists.
- **E3/E4 are documented decisions**, not code — they change accounts
  and trust, which no script should do silently.

## The disclosure rule

Every session's ledger row records the arming report:
`armed: [...]; FAILED: [...]; not configured: [...]`. If you run E1
only, the aftermath says so. A restriction you only think is active is
worse than one you know is absent.
