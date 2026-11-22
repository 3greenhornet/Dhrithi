<#
.SYNOPSIS
    Dhriti Windows Autostart & Desktop Shortcut Setup
.DESCRIPTION
    Registers a Windows Task Scheduler logon task to launch Dhriti App upon user sign-in
    with a 15-second delay, and creates a desktop shortcut.
#>

param(
    [ValidateSet("Install", "Status", "Remove")]
    [string]$Action = "Install"
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BatPath = Join-Path $RepoRoot "Launch-Dhriti-App.bat"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$StartupDir = [Environment]::GetFolderPath("Startup")
$DesktopShortcutPath = Join-Path $DesktopDir "Dhriti Placement OS.lnk"
$StartupShortcutPath = Join-Path $StartupDir "Dhriti Placement OS.lnk"

switch ($Action) {
    "Install" {
        Write-Host "==> Installing Dhriti Autostart..." -ForegroundColor Cyan

        # 1. Create Desktop Shortcut
        try {
            $WScriptShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WScriptShell.CreateShortcut($DesktopShortcutPath)
            $Shortcut.TargetPath = $BatPath
            $Shortcut.WorkingDirectory = $RepoRoot
            $Shortcut.Description = "Dhriti Placement Guardian & OS"
            $Shortcut.Save()
            Write-Host "[+] Desktop shortcut created: $DesktopShortcutPath" -ForegroundColor Green
        } catch {
            Write-Warning "Failed to create desktop shortcut: $_"
        }

        # 2. Create User Startup Folder Shortcut (Zero Admin Elevation Required, 100% Reliable)
        try {
            $WScriptShell = New-Object -ComObject WScript.Shell
            $StartupShortcut = $WScriptShell.CreateShortcut($StartupShortcutPath)
            $StartupShortcut.TargetPath = $BatPath
            $StartupShortcut.WorkingDirectory = $RepoRoot
            $StartupShortcut.Description = "Dhriti Placement Guardian Autostart"
            $StartupShortcut.Save()
            Write-Host "[+] Startup shortcut created in Windows Startup: $StartupShortcutPath" -ForegroundColor Green
        } catch {
            Write-Warning "Failed to create startup shortcut: $_"
        }
    }

    "Status" {
        Write-Host "==> Checking Dhriti Autostart Status..." -ForegroundColor Cyan
        if (Test-Path $StartupShortcutPath) {
            Write-Host "[+] Autostart shortcut is ACTIVE in Windows Startup folder: $StartupShortcutPath" -ForegroundColor Green
        } else {
            Write-Host "[-] Autostart shortcut is NOT installed in Startup folder." -ForegroundColor Yellow
        }

        if (Test-Path $DesktopShortcutPath) {
            Write-Host "[+] Desktop Shortcut exists: $DesktopShortcutPath" -ForegroundColor Green
        } else {
            Write-Host "[-] Desktop Shortcut not found on user Desktop." -ForegroundColor Yellow
        }
    }

    "Remove" {
        Write-Host "==> Removing Dhriti Autostart..." -ForegroundColor Cyan
        if (Test-Path $StartupShortcutPath) {
            Remove-Item -Path $StartupShortcutPath -Force
            Write-Host "[+] Startup shortcut removed." -ForegroundColor Green
        } else {
            Write-Host "[*] No startup shortcut found."
        }

        if (Test-Path $DesktopShortcutPath) {
            Remove-Item -Path $DesktopShortcutPath -Force
            Write-Host "[+] Desktop shortcut removed." -ForegroundColor Green
        }
    }
}
