@echo off
chcp 65001 >nul
title Maintenance Dashboard - งานซ่อมบำรุง 6 หมวด
cd /d "%~dp0"
echo กำลังเปิด Dashboard งานซ่อมบำรุง 6 หมวด...
python -m streamlit run maintenance_dashboard.py --server.port 8505
pause
