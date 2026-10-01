@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title MEGAMU Auto Train Dashboard - DONG GOI TOAN BO VAO 1 THU MUC
color 0b
cd /d "%~dp0"

echo ==============================================================================
echo       MEGAMU AUTO TRAIN DASHBOARD - TIEN TRINH BUILD TOAN BO (ALL-IN-ONE)
echo ==============================================================================
echo.
echo Thu muc hien tai: %CD%
echo.

:: ------------------------------------------------------------------------------
:: 1. KIEM TRA CAC CONG CU CAN THIET (PYTHON, G++, PIP, PYINSTALLER)
:: ------------------------------------------------------------------------------
echo [1/5] Kiem tra moi truong he thong...

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo [LOI] Khong tim thay 'python' trong PATH!
    echo Vui long cai dat Python 3.10+ va tick vao "Add Python to PATH".
    pause
    exit /b 1
)

set "HAS_GXX=1"
where g++ >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    set "HAS_GXX=0"
    if exist "meg_license_bridge.dll" (
        echo   [CHU Y] Khong tim thay 'g++' trong PATH.
        echo   + Phat hien da co san 'meg_license_bridge.dll', se dung DLL co san nay.
    ) else (
        color 0c
        echo [LOI] Khong tim thay trinh bien dich 'g++' trong PATH va chua co 'meg_license_bridge.dll'!
        echo Vui long cai dat MinGW-w64 hoac LLVM-MinGW de bien dich file C++ DLL.
        pause
        exit /b 1
    )
)

echo   + Python: OK
if "!HAS_GXX!"=="1" (
    echo   + G++ [C++ Compiler]: OK
) else (
    echo   + G++: Khong co - Su dung file DLL co san
)

:: Kiem tra va tu dong cai dat PyInstaller neu thieu
python -m PyInstaller --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   - PyInstaller chua co san. Dang tu dong cai dat PyInstaller...
    python -m pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        color 0c
        echo [LOI] Khong the cai dat PyInstaller qua pip!
        pause
        exit /b 1
    )
)
echo   + PyInstaller: OK
echo.

:: ------------------------------------------------------------------------------
:: 2. DONG CAC TIEN TRINH PYTHON / APP DANG CHAY DE TRANH KHOA FILE
:: ------------------------------------------------------------------------------
echo [2/5] Dong cac tien trinh dang chay de tranh file-lock...
powershell -NoProfile -Command "Get-Process -Name 'python','MEGAMU Auto Train Dashboard' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1
ping 127.0.0.1 -n 2 >nul
echo   + Da giai phong tai nguyen va file lock.
echo.

:: ------------------------------------------------------------------------------
:: 3. BIEN DICH FILE C++ NATIVE LICENSE BRIDGE (.DLL)
:: ------------------------------------------------------------------------------
if "!HAS_GXX!"=="1" (
    echo [3/5] Dang bien dich C++ Native Bridge [license_bridge.cpp -^> meg_license_bridge.dll]...
    if not exist "native_bridge\license_bridge.cpp" (
        color 0c
        echo [LOI] Khong tim thay file nguon: native_bridge\license_bridge.cpp
        pause
        exit /b 1
    )

    g++ -O3 -shared -std=c++17 "native_bridge\license_bridge.cpp" -o "meg_license_bridge.dll" -lwinhttp -lcrypt32 -ladvapi32 -s -static-libgcc -static-libstdc++
    if %ERRORLEVEL% NEQ 0 (
        color 0c
        echo [LOI] Bien dich meg_license_bridge.dll that bai!
        pause
        exit /b 1
    )
    echo   + Bien dich meg_license_bridge.dll thanh cong! [Strip binary, toi uu hoa O3]
) else (
    echo [3/5] Bo qua bien dich C++ vi da co san meg_license_bridge.dll...
    if not exist "meg_license_bridge.dll" (
        color 0c
        echo [LOI] Khong tim thay meg_license_bridge.dll!
        pause
        exit /b 1
    )
    echo   + meg_license_bridge.dll da san sang de dong goi vao Release!
)
echo.

:: ------------------------------------------------------------------------------
:: 4. BUILD CHUONG TRINH SANG DANG SINGLE BINARY .EXE (PYINSTALLER ONEFILE)
:: ------------------------------------------------------------------------------
echo [4/5] Dang bien dich dong goi thanh 1 file .EXE duy nhat (PyInstaller onefile)...
echo Toan bo runtime, ma nguon va thu vien duoc ma hoa va dong goi ben trong file .EXE.
echo Qua trinh nay mat khoang 30-60 giay, vui long doi...

set "BUILD_TEMP=%~dp0build_temp"
set "BUILD_DIST=%~dp0build_dist"
set "TARGET_FOLDER=%~dp0Release_MEGAMU"

:: Don dep thu muc build cu neu co
if exist "%BUILD_TEMP%" rmdir /s /q "%BUILD_TEMP%" >nul 2>&1
if exist "%BUILD_DIST%" rmdir /s /q "%BUILD_DIST%" >nul 2>&1

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name="MEGAMU Auto Train Dashboard" ^
    --icon="%~dp0megamu_dashboard_icon.ico" ^
    --uac-admin ^
    --collect-all="customtkinter" ^
    --add-data="map_commands.json;." ^
    --add-data="megamu_dashboard_icon.ico;." ^
    --add-data="megamu_dashboard_logo.png;." ^
    --hidden-import="PIL" ^
    --hidden-import="PIL.Image" ^
    --hidden-import="PIL.ImageTk" ^
    --hidden-import="darkdetect" ^
    --hidden-import="psutil" ^
    --hidden-import="frida" ^
    --hidden-import="meg_direct_engine" ^
    --hidden-import="meg_auto_worker" ^
    --hidden-import="license_client" ^
    --hidden-import="updater" ^
    --distpath="%BUILD_DIST%" ^
    --workpath="%BUILD_TEMP%" ^
    "meg_gui.py"

if %ERRORLEVEL% NEQ 0 (
    color 0c
    echo [LOI] PyInstaller gap su co khi dong goi!
    pause
    exit /b 1
)
echo   + Dong goi .EXE hoan tat!
echo.

:: ------------------------------------------------------------------------------
:: 5. TONG HOP THU MUC RELEASE: CHI GIU .EXE, .DLL VA CONFIG/ (KHONG CO THU MUC PYTHON/INTERNAL)
:: ------------------------------------------------------------------------------
echo [5/5] Dang chuan bi thu muc Release tinh gon (Chi co .EXE, .DLL va config/)...

if exist "%TARGET_FOLDER%" (
    echo   - Lam sach thu muc Release cu...
    rmdir /s /q "%TARGET_FOLDER%" >nul 2>&1
)
mkdir "%TARGET_FOLDER%"

:: 5.1 Sao chep file .EXE don nhat
if exist "%TARGET_FOLDER%\MEGAMU Auto Train Dashboard.exe" (
    del /f /q "%TARGET_FOLDER%\MEGAMU Auto Train Dashboard.exe" >nul 2>&1
    if exist "%TARGET_FOLDER%\MEGAMU Auto Train Dashboard.exe" ren "%TARGET_FOLDER%\MEGAMU Auto Train Dashboard.exe" "MEGAMU Auto Train Dashboard.old.exe" >nul 2>&1
)
copy /y "%BUILD_DIST%\MEGAMU Auto Train Dashboard.exe" "%TARGET_FOLDER%\" >nul
echo   + Da copy MEGAMU Auto Train Dashboard.exe

:: 5.2 Sao chep file C++ DLL
if exist "%TARGET_FOLDER%\meg_license_bridge.dll" (
    del /f /q "%TARGET_FOLDER%\meg_license_bridge.dll" >nul 2>&1
    if exist "%TARGET_FOLDER%\meg_license_bridge.dll" ren "%TARGET_FOLDER%\meg_license_bridge.dll" "meg_license_bridge.old.dll" >nul 2>&1
)
copy /y "meg_license_bridge.dll" "%TARGET_FOLDER%\" >nul
echo   + Da copy meg_license_bridge.dll

:: 5.3 Sao chep icon va logo de dong bo taskbar va giao dien
if exist "megamu_dashboard_icon.ico" copy /y "megamu_dashboard_icon.ico" "%TARGET_FOLDER%\" >nul
if exist "megamu_dashboard_logo.png" copy /y "megamu_dashboard_logo.png" "%TARGET_FOLDER%\" >nul
echo   + Da dong bo icon va logo vao thu muc Release

:: 5.4 Tao thu muc config
mkdir "%TARGET_FOLDER%\config" >nul 2>&1
if exist "config\ui_settings.json" copy /y "config\ui_settings.json" "%TARGET_FOLDER%\config\" >nul
echo   + Da tao thu muc config/ (Cai dat giao dien)

:: 5.5 Don dep thu muc tam thoi
if exist "%BUILD_TEMP%" rmdir /s /q "%BUILD_TEMP%" >nul 2>&1
if exist "%BUILD_DIST%" rmdir /s /q "%BUILD_DIST%" >nul 2>&1

echo.
echo ==============================================================================
echo                     BUILD HOAN TAT THANH CONG 100%%!
echo ==============================================================================
echo Toan bo chuong trinh da duoc tap hop tai thu muc:
echo   %TARGET_FOLDER%
echo.
echo File khoi dong chinh:
echo   %TARGET_FOLDER%\MEGAMU Auto Train Dashboard.exe
echo   (kem file license: %TARGET_FOLDER%\meg_license_bridge.dll)
echo ==============================================================================
echo.
echo Dang mo thu muc Release_MEGAMU...
explorer.exe "%TARGET_FOLDER%"
if /i "%1" NEQ "/nopause" pause
exit /b 0
