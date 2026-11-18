@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title ลูกโลกเที่ยวบินสด
cd /d "%~dp0"
echo กำลังเปิดลูกโลกเที่ยวบินสด...
"%PY%" -m streamlit run flight_globe.py --server.port 8509
pause
