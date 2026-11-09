# hosts-block.ps1 — Dhriti E2 DNS blocking (manual apply/remove)
#
# The daemon GENERATES <dhriti-home>/hosts/dhriti-block.txt from the
# active policy. Applying it to the real hosts file needs an elevated
# shell, so it stays this deliberate manual step (audit-friendly,
# reversible, never silent).
#
# Usage (run as Administrator):
#   .\hosts-block.ps1 -Apply      # append Dhriti block to the hosts file
#   .\hosts-block.ps1 -Restore    # remove the Dhriti block
#
# The script is idempotent: applying twice never duplicates lines.

param(
    [Parameter(Mandatory = $true, ParameterSetName = "Apply")]
    [switch]$Apply,
    [Parameter(Mandatory = $true, ParameterSetName = "Restore")]
    [switch]$Restore,
    [string]$DhritiHome = (Join-Path $env:USERPROFILE ".dhriti")
)

$ErrorActionPreference = "Stop"
$hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
$blockFile = Join-Path $DhritiHome "hosts\dhriti-block.txt"
$markerFile = Join-Path $DhritiHome "hosts\APPLIED"
$beginMark = "# Dhriti E2 hosts block - BEGIN"
$endMark = "# Dhriti E2 hosts block - END"

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "hosts-block: administrator required. Right-click PowerShell -> Run as administrator."
    exit 1
}

function Remove-DhritiBlock {
    $lines = Get-Content $hostsPath -ErrorAction SilentlyContinue
    $kept = New-Object System.Collections.Generic.List[string]
    $inside = $false
    foreach ($line in $lines) {
        if ($line -eq $beginMark) { $inside = $true; continue }
        if ($line -eq $endMark)   { $inside = $false; continue }
        if (-not $inside) { $kept.Add($line) }
    }
    Set-Content -Path $hostsPath -Value $kept -Encoding ASCII
    if (Test-Path $markerFile) { Remove-Item $markerFile }
    Write-Host "hosts-block: Dhriti block removed from $hostsPath"
}

if ($Restore) {
    Remove-DhritiBlock
    exit 0
}

if (-not (Test-Path $blockFile)) {
    Write-Host "hosts-block: no block file yet. Start the daemon with an open day first"
    Write-Host "hosts-block: (the file is generated at $blockFile)."
    exit 1
}

Remove-DhritiBlock  # idempotency: clean any previous block first

$blockLines = Get-Content $blockFile | Where-Object { $_ -match "^0\.0\.0\.0" }
Add-Content -Path $hostsPath -Value ""
Add-Content -Path $hostsPath -Value $beginMark
Add-Content -Path $hostsPath -Value $blockLines
Add-Content -Path $hostsPath -Value $endMark

# flush DNS cache so the block takes effect immediately
Clear-DnsClientCache -ErrorAction SilentlyContinue

Set-Content -Path $markerFile -Value (Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ")
Write-Host "hosts-block: applied $($blockLines.Count) entries from $blockFile"
Write-Host "hosts-block: marker written; dhriti adapter status will now show hosts_file INSTALLED"
Write-Host "hosts-block: to undo: .\hosts-block.ps1 -Restore"
