@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title Power BI Academy - ระบบเรียนและฝึกทักษะ Power BI
cd /d "%~dp0"
echo กำลังเปิด Power BI Academy...
echo เปิดเบราว์เซอร์ที่ http://localhost:8508
"%PY%" -m streamlit run powerbi_academy.py --server.port 8508
pause
