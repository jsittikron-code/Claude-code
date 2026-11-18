@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title Dashboard ภาพรวมฝ่ายวิศวกรรมกระบวนการผลิต
cd /d "%~dp0"
echo กำลังเปิด Dashboard ภาพรวมฝ่ายวิศวกรรมกระบวนการผลิต...
"%PY%" -m streamlit run overview_dashboard.py --server.port 8507
pause
