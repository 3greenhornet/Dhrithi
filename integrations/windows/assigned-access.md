# Assigned Access — restricted desktop (E3)

Lead: https://learn.microsoft.com/windows/configuration/assigned-access/

## What it is

Windows' native kiosk mode: a standard user account limited to one
allowlisted app set on a separate desktop. This is the same mechanism
Safe Exam Browser builds on (audit item 4), available without third-
party software.

## Dhriti mapping

- A separate "work" standard account IS the E3 pattern: restrictions
  administered outside the active user context.
- Your admin account stays untouched; the work account runs the day
  window with the wall up.
- The Dhriti daemon + extension run inside the work account; your
  admin account is the E4 escape hatch.

## Steps (manual, cold state — read the Microsoft doc first)

1. `Settings -> Accounts -> Family & other users` — create a standard
   local account ("work").
2. Configure Assigned Access (single-app kiosk, or multi-app
   `AssignedAccess Configuration` XML for: browser + terminal + IDE).
3. Test in a disposable account first (audit item discipline).
4. Recovery: know the unlock path BEFORE you enable it.

## Cautions (from the dossier's SEB notes)

- A restricted desktop is not full network containment; admitted apps
  may still reach the network/filesystem.
- Test edition support on your actual Windows licence.
- Record what you enabled in the audit notes + experiment record.
