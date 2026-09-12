@echo off
chcp 65001 >nul
title เปิด Firewall พอร์ต Dashboard ทั้งหมด (8503-8511)

echo ============================================================
echo   เปิดพอร์ต 8503-8511 ใน Windows Firewall
echo   เพื่อให้เพื่อนร่วมงานในเน็ตเวิร์กเดียวกันเข้าดู dashboard ได้
echo.
echo     8503 = ศูนย์ปฏิบัติการเครื่องจักร (Workcenter)
echo     8504 = ระบบบริหารพลังงานโรงงาน
echo     8505 = ระบบบริหารใบงานซ่อม
echo     8506 = ระบบบริหาร OEE
echo     8507 = Dashboard ภาพรวม (Overview)
echo     8508 = Power BI Academy (ระบบเรียนและฝึกทักษะ Power BI)
echo     8509 = Python Academy (ระบบเรียนและฝึกเขียน Python)
echo     8510 = Dashboard ฝ่ายผลิต
echo     8511 = Dashboard วิศวกรรมซ่อมบำรุง
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
netsh advfirewall firewall delete rule name="MDF Dashboards 8503-8511" >nul 2>&1
REM ลบ rule ชื่อเดิมสมัยที่ยังมีแค่ 8503-8509 ด้วย ไม่งั้นจะค้างเป็น rule ซ้ำซ้อน
netsh advfirewall firewall delete rule name="MDF Dashboards 8503-8509" >nul 2>&1

echo [2/2] เพิ่ม rule ใหม่ (พอร์ต 8503-8511)...
netsh advfirewall firewall add rule name="MDF Dashboards 8503-8511" dir=in action=allow protocol=TCP localport=8503-8511 profile=domain,private

echo.
if %errorLevel% equ 0 (
    echo ============================================================
    echo   สำเร็จ! เปิดพอร์ต 8503-8511 เรียบร้อย
    echo ============================================================
    echo.
    echo ขั้นตอนต่อไป:
    echo   1. ดับเบิลคลิก run_*.bat ของระบบที่ต้องการแชร์ แล้วปล่อยหน้าต่างเปิดค้างไว้
    echo      (ระบบย่อยจะกดเปิดจาก Dashboard ภาพรวมได้ ก็ต่อเมื่อแอปนั้นรันอยู่)
    echo   2. ส่งลิงก์ Dashboard ภาพรวมให้เพื่อนร่วมงาน:
    echo.
    echo        http://%COMPUTERNAME%:8507
    echo.
    echo   หมายเหตุ: เพื่อนต้องอยู่ในเน็ตเวิร์กออฟฟิศเดียวกัน
    echo             และเครื่องนี้ต้องเปิดพร้อมรันแอปอยู่ตลอด
) else (
    echo เพิ่ม rule ไม่สำเร็จ - อาจถูกนโยบายของบริษัทล็อกไว้
    echo กรุณาติดต่อฝ่าย IT เพื่อขอเปิดพอร์ต 8503-8511 (TCP ขาเข้า)
)
echo.
pause
