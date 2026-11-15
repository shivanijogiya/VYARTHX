@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VYARTHX - starting
echo ============================================================
echo   VYARTHX - AI-Powered City Waste Intelligence Platform
echo ============================================================

rem ---- 1. find Python 3.10+
set "PY="
where py >nul 2>nul && (py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=py -3")
if not defined PY (where python >nul 2>nul && (python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=python"))
if not defined PY (
  echo.
  echo [ERROR] Python 3.10 or newer was not found.
  echo         Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run run.bat again.
  pause
  exit /b 1
)
echo [setup] Using: %PY%

rem ---- 2. virtual environment
if not exist ".venv\Scripts\python.exe" (
  echo [setup] Creating virtual environment ...
  %PY% -m venv .venv
  if errorlevel 1 ( echo [ERROR] Could not create the virtual environment. & pause & exit /b 1 )
)
set "VPY=.venv\Scripts\python.exe"

rem ---- 3. dependencies (only when requirements changed)
fc /b requirements.txt .venv\.installed_requirements.txt >nul 2>nul
if errorlevel 1 (
  echo [setup] Installing dependencies - first run takes a few minutes ...
  "%VPY%" -m pip install --upgrade pip >nul 2>nul
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [setup] Range install failed, trying the pinned lock file ...
    "%VPY%" -m pip install -r requirements.lock
    if errorlevel 1 ( echo [ERROR] Dependency installation failed. See docs\TROUBLESHOOTING.md & pause & exit /b 1 )
  )
  copy /y requirements.txt .venv\.installed_requirements.txt >nul
)

rem ---- 4. env file
if not exist ".env" if exist ".env.example" copy /y ".env.example" ".env" >nul

rem ---- 5. launch
"%VPY%" scripts\launcher.py
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [ERROR] VYARTHX did not start correctly ^(code %RC%^). Check data\runtime\server.log and docs\TROUBLESHOOTING.md
  pause
  exit /b %RC%
)
echo.
echo VYARTHX is running. This window can be closed; use stop.bat to stop the server.
timeout /t 8 >nul
endlocal
