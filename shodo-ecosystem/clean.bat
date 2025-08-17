@echo off
echo ====================================
echo Cleaning Shodo Ecosystem
echo ====================================
echo.

echo This will remove all containers, volumes, and data!
set /p confirm="Are you sure? (y/N): "

if /i not "%confirm%"=="y" (
    echo Cleanup cancelled.
    pause
    exit /b 0
)

echo.
echo Removing containers and volumes...
docker-compose -f docker-compose.windows.yml down -v

echo Cleaning directories...
if exist "frontend\node_modules" rmdir /s /q "frontend\node_modules"
if exist "backend\__pycache__" rmdir /s /q "backend\__pycache__"
if exist ".pytest_cache" rmdir /s /q ".pytest_cache"

echo.
echo ====================================
echo Cleanup completed!
echo ====================================
echo.
pause