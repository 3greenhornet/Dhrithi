# Windows policy guides (E2/E3) — documented, deliberate, manual

These are the dossier's native-policy leads (section 5.1). None is
auto-applied by Dhriti; each is a decision for a cold-state review
after reading the linked Microsoft docs. The common pattern they
implement from the dossier: **E3 — restrictions administered outside
the active user context.**

## In this folder

| File | What it covers |
|---|---|
| `hosts-block.ps1` | E2 DNS blocking — ready to run (see header) |
| `assigned-access.md` | kiosk / restricted desktop |
| `applocker.md` | application execution rules |
| `wdac.md` | App Control for Business policies |
| `chrome-policies.md` | managed browser profile / force-install |

## Honest limits (dossier 3.3)

- No level is unbreakable while you hold admin rights on the machine.
- E4 (a trusted person holding admin/router control) is the only
  level that materially changes the bypass cost — see
  `docs/ENFORCEMENT_LEVELS.md`.
- Whatever you enable, record it: which level is active, which bypass
  routes remain. The experiment record keeps the honest version.
