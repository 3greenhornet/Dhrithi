# Integrations — the manual-step inventory

Every placeholder in this project follows one pattern: **config-driven,
probed, honest**. Nothing silently fakes being installed. Each guide
below says what to install, what to put in `dhriti.config.json`, and
how to verify with `dhriti adapter status`.

| Integration | Capability | Status in v1 | Enable via |
|---|---|---|---|
| Dhriti Wall extension | E1 website blocking | **LIVE** | `extension/INSTALL.md` |
| hosts file | E2 DNS blocking | generated; apply = admin script | `windows/hosts-block.ps1` |
| ActivityWatch | observation (windows/afk) | placeholder → real client ready | `activitywatch/SETUP.md` |
| Sysmon | process provenance | placeholder (narrow config shipped) | `sysmon/SETUP.md` |
| Screenpipe | rich capture | placeholder (trial first!) | — (audit item 7) |
| FocusMe / Cold Turkey / Plucky / Focuser | E2/E3 enforcement | placeholders pending your audit | `enforcement-audit/` |
| Windows policies (AppLocker / Assigned Access / WDAC) | E3 | documented only | `windows/*.md` |
| Chrome enterprise policies | managed browser | documented only | `windows/chrome-policies.md` |
| Vision-model proof | optional experiment | **disabled** (needs API key) | `vision-proof/SETUP.md` |

## Why placeholders instead of auto-install

The dossier is explicit (D-005/D-006): do not adopt enforcement
backends from READMEs. Each external tool has a Defender report,
licence, or bypass behaviour that YOU must audit in a controlled
environment first (`enforcement-audit/` maps to your Manual Audit
Queue). Until the audit passes, the adapter refuses to arm and says so.

## Enabling anything

1. Follow the integration's SETUP guide (install / configure).
2. Edit `~/.dhriti/dhriti.config.json` → `adapters.<name>.enabled: true`
   (+ executable/commands where relevant).
3. `dhriti adapter status` — the probe must say INSTALLED.
4. Only then can it be listed in `enforcement.required_adapters`.
   Otherwise sessions stay ARMING_FAILED and the experiment record
   discloses why. Nothing pretends.
