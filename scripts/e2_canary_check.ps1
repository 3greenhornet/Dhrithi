# e2_canary_check.ps1 -- D-081: prove the hosts-file block is still live.
# Expected output statuses: alive | tampered | missing_entry | unknown
param(
    [string]$Canary = "dhriti-canary.invalid",
    [int]$FailExit = 1
)

try {
    $answers = Resolve-DnsName -Name $Canary -ErrorAction Stop |
        Select-Object -ExpandProperty IPAddress -ErrorAction SilentlyContinue
} catch {
    Write-Output "missing_entry: $Canary did not resolve. Add '0.0.0.0 $Canary' to hosts (see dhriti.canary.hosts_line)."
    exit $FailExit
}

$blackhole = @("0.0.0.0", "127.0.0.1")
$public = $answers | Where-Object { $blackhole -notcontains $_ }

if (-not $public) {
    Write-Output "alive: hosts-file block is live ($Canary -> $($answers -join ', '))"
    exit 0
} else {
    Write-Output "tampered: $Canary resolved to $($public -join ', ') -- the E2 block is gone. Emit guard_e2_canary_missing and re-apply hosts-block.ps1."
    exit $FailExit
}
