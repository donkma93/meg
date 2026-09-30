@echo off
chcp 65001 >nul
title donpv License Server - Laravel Backend
color 0b

echo ========================================================
echo        DONPV LICENSE SERVER - LARAVEL SYSTEM
echo ========================================================
echo.

set "PHP_PATH=C:\Users\donpv\AppData\Local\Microsoft\WinGet\Packages\PHP.PHP.8.3_Microsoft.Winget.Source_8wekyb3d8bbwe\php.exe"

if not exist "%PHP_PATH%" (
    echo [ERROR] Khong tim thay php.exe tai duong dan: %PHP_PATH%
    pause
    exit /b 1
)

cd /d "%~dp0license-server"

echo [1/3] Kiem tra quyen ghi thu muc bootstrap/cache & storage...
attrib -r "%~dp0license-server\*" /s /d >nul 2>&1

echo [2/3] Khoi dong Laravel Server tai http://127.0.0.1:8000...
echo.
echo ========================================================
echo   - Web Admin Dashboard: http://127.0.0.1:8000/admin/licenses
echo   - API Activate:        http://127.0.0.1:8000/api/v1/license/activate
echo   - API Verify:          http://127.0.0.1:8000/api/v1/license/verify
echo ========================================================
echo.

"%PHP_PATH%" artisan serve --host=127.0.0.1 --port=8000
pause
