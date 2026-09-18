@echo off
REM Health check for the dashboard system. All Thai text lives in the .py,
REM because Thai characters and parentheses inside batch echo lines break cmd.exe.
REM Keep this file ASCII-only.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
title Health check
python "%~dp0ตรวจสุขภาพระบบ.py" %*
echo.
pause
