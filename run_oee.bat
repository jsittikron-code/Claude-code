@echo off
chcp 65001 >nul
title ระบบบริหาร OEE
cd /d "%~dp0"
echo กำลังเปิดระบบบริหาร OEE...
python -m streamlit run oee_manager.py --server.port 8506
pause
