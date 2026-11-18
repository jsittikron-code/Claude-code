@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title จัดการผู้ใช้แดชบอร์ด
cd /d "%~dp0"
"%PY%" manage_users.py
pause
