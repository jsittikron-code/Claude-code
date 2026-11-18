@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title ระบบบริหาร OEE
cd /d "%~dp0"
echo กำลังเปิดระบบบริหาร OEE...
"%PY%" -m streamlit run oee_manager.py --server.port 8506
pause
