@echo off
echo ====================================
echo Building Shodo Ecosystem
echo ====================================
echo.

echo Building Docker images...
echo This may take several minutes on first run.
echo.

REM Windows用のDocker Composeファイルを使用
docker-compose -f docker-compose.windows.yml build

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    echo Please check the error messages above.
    echo.
    pause
    exit /b 1
)

echo.
echo ====================================
echo Build completed successfully!
echo ====================================
echo.
echo To start the services, run: start.bat
echo.
pause