@echo off
chcp 65001 >nul
title Power BI Academy - ระบบเรียนและฝึกทักษะ Power BI
cd /d "%~dp0"
echo กำลังเปิด Power BI Academy...
echo เปิดเบราว์เซอร์ที่ http://localhost:8508
python -m streamlit run powerbi_academy.py --server.port 8508
pause
