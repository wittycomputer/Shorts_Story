@echo off
chcp 65001 >nul
if not exist "%~dp0backend\.venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
"%~dp0backend\.venv\Scripts\python.exe" -X utf8 "%~dp0backend\check_environment.py"
set "checkExitCode=%errorlevel%"
pause
exit /b %checkExitCode%
