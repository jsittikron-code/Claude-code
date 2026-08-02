@echo off
chcp 65001 >nul
title เปิด Firewall พอร์ต 8503 - Workcenter Monitoring

echo ============================================================
echo   เปิดพอร์ต 8503 ใน Windows Firewall
echo   เพื่อให้เพื่อนร่วมงานในเน็ตเวิร์กเดียวกันเข้าดู dashboard ได้
echo ============================================================
echo.

REM ต้องใช้สิทธิ์ Administrator - ถ้ายังไม่มี ให้ขอผ่าน UAC (จะมีหน้าต่างเด้งให้กดยืนยัน)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ต้องใช้สิทธิ์ Administrator - กำลังขอสิทธิ์...
    echo กรุณากด "Yes" ในหน้าต่างที่เด้งขึ้นมา
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo [1/2] ลบ rule เดิม (ถ้ามี)...
netsh advfirewall firewall delete rule name="Workcenter Monitoring 8503" >nul 2>&1

echo [2/2] เพิ่ม rule ใหม่...
netsh advfirewall firewall add rule name="Workcenter Monitoring 8503" dir=in action=allow protocol=TCP localport=8503 profile=domain,private

echo.
if %errorLevel% equ 0 (
    echo ============================================================
    echo   สำเร็จ! เปิดพอร์ต 8503 เรียบร้อย
    echo ============================================================
    echo.
    echo ขั้นตอนต่อไป:
    echo   1. ดับเบิลคลิก run_workcenter.bat แล้วปล่อยหน้าต่างเปิดค้างไว้
    echo   2. ส่งลิงก์นี้ให้เพื่อนร่วมงาน:
    echo.
    echo        http://%COMPUTERNAME%:8503
    echo.
    echo   หมายเหตุ: เพื่อนต้องอยู่ในเน็ตเวิร์กออฟฟิศเดียวกัน
    echo             และเครื่องนี้ต้องเปิดพร้อมรันแอปอยู่ตลอด
) else (
    echo เพิ่ม rule ไม่สำเร็จ - อาจถูกนโยบายของบริษัทล็อกไว้
    echo กรุณาติดต่อฝ่าย IT เพื่อขอเปิดพอร์ต 8503 (TCP ขาเข้า)
)
echo.
pause
