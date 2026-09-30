@echo off
setlocal
cd /d "%~dp0"
echo ==============================================================================
echo   HE THONG DONG GOI BAO MAT TOAN DIEN - MEGAMU AUTO TRAIN (ANTI-CRACK v2.0)
echo ==============================================================================
echo.
echo [BUOC 1] BIEN DICH NATIVE C++ BRIDGE (Mahoa XOR + HMAC-SHA256 + Encrypted Offsets)...

where g++.exe >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Khong tim thay trinh bien dich g++.exe trong PATH!
    pause
    exit /b 1
)

:: Tat cac tien trinh dang chay DLL de tranh file lock
powershell -Command "Get-Process -Name 'python' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue" >nul 2>&1

g++ -O3 -shared -std=c++17 "native_bridge\license_bridge.cpp" -o "meg_license_bridge.dll" -lwinhttp -lcrypt32 -ladvapi32 -s -static-libgcc -static-libstdc++
if %ERRORLEVEL% NEQ 0 (
    echo [LOI] Bien dich meg_license_bridge.dll that bai!
    pause
    exit /b 1
)
echo [THANH CONG] meg_license_bridge.dll da duoc tao va strip ma doc lap!
echo.

echo [BUOC 2] KIEM TRA MOI TRUONG DONG GOI PYTHON NATIVE BINARY (NUITKA)...
python -m nuitka --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [THONG BAO] Nuitka chua duoc cai dat trong moi truong Python hien tai.
    echo.
    echo Ban co muon tu dong cai dat Nuitka de build EXE native khong? (Y/N)
    set /p USER_CHOICE="Lua chon cua ban: "
    if /i "%USER_CHOICE%"=="Y" (
        echo Dang cai dat Nuitka va Zstandard...
        python -m pip install nuitka zstandard
    ) else (
        echo [BO QUA] Chi su dung Native DLL cho ma nguon Python hien tai.
        pause
        exit /b 0
    )
)

echo.
echo [BUOC 3] DANG TIEN HANH BIEN DICH PYTHON RA NATIVE C MACHINE CODE (NUITKA)...
echo Qua trinh nay se chuyen doi code Python sang file .EXE nhi phan chong dich nguoc.
echo.

python -m nuitka ^
    --standalone ^
    --windows-disable-console ^
    --enable-plugin=tk-inter ^
    --windows-icon-from-ico="megamu_dashboard_icon.ico" ^
    --include-data-file="meg_license_bridge.dll=meg_license_bridge.dll" ^
    --include-data-file="megamu_dashboard_icon.ico=megamu_dashboard_icon.ico" ^
    --include-data-file="megamu_dashboard_logo.png=megamu_dashboard_logo.png" ^
    --include-data-dir="config=config" ^
    --output-dir="dist_secure" ^
    --main="meg_gui.py"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================================================
    echo [HOAN TAT XUAT SAC] 
    echo Chuong trinh da duoc bien dich an toan tai thu muc: dist_secure\meg_gui.dist\
    echo ==============================================================================
) else (
    echo.
    echo [Luu y] Bien dich Nuitka co the can them bo compiler C++ (MinGW64 hoac MSVC).
)

pause
endlocal
