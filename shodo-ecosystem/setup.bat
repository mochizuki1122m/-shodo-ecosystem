@echo off
echo ====================================
echo Shodo Ecosystem Setup for Windows
echo ====================================
echo.

REM 必要なディレクトリを作成
echo Creating directories...
if not exist "models" mkdir models
if not exist "cache" mkdir cache
if not exist "browser-data" mkdir browser-data

REM 環境変数ファイルをコピー
echo Setting up environment variables...
if not exist ".env" (
    copy .env.example .env
    echo Created .env file from .env.example
) else (
    echo .env file already exists
)

REM Docker Desktop確認
echo.
echo Checking Docker Desktop...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Docker is not installed or not running!
    echo Please install Docker Desktop for Windows from:
    echo https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Docker Compose is not installed!
    echo Please ensure Docker Desktop is properly installed.
    echo.
    pause
    exit /b 1
)

echo Docker is installed and running.

REM WSL2確認（推奨）
echo.
echo Checking WSL2 backend...
wsl --status >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] WSL2 is not installed or not configured.
    echo WSL2 backend is recommended for better performance.
    echo You can continue with Hyper-V backend, but performance may be slower.
    echo.
    echo To install WSL2, run in PowerShell as Administrator:
    echo   wsl --install
    echo.
)

echo.
echo ====================================
echo Setup completed successfully!
echo ====================================
echo.
echo Next steps:
echo 1. Build Docker images: build.bat
echo 2. Start services: start.bat
echo.
pause