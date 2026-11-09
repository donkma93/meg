@echo off
chcp 65001 >nul
title KHOI DONG LAI MEGAMU AUTO TRAIN DASHBOARD
cls
echo =====================================================================
echo  ĐANG DỪNG TIẾN TRÌNH CŨ VÀ KHỞI ĐỘNG BẢN SỬA MỚI NHẤT...
echo =====================================================================
echo.

echo 1. Dang dong giao dien Dashboard cu...
taskkill /F /FI "WINDOWTITLE eq MEGAMU Auto Train*" >nul 2>&1
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*meg_gui.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

timeout /t 1 /nobreak >nul

echo 2. Dang khoi dong Dashboard moi voi ma nguon da sua loi DS...
cd /d "C:\Users\donpv\Desktop\meg"
start "" python -u meg_gui.py

echo.
echo =====================================================================
echo  THANH CONG! Giao dien moi da duoc mo tren Desktop.
echo =====================================================================
timeout /t 3 >nul
exit

