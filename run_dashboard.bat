@echo off
REM เปิด OEE Dashboard ด้วย Streamlit (ดับเบิลคลิกไฟล์นี้ได้เลย)
cd /d "%~dp0"
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m streamlit run app.py
pause
