@echo off
chcp 65001 >nul
title ลูกโลกเที่ยวบินสด
cd /d "%~dp0"
echo กำลังเปิดลูกโลกเที่ยวบินสด...
python -m streamlit run flight_globe.py --server.port 8509
pause
