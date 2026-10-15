@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title MEGAMU Auto Train Dashboard - TAO BAN CAI DAT (INSTALLER)
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo       MEGAMU AUTO TRAIN DASHBOARD - DONG GOI FILE CAI DAT (SETUP.EXE)
echo ==============================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo [LOI] Khong tim thay Python trong PATH!
    pause
    exit /b 1
)

python create_installer.py
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo.
    echo [LOI] Qua trinh tao ban cai dat that bai!
    pause
    exit /b 1
)

echo.
pause
exit /b 0
