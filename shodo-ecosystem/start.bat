@echo off
echo ====================================
echo Starting Shodo Ecosystem
echo ====================================
echo.

echo Starting services...
docker-compose -f docker-compose.windows.yml up -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start services!
    echo Please check if Docker Desktop is running.
    echo.
    pause
    exit /b 1
)

echo.
echo Waiting for services to be ready...
timeout /t 10 /nobreak >nul

echo.
echo ====================================
echo Shodo Ecosystem is running!
echo ====================================
echo.
echo Access points:
echo   Frontend:    http://localhost:3000
echo   Backend API: http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo   Database:    localhost:5432
echo   Redis:       localhost:6379
echo.
echo To view logs, run: logs.bat
echo To stop services, run: stop.bat
echo.

REM ブラウザを開く
echo Opening browser...
start http://localhost:3000

pause