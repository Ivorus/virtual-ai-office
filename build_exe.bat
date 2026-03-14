@echo off
chcp 65001 >nul
title Virtual AI Office - Build EXE

echo.
echo  ==========================================
echo   VIRTUAL AI OFFICE - BUILD EXE
echo  ==========================================
echo.
echo  [1/4] Checking Python...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python not found!
    echo  Download Python 3.11+ from: https://python.org/downloads
    echo  Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b 1
)
echo  [OK] Python found:
python --version

echo.
echo  [2/4] Installing dependencies...
pip install PySide6 requests pyinstaller --quiet --upgrade
echo  [OK] Done

echo.
echo  [3/4] Building EXE (2-5 minutes, please wait)...
echo.

pyinstaller --onefile --windowed --name VirtualAIOffice --add-data "office_scene.py;." --hidden-import PySide6.QtCore --hidden-import PySide6.QtGui --hidden-import PySide6.QtWidgets --hidden-import requests --hidden-import sqlite3 --noconfirm main.py

if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Build failed. Use run.bat instead.
    pause
    exit /b 1
)

echo.
echo  [4/4] Copying to Desktop...
set DESKTOP=%USERPROFILE%\Desktop
if exist "dist\VirtualAIOffice.exe" (
    copy /Y "dist\VirtualAIOffice.exe" "%DESKTOP%\VirtualAIOffice.exe" >nul
    echo  [OK] VirtualAIOffice.exe copied to Desktop!
) else (
    echo  [!] File not found in dist folder
)

echo.
echo  ==========================================
echo   DONE! VirtualAIOffice.exe is on Desktop.
echo   If Windows asks - click "More info" then
echo   "Run anyway" - this is normal for custom apps.
echo  ==========================================
echo.
pause
