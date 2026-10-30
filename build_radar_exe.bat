@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Build MEGAMU Radar .EXE
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo       MEGAMU RADAR & ENTITY SCANNER - TIẾN TRÌNH BUILD FILE .EXE
echo ==============================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo [LỖI] Không tìm thấy Python trong PATH!
    pause
    exit /b 1
)

echo [1/3] Kiểm tra PyInstaller...
python -c "import PyInstaller" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Đang cài đặt PyInstaller...
    pip install pyinstaller
)

echo [2/3] Đang đóng gói MEGAMU_Radar.exe...
python -m PyInstaller --noconfirm --clean meg_radar.spec

if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo.
    echo [LỖI] Đóng gói thất bại!
    pause
    exit /b 1
)

echo [3/3] Hoàn tất build!
if exist "dist\MEGAMU_Radar.exe" (
    echo.
    echo ==============================================================================
    echo [THÀNH CÔNG] File chạy độc lập: dist\MEGAMU_Radar.exe
    echo ==============================================================================
)
echo.
pause

