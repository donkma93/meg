@echo off
chcp 65001 > nul
echo ======================================================================
echo   MEGAMU AUTO TRAIN DASHBOARD - PHIÊN BẢN V2 TỐI ƯU HÓA (ZERO-LAG)
echo ======================================================================
echo.
echo [1/2] Đang kiểm tra môi trường Python...
python --version
if errorlevel 1 (
    echo [LOI] Khong tim thay Python! Vui long cai dat Python 3.10 hoac 3.11.
    pause
    exit /b 1
)

echo.
echo [2/2] Dang khoi chay MEGAMU Dashboard V2 (Zero-Lag Engine)...
python meg_gui_optimized.py

if errorlevel 1 (
    echo.
    echo [CANH BAO] Chuong trinh dung voi ma loi: %errorlevel%
    pause
)

