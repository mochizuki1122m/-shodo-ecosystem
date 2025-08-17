@echo off
echo ========================================
echo   Shodo Ecosystem - Simple Start
echo   (Windows - No Docker Required)
echo ========================================
echo.

REM Python確認
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Please install Python from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Node.js確認
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed!
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo [1/3] Starting Backend Server...
cd backend
start "Shodo Backend" cmd /k "python simple_server.py"
cd ..

echo [2/3] Starting Frontend Server...
cd frontend\public
start "Shodo Frontend" cmd /k "python -m http.server 3000"
cd ..\..

echo [3/3] Waiting for services to start...
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Services Started Successfully!
echo ========================================
echo.
echo   Backend API:  http://localhost:8000
echo   Test Page:    http://localhost:3000/simple.html
echo.
echo ========================================
echo.
echo Opening test page in browser...
timeout /t 2 /nobreak >nul
start http://localhost:3000/simple.html

echo.
echo Press any key to stop all services...
pause >nul

echo.
echo Stopping services...
taskkill /FI "WindowTitle eq Shodo Backend*" /T /F >nul 2>&1
taskkill /FI "WindowTitle eq Shodo Frontend*" /T /F >nul 2>&1

echo Services stopped.
pause