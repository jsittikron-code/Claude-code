@echo off
chcp 65001 >nul
title จัดการผู้ใช้แดชบอร์ด
cd /d "%~dp0"
python manage_users.py
pause
