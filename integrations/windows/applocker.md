# AppLocker — application execution rules (E2/E3)

Lead: https://learn.microsoft.com/windows/security/application-security/application-control/app-control-for-business/applocker/

## What it is

Windows' native application allowlisting: EXE/DLL/script/MSI rules per
user/group. In Dhriti terms: the OS-level version of a task profile's
`allowed_apps`.

## Dhriti mapping

- A rule set that allows ONLY the coding stack (IDE, terminal, JVM,
  browser) during the day window is the strictest app restriction
  available natively.
- Audit mode first: rules log what WOULD have blocked, nothing
   actually blocks. Run it for a few workdays, read the events, then
  enforce.

## Steps (manual, admin, cold state)

1. `secpol.msc` -> Application Control Policies -> AppLocker.
2. Create the rule collection (EXE: allow your work apps for the work
   account; default deny everything else for that account).
3. Run in **Audit mode** first; review
   `Event Viewer -> AppLocker logs`.
4. Enforce only after a week of clean audit events.

## Cautions

- Edition support: AppLocker needs Enterprise/Education (WDAC is the
  modern cross-edition alternative — see wdac.md).
- Allowlist dependencies: a blocked JVM helper DLL breaks your build;
  that is why audit mode comes first.
- The admin account is NOT restricted — that is the E4 boundary
  decision you make consciously.
