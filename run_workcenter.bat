@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title Workcenter Monitoring - ศูนย์ปฏิบัติการเครื่องจักร
cd /d "%~dp0"
echo กำลังเปิดระบบ Workcenter Monitoring...
"%PY%" -m streamlit run workcenter_monitor.py --server.port 8503
pause
