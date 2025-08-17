@echo off
echo ====================================
echo Stopping Shodo Ecosystem
echo ====================================
echo.

echo Stopping services...
docker-compose -f docker-compose.windows.yml down

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to stop services!
    echo.
    pause
    exit /b 1
)

echo.
echo ====================================
echo Services stopped successfully!
echo ====================================
echo.
pause