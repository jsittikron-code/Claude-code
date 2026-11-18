@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title Maintenance Dashboard - งานซ่อมบำรุง 6 หมวด
cd /d "%~dp0"
echo กำลังเปิด Dashboard งานซ่อมบำรุง 6 หมวด...
"%PY%" -m streamlit run maintenance_dashboard.py --server.port 8505
pause
