@echo off
chcp 65001 >nul
title Production Dashboard - แดชบอร์ดฝ่ายผลิต
cd /d "%~dp0"
echo กำลังเปิด Production Dashboard... http://localhost:8510
python -m streamlit run production_dashboard.py --server.port 8510
pause
