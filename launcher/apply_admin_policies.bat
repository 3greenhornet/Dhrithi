@echo off
:: ============================================================
:: Dhriti - Elevated Policy & Hosts Block Runner
:: ============================================================
net session >nul 2>&1
if %errorLevel% == 0 (
    echo ============================================================
    echo [OK] Running with Administrator privileges...
    echo ============================================================
    cd /d "%~dp0\.."
    echo 1. Applying Windows Registry Machine Policies (Incognito & DoH lockout)...
    call integrations\windows\windows-policy-layer.cmd
    echo.
    echo 2. Arming Ring 1 DNS Image Block & Canary...
    python -m dhriti.e2_images_block arm
    echo.
    echo 3. Checking canary status...
    python -m dhriti.cli canary check --hosts-audit
    echo.
    echo ============================================================
    echo [SUCCESS] Layer 0 and Layer 1 enforcement armed successfully.
    echo ============================================================
    pause
) else (
    echo Requesting Administrator elevation...
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~dp0apply_admin_policies.bat\"' -Verb RunAs"
)

