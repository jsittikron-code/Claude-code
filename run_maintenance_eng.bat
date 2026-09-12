@echo off
chcp 65001 >nul
title Maintenance Engineering Dashboard - วิศวกรรมซ่อมบำรุง
cd /d "%~dp0"
echo กำลังเปิด Maintenance Engineering Dashboard... http://localhost:8511
python -m streamlit run maintenance_eng_dashboard.py --server.port 8511
pause
