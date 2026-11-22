@echo off
title MEGAMU Auto Train Dashboard - Qt6 Native (PySide6)
cd /d "%~dp0"

:: Kiem tra quyen Administrator va tu dong xin quyen neu chua co
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ==============================================================================
    echo [!] Chuong trinh can quyen Administrator de doc/ghi bo nho MEGAMU.
    echo [!] Dang tu dong mo lai voi quyen Administrator...
    echo ==============================================================================
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo ==============================================================================
echo   MEGAMU AUTO TRAIN DASHBOARD - Qt6 NATIVE 60FPS (ADMINISTRATOR)
echo ==============================================================================

set "PY_EXE=C:\Users\donpv\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

echo Dang khoi dong: "%PY_EXE%" meg_gui_qt.py ...
echo.

"%PY_EXE%" meg_gui_qt.py

if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo   CHUONG TRINH DA DUNG (Ma thoat: %ERRORLEVEL%)
    echo ==============================================================================
    pause
)
