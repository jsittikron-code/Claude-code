@echo off
chcp 65001 >nul
title Dashboard ภาพรวมฝ่ายวิศวกรรมกระบวนการผลิต
cd /d "%~dp0"
echo กำลังเปิด Dashboard ภาพรวมฝ่ายวิศวกรรมกระบวนการผลิต...
python -m streamlit run overview_dashboard.py --server.port 8507
pause
