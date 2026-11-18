@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title Python Academy - ระบบเรียนและฝึกเขียน Python
cd /d "%~dp0"
echo กำลังเปิด Python Academy...
echo เปิดเบราว์เซอร์ที่ http://localhost:8509
"%PY%" -m streamlit run python_academy.py --server.port 8509
pause
