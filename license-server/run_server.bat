@echo off
chcp 65001 >nul
title MEGATEAM License Server - Laravel
color 0a

set "PHP_PATH=C:\Users\donpv\AppData\Local\Microsoft\WinGet\Packages\PHP.PHP.8.3_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe"

cd /d "%~dp0"
attrib -r "%~dp0*" /s /d >nul 2>&1

echo Khoi dong MEGATEAM License Server...
echo Web Dashboard: http://127.0.0.1:8000/admin/licenses
echo.

"%PHP_PATH%" artisan serve --host=127.0.0.1 --port=8000
pause
