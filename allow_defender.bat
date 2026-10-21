@echo off
title Configure Windows Defender for Universal IDE Bridge
echo ======================================================================
echo  Universal IDE Bridge - Windows Security Defender Configuration
echo ======================================================================
echo.
echo Requesting Administrator privileges to add Windows Defender exclusions
echo for Python and your code projects.
echo.
echo In the User Account Control (UAC) dialog that appears, click 'YES'.
echo.

python bridge.py --allow-defender

if %errorlevel% neq 0 (
    echo.
    echo Running direct elevated PowerShell exclusion...
    powershell -NoProfile -Command "Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy RemoteSigned -Command Add-MpPreference -ExclusionPath ''%~dp0..'', ''%~dp0'' -ExclusionProcess ''python.exe''; Write-Host ''[SUCCESS] Windows Defender exclusions configured successfully!'' -ForegroundColor Green; Start-Sleep -Seconds 3'"
)

echo.
pause
