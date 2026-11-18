@echo off
REM Use the project .venv when the installer created one (e.g. machine Python too new)
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
REM เปิดระบบบริหารพลังงานโรงงานด้วย Streamlit (ดับเบิลคลิกไฟล์นี้ได้เลย)
REM ใช้พอร์ต 8504 — ถ้าจะแชร์ในวง LAN ให้เปิด firewall rule พอร์ตนี้เพิ่ม
cd /d "%~dp0"
"%PY%" -m streamlit run energy_monitor.py --server.port 8504 --server.headless true
pause
