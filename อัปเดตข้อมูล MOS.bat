@echo off
REM Daily MOS data update. All logic and all Thai text live in etl_run.py,
REM because Thai characters and parentheses inside batch echo lines break cmd.exe.
REM Keep this file ASCII-only.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
title Update MOS data
python "%~dp0etl_run.py" %*
