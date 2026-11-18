@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
REM First-time setup on a new machine after git clone.
REM All Thai text lives in the .py, because Thai characters and parentheses
REM inside batch echo lines break cmd.exe. Keep this file ASCII-only.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
title First-time setup
"%PY%" "%~dp0ติดตั้งเครื่องใหม่.py"
echo.
pause
