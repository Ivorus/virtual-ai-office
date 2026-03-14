@echo off
chcp 65001 >nul
title Virtual AI Office v4

echo.
echo  [*] Virtual AI Office v4 - Starting...
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found.
    echo  Run build_exe.bat to create EXE, or download Python from python.org
    pause
    exit /b 1
)

pip show PySide6 >nul 2>&1
if %errorlevel% neq 0 (
    echo  [*] Installing PySide6...
    pip install PySide6 requests --quiet
)

python main.py
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Startup failed. Check Python version (need 3.11+)
    pause
)
