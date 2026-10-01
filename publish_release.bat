@echo off
chcp 65001 >nul
title Phat hanh Release len GitHub (MEGATEAM)
cd /d "%~dp0"
echo ==============================================================================
echo       PHAT HANH BAN BUILD .EXE VA .ZIP LEN GITHUB RELEASES
echo ==============================================================================
echo.
python publish_release.py
echo.
pause
