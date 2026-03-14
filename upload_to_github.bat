@echo off
chcp 65001 >nul
title Upload to GitHub

echo.
echo  ==========================================
echo   UPLOAD VIRTUAL AI OFFICE TO GITHUB
echo  ==========================================
echo.

git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Git not found!
    echo  Download: https://git-scm.com/download/win
    echo  Install with default settings, then run again.
    pause
    exit /b 1
)
echo  [OK] Git is installed
echo.

set /p GITHUB_USER="Enter GitHub username: "
if "%GITHUB_USER%"=="" ( echo [ERROR] Empty username & pause & exit /b 1 )

set /p REPO_NAME="Enter repo name (e.g. virtual-ai-office): "
if "%REPO_NAME%"=="" set REPO_NAME=virtual-ai-office

set /p GIT_EMAIL="Enter GitHub email: "

echo.
echo  [*] Setting up Git identity...
git config --global user.name "%GITHUB_USER%"
git config --global user.email "%GIT_EMAIL%"

echo  [*] Creating .gitignore...
(
echo __pycache__/
echo *.pyc
echo build/
echo dist/
echo settings.json
echo office.db
echo office_cloud/
echo floors.json
echo quick_commands.json
echo *.spec
) > .gitignore

echo  [*] Initializing repository...
git init
git branch -M main
git add .
git commit -m "Initial commit: Virtual AI Office v4"

set REPO_URL=https://github.com/%GITHUB_USER%/%REPO_NAME%.git
git remote add origin %REPO_URL%

echo.
echo  ==========================================
echo  IMPORTANT: When asked for password,
echo  use a Personal Access Token, not password!
echo.
echo  Get token at:
echo  github.com/settings/tokens
echo  -> Generate new token (classic)
echo  -> Check "repo" checkbox
echo  -> Copy token and paste as password
echo  ==========================================
echo.

git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo  [!] Push failed. See instructions above for token.
    echo  Then run: git push -u origin main
    pause
    exit /b 1
)

echo.
echo  ==========================================
echo   DONE! Your repo:
echo   https://github.com/%GITHUB_USER%/%REPO_NAME%
echo  ==========================================
echo.
pause
