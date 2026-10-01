@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\configure-firebase.ps1" %*
set "setupExitCode=%errorlevel%"
pause
exit /b %setupExitCode%
