@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title Production Dashboard - แดชบอร์ดฝ่ายผลิต
cd /d "%~dp0"
echo กำลังเปิด Production Dashboard... http://localhost:8510
"%PY%" -m streamlit run production_dashboard.py --server.port 8510
pause
