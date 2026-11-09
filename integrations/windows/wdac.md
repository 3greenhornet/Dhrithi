# App Control for Business (WDAC) (E2/E3)

Lead: https://learn.microsoft.com/windows/security/application-security/application-control/app-control-for-business/

## What it is

The successor policy system to AppLocker: kernel-enforced code
integrity policies, works on Pro/Enterprise, audit mode available.

## Dhriti mapping

Same pattern as AppLocker (allowlist the work stack for the work
account) but stronger enforcement and broader edition support. The
dossier's caution applies fully: this is a powerful, machine-wide
mechanism — treat it as a later experiment, not a v1 step.

## Steps (manual, admin, cold state)

1. Build a policy with the **WDAC wizard**
   (https://webapp-wdac-wizard.azurewebsites.net/) — start from
   "allow installed apps + common risks blocked".
2. Deploy in **audit mode**, read
   `Microsoft-Windows-CodeIntegrity/Operational` events for a week.
3. Only then consider enforcement, on the work account only.

## Cautions

- A bad WDAC policy can make a machine unbootable or unusable —
  always keep the recovery path (signed policy removal procedure)
  written down and tested in a VM first.
- This is the highest-blast-radius item in the whole integrations
  folder. Nothing in Dhriti requires it; it is an optional E2/E3
  escalation for a later, evidence-motivated decision.
