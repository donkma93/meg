@echo off
cd /d "%~dp0"
echo Khoi dong MEGAMU Auto Navigator GUI...
"C:\Users\donpv\AppData\Local\Programs\Python\Python312\python.exe" meg_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Loi] Chuong trinh bi dung voi ma loi %ERRORLEVEL%
    pause
)
