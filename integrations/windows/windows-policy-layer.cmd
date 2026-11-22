@echo off
:: ============================================================
:: Dhriti - Layer 0: MACHINE POLICY  (D-082, incognito closure)
:: Run from an ELEVATED Command Prompt (Administrator).
::
:: Closes, at a level above any browser toggle and above Incognito:
::   1. Incognito / InPrivate windows - disabled entirely
::      (Chrome+Brave: IncognitoModeAvailability=1, Edge: InPrivateModeAvailability=1)
::   2. Secure DNS / DoH - forced off, so the hosts-file ring (ring 1)
::      cannot be bypassed; the user toggle shows 'managed' and is locked
::   3. URLBlocklist - kills the Images entry hosts AND the udm=2 / tbm=isch
::      params. Query matching is TOKEN-BASED and ORDER-INSENSITIVE per the
::      official filter format, so 'search?udm=2' matches the param in any
::      position. Normal search (no udm/tbm) is untouched.
::
:: Verify afterwards:  chrome://policy | brave://policy | edge://policy
::                     then:  python policy_health.py
:: Revert: see the REVERT block at the bottom of this file.
:: Caveat: if a URLAllowlist policy exists, it takes precedence over
::         URLBlocklist - do not maintain an allowlist that covers Google.
:: ============================================================

:: ---------- Google Chrome ----------
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome" /v IncognitoModeAvailability /t REG_DWORD /d 1 /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome" /v DnsOverHttpsMode /t REG_SZ /d off /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome" /v ForceSafeSearch /t REG_DWORD /d 1 /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 1 /t REG_SZ /d "images.google.com" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 2 /t REG_SZ /d "lens.google.com" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 3 /t REG_SZ /d "google.com/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 4 /t REG_SZ /d "google.com/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 5 /t REG_SZ /d "google.com/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 6 /t REG_SZ /d "google.com/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 7 /t REG_SZ /d "google.co.in/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 8 /t REG_SZ /d "google.co.in/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 9 /t REG_SZ /d "google.co.in/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 10 /t REG_SZ /d "google.co.in/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 11 /t REG_SZ /d "google.co.uk/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 12 /t REG_SZ /d "google.co.uk/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 13 /t REG_SZ /d "google.co.uk/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 14 /t REG_SZ /d "google.co.uk/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 15 /t REG_SZ /d "google.ca/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 16 /t REG_SZ /d "google.ca/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 17 /t REG_SZ /d "google.ca/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 18 /t REG_SZ /d "google.ca/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 19 /t REG_SZ /d "google.com.au/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 20 /t REG_SZ /d "google.com.au/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 21 /t REG_SZ /d "google.com.au/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 22 /t REG_SZ /d "google.com.au/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 23 /t REG_SZ /d "google.de/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 24 /t REG_SZ /d "google.de/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 25 /t REG_SZ /d "google.de/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 26 /t REG_SZ /d "google.de/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 27 /t REG_SZ /d "google.fr/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 28 /t REG_SZ /d "google.fr/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 29 /t REG_SZ /d "google.fr/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /v 30 /t REG_SZ /d "google.fr/imgres" /f

:: ---------- Brave ----------
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave" /v IncognitoModeAvailability /t REG_DWORD /d 1 /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave" /v DnsOverHttpsMode /t REG_SZ /d off /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave" /v ForceSafeSearch /t REG_DWORD /d 1 /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave" /v TorDisabled /t REG_DWORD /d 1 /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 1 /t REG_SZ /d "images.google.com" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 2 /t REG_SZ /d "lens.google.com" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 3 /t REG_SZ /d "google.com/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 4 /t REG_SZ /d "google.com/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 5 /t REG_SZ /d "google.com/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 6 /t REG_SZ /d "google.com/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 7 /t REG_SZ /d "google.co.in/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 8 /t REG_SZ /d "google.co.in/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 9 /t REG_SZ /d "google.co.in/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 10 /t REG_SZ /d "google.co.in/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 11 /t REG_SZ /d "google.co.uk/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 12 /t REG_SZ /d "google.co.uk/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 13 /t REG_SZ /d "google.co.uk/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 14 /t REG_SZ /d "google.co.uk/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 15 /t REG_SZ /d "google.ca/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 16 /t REG_SZ /d "google.ca/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 17 /t REG_SZ /d "google.ca/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 18 /t REG_SZ /d "google.ca/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 19 /t REG_SZ /d "google.com.au/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 20 /t REG_SZ /d "google.com.au/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 21 /t REG_SZ /d "google.com.au/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 22 /t REG_SZ /d "google.com.au/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 23 /t REG_SZ /d "google.de/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 24 /t REG_SZ /d "google.de/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 25 /t REG_SZ /d "google.de/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 26 /t REG_SZ /d "google.de/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 27 /t REG_SZ /d "google.fr/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 28 /t REG_SZ /d "google.fr/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 29 /t REG_SZ /d "google.fr/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\BraveSoftware\Brave\URLBlocklist" /v 30 /t REG_SZ /d "google.fr/imgres" /f

:: ---------- Microsoft Edge ----------
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v InPrivateModeAvailability /t REG_DWORD /d 1 /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v DnsOverHttpsMode /t REG_SZ /d off /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge" /v ForceSafeSearch /t REG_DWORD /d 1 /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 1 /t REG_SZ /d "images.google.com" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 2 /t REG_SZ /d "lens.google.com" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 3 /t REG_SZ /d "google.com/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 4 /t REG_SZ /d "google.com/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 5 /t REG_SZ /d "google.com/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 6 /t REG_SZ /d "google.com/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 7 /t REG_SZ /d "google.co.in/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 8 /t REG_SZ /d "google.co.in/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 9 /t REG_SZ /d "google.co.in/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 10 /t REG_SZ /d "google.co.in/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 11 /t REG_SZ /d "google.co.uk/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 12 /t REG_SZ /d "google.co.uk/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 13 /t REG_SZ /d "google.co.uk/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 14 /t REG_SZ /d "google.co.uk/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 15 /t REG_SZ /d "google.ca/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 16 /t REG_SZ /d "google.ca/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 17 /t REG_SZ /d "google.ca/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 18 /t REG_SZ /d "google.ca/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 19 /t REG_SZ /d "google.com.au/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 20 /t REG_SZ /d "google.com.au/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 21 /t REG_SZ /d "google.com.au/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 22 /t REG_SZ /d "google.com.au/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 23 /t REG_SZ /d "google.de/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 24 /t REG_SZ /d "google.de/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 25 /t REG_SZ /d "google.de/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 26 /t REG_SZ /d "google.de/imgres" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 27 /t REG_SZ /d "google.fr/search?udm=2" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 28 /t REG_SZ /d "google.fr/search?tbm=isch" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 29 /t REG_SZ /d "google.fr/imghp" /f
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Edge\URLBlocklist" /v 30 /t REG_SZ /d "google.fr/imgres" /f

:: ---------- REVERT (only if you intentionally want the hole back) ----------
:: REG DELETE "HKLM\SOFTWARE\Policies\Google\Chrome" /v IncognitoModeAvailability /f
:: REG DELETE "HKLM\SOFTWARE\Policies\Google\Chrome" /v DnsOverHttpsMode /f
:: REG DELETE "HKLM\SOFTWARE\Policies\Google\Chrome\URLBlocklist" /f
:: (same three lines for the Brave and Edge keys)

echo Done. Restart all browsers, then verify at chrome://policy / brave://policy / edge://policy
pause
