@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
REM Make THIS computer the only one allowed to run the MOS / Solar data updates.
REM All logic and all Thai text live in the .py, because Thai characters and
REM parentheses inside batch echo lines break cmd.exe. Keep this file ASCII-only.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
title Set update machine
"%PY%" "%~dp0ตั้งเครื่องอัปเดต.py" %*
echo.
pause
