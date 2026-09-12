@echo off
chcp 65001 >nul
title ลิงก์แชร์ Dashboard วันนี้
echo ============================================================
echo   ลิงก์แชร์ Dashboard ภาพรวม (เช็ค IP ปัจจุบันอัตโนมัติ)
echo ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Sort-Object { $_.IPAddress -notlike '10.*' } | Select-Object -First 1).IPAddress; $link = 'http://' + $ip + ':8507'; Set-Clipboard -Value $link; Write-Host ''; Write-Host ('   ลิงก์ IP วันนี้     :  ' + $link); Write-Host ('   ลิงก์ชื่อเครื่อง (ถาวร):  http://' + $env:COMPUTERNAME + ':8507'); Write-Host ''; Write-Host '   คัดลอกลิงก์ IP ไว้ในคลิปบอร์ดให้แล้ว — กด Ctrl+V วางส่งให้เพื่อนได้เลย'"
echo.
pause
