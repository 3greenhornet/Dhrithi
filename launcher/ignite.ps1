# ignite.ps1 — Dhriti workspace ignition (dossier 6.2)
#
# Opens the actual project, files, terminal and browser work profile,
# then prints the first command. Access restriction alone does not
# start work; ignition removes the friction between "window open" and
# "first action taken".
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File ignite.ps1 -Profile C:\Users\you\.dhriti\profiles\ignite.coding.json
#
# Profile schema (see profiles/ignite.example.json):
#   project_dir, files[], terminal_command, first_command, browser{
#     profile, start_url }

param(
    [Parameter(Mandatory = $true)]
    [string]$Profile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Profile)) {
    Write-Host "ignite: profile not found: $Profile"
    Write-Host "ignite: copy launcher/profiles/ignite.example.json to ~/.dhriti/profiles/ and edit it."
    exit 1
}

$p = Get-Content $Profile -Raw | ConvertFrom-Json

Write-Host "ignite: opening project $($p.project_dir)"
if ($p.project_dir -and (Test-Path $p.project_dir)) {
    Start-Process explorer.exe $p.project_dir
} else {
    Write-Host "ignite: project_dir missing or invalid - skipped"
}

foreach ($file in $p.files) {
    if (Test-Path $file) {
        Write-Host "ignite: opening $file"
        Start-Process $file
    } else {
        Write-Host "ignite: file not found, skipped: $file"
    }
}

if ($p.terminal_command) {
    Write-Host "ignite: launching terminal"
    # Windows Terminal if available, else conhost
    $wt = Get-Command wt.exe -ErrorAction SilentlyContinue
    if ($wt) {
        Start-Process wt.exe -ArgumentList "new-tab", "-d", $p.project_dir
    } else {
        Start-Process conhost.exe -ArgumentList "--%", "cmd", "/K", "cd /d $($p.project_dir)"
    }
}

if ($p.browser.profile) {
    Write-Host "ignite: launching browser work profile '$($p.browser.profile)'"
    $chromeArgs = @("--profile-directory=$($p.browser.profile)")
    if ($p.browser.start_url) { $chromeArgs += $p.browser.start_url }
    $chrome = Get-Command chrome.exe -ErrorAction SilentlyContinue
    if (-not $chrome) {
        $chrome = Get-Command "C:\Program Files\Google\Chrome\Application\chrome.exe" -ErrorAction SilentlyContinue
    }
    if ($chrome) { Start-Process $chrome.Source -ArgumentList $chromeArgs }
    else { Write-Host "ignite: chrome not found - skipped" }
}

Write-Host ""
Write-Host "ignite: first action (from your own plan):"
Write-Host "  $($p.first_command)"
Write-Host ""
Write-Host "ignite: expected obstacle + IF-THEN (from your plan):"
Write-Host "  obstacle: $($p.expected_obstacle)"
Write-Host "  if-then:  $($p.if_then)"
Write-Host ""
Write-Host "ignite: done. The terminal is waiting."
