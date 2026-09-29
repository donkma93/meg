@echo off
title Day code len GitHub (donkma93/meg)
cd /d "%~dp0"
echo ========================================================
echo   DANG DAY CODE LEN REPO: https://github.com/donkma93/meg.git
echo ========================================================
echo.
git push -u origin main
echo.
echo ========================================================
if %errorlevel% equ 0 (
    echo [OK] Day code len GitHub thanh cong!
) else (
    echo [!] Neu trinh duyet bat len yeu cau dang nhap, hay chon Authorize de xac thuc GitHub.
)
echo ========================================================
pause
