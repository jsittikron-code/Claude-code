@echo off
chcp 65001 >nul
title Python Academy - ระบบเรียนและฝึกเขียน Python
cd /d "%~dp0"
echo กำลังเปิด Python Academy...
echo เปิดเบราว์เซอร์ที่ http://localhost:8509
python -m streamlit run python_academy.py --server.port 8509
pause
