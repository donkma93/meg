@echo off
setlocal
cd /d "%~dp0"
echo ==============================================================================
echo BIEN DICH NATIVE C++ LICENSE BRIDGE CHO MEGAMU AUTO TRAIN
echo ==============================================================================

powershell -Command "Get-Process -Name 'python' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1

where g++.exe >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong tim thay trinh bien dich g++.exe trong PATH!
    exit /b 1
)

echo [1/2] Dang bien dich DLL: native_bridge\license_bridge.cpp -> meg_license_bridge.dll...
g++ -O3 -shared -std=c++17 "native_bridge\license_bridge.cpp" -o "meg_license_bridge.dll" -lwinhttp -lcrypt32 -ladvapi32 -s -static-libgcc -static-libstdc++
if %ERRORLEVEL% NEQ 0 (
    echo [THAT BAI] Khong the bien dich meg_license_bridge.dll!
    exit /b 1
)

echo [2/2] Dang bien dich CLI: native_bridge\cli_test.cpp -> meg_bridge_cli.exe...
g++ -O3 -std=c++17 "native_bridge\cli_test.cpp" -o "meg_bridge_cli.exe" -s -static-libgcc -static-libstdc++
if %ERRORLEVEL% NEQ 0 (
    echo [THAT BAI] Khong the bien dich meg_bridge_cli.exe!
    exit /b 1
)

echo.
echo ==============================================================================
echo [THANH CONG] Da bien dich xong ca 2 thanh phan:
echo   1. meg_license_bridge.dll (Thu vien Native C++ Bridge cho App)
echo   2. meg_bridge_cli.exe      (Chuong trinh C++ doc lap de test cau noi)
echo ==============================================================================
endlocal
