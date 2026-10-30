@echo off
cd /d "%~dp0"
chcp 65001 >nul
title MEGAMU Entity Radar & Nearby Scanner (Live Sci-Fi HUD)
echo ============================================================
echo   MEGAMU ENTITY RADAR & SCANNER (PyQt5 LIVE HUD)
echo   Zero-Injection ReadProcessMemory RAM Reader
echo ============================================================

if exist "MEGAMU_Radar.exe" (
    echo Đang khởi chạy MEGAMU_Radar.exe...
    start "" "MEGAMU_Radar.exe"
    exit /b 0
)

if exist "dist\MEGAMU_Radar.exe" (
    echo Đang khởi chạy dist\MEGAMU_Radar.exe...
    start "" "dist\MEGAMU_Radar.exe"
    exit /b 0
)

python meg_radar_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Loi] Chuong trinh bi dung voi ma loi %ERRORLEVEL%
    pause
)

