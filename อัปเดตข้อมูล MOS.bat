@echo off
chcp 65001 >nul
title อัปเดตข้อมูล MOS ประจำวัน
setlocal enabledelayedexpansion

set "BASE=C:\Users\p\OneDrive - Modernform Tower Co Ltd\Cue_IE_PD\ฝ่ายซ่อมบำรุงรักษา"
set "PY=python"

echo ============================================================
echo   อัปเดตข้อมูล MOS ประจำวัน
echo ============================================================
echo.
echo ขั้นตอนทั้งหมดทำให้อัตโนมัติ:
echo   1. ย้ายไฟล์ export จาก Downloads เข้าโฟลเดอร์ลงวันที่
echo   2. ตรวจคุณภาพข้อมูลก่อน (ถ้ามี error จะหยุด ไม่เขียนอะไร)
echo   3. อัปเดตฐานข้อมูลหลักทั้ง 3 เรื่อง + สร้าง parquet ให้แดชบอร์ด
echo   4. สั่ง Excel คำนวณสูตรและเซฟให้เอง
echo.
echo ก่อนรัน: ดึง export 2 ไฟล์จาก MOS ไว้ในโฟลเดอร์ Downloads
echo   r-jobtran-mc-2-excel_*.xls   (ใบงานรายเครื่อง)
echo   r-jobtran-oee_*.xls          (OEE รายเครื่อง-รายวัน)
echo.
pause

echo.
echo [1/4] ย้ายไฟล์เข้าโฟลเดอร์ลงวันที่...
%PY% "%~dp0etl_prepare.py"
if errorlevel 1 goto :failed

echo.
echo [2/4] ตรวจคุณภาพข้อมูล...
%PY% "%BASE%\00_ETL_Pipeline\update_mos.py" --check
if errorlevel 1 goto :failed
echo.
choice /C YN /M "ด่านตรวจผ่านแล้ว จะอัปเดตจริงไหม"
if errorlevel 2 goto :cancelled

echo.
echo [3/4] อัปเดตฐานข้อมูลหลัก...
%PY% "%BASE%\00_ETL_Pipeline\update_mos.py"
if errorlevel 1 goto :failed

echo.
echo [4/4] สั่ง Excel คำนวณสูตรและเซฟ...
%PY% "%~dp0etl_recalc_excel.py"
if errorlevel 1 goto :failed

echo.
echo ============================================================
echo   เสร็จเรียบร้อย
echo ============================================================
echo   แดชบอร์ดพอร์ต 8503 กับ 8507 จะเห็นข้อมูลใหม่ในรอบรีเฟรชถัดไป
echo   Power BI ให้กด Refresh All เอง
echo.
pause
exit /b 0

:cancelled
echo.
echo ยกเลิกแล้ว ไม่มีการเขียนไฟล์ใด ๆ
pause
exit /b 0

:failed
echo.
echo ============================================================
echo   หยุดกลางทาง — ยังไม่ได้อัปเดตครบ
echo ============================================================
echo   อ่านข้อความ error ด้านบน แล้วแก้ก่อนรันใหม่
echo   ไฟล์ต้นฉบับถูกสำรองไว้ที่ _backup_ROLLBACK_ ลงวันที่แล้ว
echo.
pause
exit /b 1
