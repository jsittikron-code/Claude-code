@echo off
REM Daily Solar inverter update (EVE export -> parquet -> dashboard 8504).
REM All logic and all Thai text live in solar_etl.py, because Thai characters
REM and parentheses inside batch echo lines break cmd.exe. Keep this file ASCII-only.
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
title Update Solar data
python "%~dp0solar_etl.py" %*
