@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
chcp 65001 >nul
title ETL Studio
cd /d "%~dp0"
echo กำลังเปิด ETL Studio...
"%PY%" -m streamlit run etl_studio.py --server.port 8507
pause
