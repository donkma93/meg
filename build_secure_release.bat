@echo off
setlocal
chcp 65001 >nul
title MEGAMU Auto Train Dashboard - NUITKA NATIVE C MACHINE CODE BUILDER
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo   HE THONG BIEN DICH NATIVE C MACHINE CODE - CHONG DICH NGUOC (NUITKA v4.3)
echo ==============================================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    color 0c
    echo [LOI] Khong tim thay Python trong PATH!
    pause
    exit /b 1
)

python build_secure_release.py %*
if errorlevel 1 (
    color 0c
    echo.
    echo [LOI] Tien trinh build that bai!
    pause
    exit /b 1
)

echo.
pause
