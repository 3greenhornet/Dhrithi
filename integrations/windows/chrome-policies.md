# Chrome enterprise policies — managed browser (E1+)

Lead: https://chromeenterprise.google/policies/

## What it is

Chrome/Edge respect Group Policy / registry policy even on Pro
editions. Relevant Dhriti uses:

1. **Force-install the Dhriti Wall extension** so removing it from
   chrome://extensions is not trivial (`ExtensionInstallForcelist`).
2. **Block extension uninstall** (`ExtensionUninstallDisabled`).
3. **URL blocklists** as a browser-level backup to the extension.
4. A managed **work profile** separate from your personal profile.

## Dhriti mapping

- The extension is E1; policies make E1 harder to casually remove —
  still tamper-resistant, not tamper-proof (an admin can undo the
  policy; the daemon records the extension going silent either way).
- Policy path (registry, per-machine):
  `HKLM\Software\Policies\Google\Chrome\...`

## Steps (manual, admin, cold state)

1. Pack the extension as .crx / host it, get the extension ID +
   update URL (self-hosting guide: developer.chrome.com/docs/extensions/how-to/distribute).
2. Set the forcelist policy for that ID.
3. Verify with `chrome://policy` in the browser.
4. Test the escape routes the dossier names: another browser profile,
   another browser entirely, incognito — record what actually stays
   blocked. (Another browser is an E2 problem, not an E1 one.)

## Cautions

- A managed browser is still the user's browser if the user is admin:
  this raises friction, not a wall. That is fine — friction with an
  honest ledger beats a fake prison.
