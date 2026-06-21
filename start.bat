@echo off
title NotebookLM Clone - 1-Click Setup
color 0A

echo ==================================================
echo      NOTEBOOKLM CLONE - AUTO SETUP (WINDOWS)      
echo ==================================================
echo.

echo [1/3] Kiem tra Python...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [CANH BAO] Python chua duoc cai dat tren may nay!
    echo Dang tai va cai dat Python tu Microsoft Store tu dong...
    winget install -e --id Python.Python.3.10 --accept-source-agreements --accept-package-agreements
    echo.
    echo [THANH CONG] Vui long tat bang nay va mo lai start.bat nhe!
    pause
    exit /b
)

echo [2/3] Cai dat moi truong co ban...
pip install psutil requests uv >nul 2>&1

echo [3/3] Chuyen giao quyen cho Setup Wizard...
python setup_wizard.py

pause
