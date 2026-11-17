# chaos_drills.ps1 -- Dhriti Guard Kit monthly fault-injection ritual (Windows).
# Guided semi-automation: cheap assertions are checked; the human reads states.
param([string]$Drill = "all")
$fail = 0

function Manual($msg) { Write-Host "MANUAL $msg" }

if ($Drill -eq "all" -or $Drill -eq "1") {
  Write-Host "--- Drill 1: dead daemon mid-session (RECOVERED path)"
  Manual "kill the daemon while a session is ACTIVE; restart it"
  Manual "expect: dhriti day status shows RECOVERED"
  try { dhriti verify | Out-Null; Write-Host "PASS  verify chain" }
  catch { Write-Host "FAIL  verify chain"; $fail++ }
}

if ($Drill -eq "all" -or $Drill -eq "2") {
  Write-Host "--- Drill 2: policy TTL lapse (D-062)"
  Manual "stop daemon; browse a chat site; expect LOCAL deterministic burst toll only"
  Manual "restart daemon; expect policy returns within one poll cycle"
}

if ($Drill -eq "all" -or $Drill -eq "3") {
  Write-Host "--- Drill 3: sidecar quarantine (D-052/D-064)"
  Manual "corrupt-shape a sidecar (truncate middle bytes); expect *.corrupt-<ts> + retry"
  Manual "renamed/locked file must NOT quarantine (locked is not corrupt)"
}

if ($Drill -eq "all" -or $Drill -eq "4") {
  Write-Host "--- Drill 4: token revocation"
  Manual "rotate bridge token; old token must 401 + bridge_token_rejected (rate-limited)"
}

if ($Drill -eq "all" -or $Drill -eq "5") {
  Write-Host "--- Drill 5: E2 canary (D-081)"
  $out = & powershell -File "$PSScriptRoot\e2_canary_check.ps1"
  Write-Host $out
  if ($LASTEXITCODE -ne 0) { $fail++ }
}

if ($fail -gt 0) { Write-Host "drills FAILED: $fail"; exit 1 }
Write-Host "drills complete"
