@echo off
REM เปิดระบบบริหารพลังงานโรงงานด้วย Streamlit (ดับเบิลคลิกไฟล์นี้ได้เลย)
REM ใช้พอร์ต 8504 — ถ้าจะแชร์ในวง LAN ให้เปิด firewall rule พอร์ตนี้เพิ่ม
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m streamlit run energy_monitor.py --server.port 8504 --server.headless true
pause
