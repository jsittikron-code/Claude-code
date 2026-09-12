@echo off
chcp 65001 >nul
title หยุดแดชบอร์ดทุกระบบ (พอร์ต 8503-8511)
echo กำลังหยุดแดชบอร์ดทุกระบบ...
powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -ge 8503 -and $_.LocalPort -le 8511 } | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
echo หยุดเรียบร้อย
pause
