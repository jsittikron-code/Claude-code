@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title Maintenance Engineering Dashboard - วิศวกรรมซ่อมบำรุง
cd /d "%~dp0"
echo กำลังเปิด Maintenance Engineering Dashboard... http://localhost:8511
"%PY%" -m streamlit run maintenance_eng_dashboard.py --server.port 8511
pause
