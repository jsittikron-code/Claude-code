@echo off
REM เปิดระบบ Monitoring กระบวนการผลิตด้วย Streamlit (ดับเบิลคลิกไฟล์นี้ได้เลย)
REM ใช้พอร์ต 8502 ให้ตรงกับ firewall rule ที่เปิดไว้สำหรับแชร์ในวง LAN
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m streamlit run monitor.py --server.port 8502 --server.headless true
pause
