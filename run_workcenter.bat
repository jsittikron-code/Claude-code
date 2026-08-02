@echo off
chcp 65001 >nul
title Workcenter Monitoring - ศูนย์ปฏิบัติการเครื่องจักร
cd /d "%~dp0"
echo กำลังเปิดระบบ Workcenter Monitoring...
python -m streamlit run workcenter_monitor.py --server.port 8503
pause
