# Launcher — workspace ignition (dossier 6.2)

Access restriction does not start work. The sequence "distractions
blocked -> work starts" is an unproven assumption; initiation friction
is a separate failure class. Ignition is the custom Dhriti feature that
attacks it.

## Layout

- `ignite.ps1` — Windows-first launcher. Opens project, files,
  terminal (Windows Terminal if present), and a separate Chrome
  profile for the work browser, then prints the first command and the
  IF-THEN plan you wrote in the cold state.
- `profiles/ignite.example.json` — copy to
  `~/.dhriti/profiles/ignite.coding.json` and edit. This is the manual
  step; paths are machine-specific by nature.

## Cold-state plan fields (dossier 6.2)

```
Outcome: Implement registration endpoint.
First action: Open RegistrationController and run existing tests.
Obstacle: Validation test fails.
IF validation test fails THEN inspect the first failing assertion.
Research fallback: Spring Security JWT documentation (bounded pass).
Return condition: Return to controller and rerun test.
Evidence: changed code + test result + note for unresolved issue.
```

The 10/15/20-minute values you may see elsewhere are personal
experimental parameters, not universal scientific thresholds.

## `dhriti ignite --profile coding`

Prints which plan file the CLI expects and reminds you to create it if
missing — the plan itself stays a file you own, not a database row.
