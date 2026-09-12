@echo off
chcp 65001 >nul
title ETL Studio
cd /d "%~dp0"
echo กำลังเปิด ETL Studio...
python -m streamlit run etl_studio.py --server.port 8507
pause
