@echo off
title NotebookLM-Mini 1-Click Run cho Windows
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ==============================================================================
echo [*] Khoi dong NotebookLM-Mini cho Windows...
echo ==============================================================================

cd /d "%~dp0"

:: 1. Kiem tra Python
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [X] Loi: Khong tim thay Python! Vui long cai dat Python tu trang chu: https://www.python.org/downloads/
    pause
    exit /b
)

:: 2. Kiem tra Node.js
node --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [X] Loi: Khong tim thay Node.js! Vui long cai dat Node.js: https://nodejs.org/
    pause
    exit /b
)

:: 2.5 Kiem tra ffmpeg
ffmpeg -version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [!] Canh bao: Khong tim thay ffmpeg! Tinh nang doc file am thanh se khong hoat dong.
    echo [!] Ban co the cai dat ffmpeg hoac bo qua canh bao nay.
)

:: 3. Kiem tra va cai dat uv
uv --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [i] Dang cai dat cong cu uv...
    python -m pip install uv
)

:: 4. Tao moi truong ao
if not exist ".venv" (
    echo [i] Dang tao moi truong ao Python...
    uv venv
)
call .venv\Scripts\activate.bat

:: 5. Cai dat thu vien Backend
echo [i] Dang cai dat thu vien Backend...
uv pip install -r requirements.txt

:: 6. Quet phan cung
echo [i] Dang quet cau hinh may tinh...
python src\utils\hardware_profiler.py

:: 7. Cai thu vien Node.js
echo [i] Dang kiem tra thu vien Frontend...
cd frontend
if not exist "node_modules" (
    echo [i] Dang cai dat Node Modules...
    call npm install
)
cd ..

:: 8. Khoi dong server
echo [*] Bat dau chay he thong...

start "NotebookLM Backend" cmd /c "call .venv\Scripts\activate.bat && uvicorn src.api.api:app --host 127.0.0.1 --port 8000"
start "NotebookLM Frontend" cmd /c "cd frontend && npm run dev"

timeout /t 4 /nobreak >nul
start "" "http://localhost:5173"

echo [*] Thanh cong! Phim tat cua so nay de thoat.
pause
