@echo off
echo ========================================
echo   Shodo Ecosystem - Production Start
echo   (Windows - Docker-free with PM2)
echo ========================================
echo.

REM Check prerequisites
echo [1/5] Checking prerequisites...

REM Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed!
    echo Download from: https://nodejs.org/
    pause
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed!
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check PM2
pm2 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing PM2 globally...
    npm install -g pm2
)

REM Check pnpm (optional but recommended)
pnpm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing pnpm globally...
    npm install -g pnpm
)

echo [✓] All prerequisites installed
echo.

REM Setup environment
echo [2/5] Setting up environment...
if not exist .env (
    copy .env.example .env
    echo [!] Created .env file. Please edit it with your settings.
)

REM Install dependencies
echo [3/5] Installing dependencies...
call npm install
cd frontend
call npm install --legacy-peer-deps
cd ..

REM Create logs directory
if not exist logs mkdir logs

REM Check Ollama
echo [4/5] Checking LLM service...
where ollama >nul 2>&1
if %errorlevel% eq 0 (
    echo [✓] Ollama detected
    REM Start Ollama if not running
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if %errorlevel% neq 0 (
        echo Starting Ollama service...
        start "Ollama" cmd /c "ollama serve"
        timeout /t 5 /nobreak >nul
    )
) else (
    echo [!] Ollama not found. LLM features will be limited.
    echo     Install from: https://ollama.com/download/windows
)

REM Start services with PM2
echo [5/5] Starting services with PM2...
pm2 delete all >nul 2>&1
pm2 start ecosystem.config.js

echo.
echo ========================================
echo   Services Started Successfully!
echo ========================================
echo.

REM Show status
pm2 status

echo.
echo URLs:
echo   Frontend:  http://localhost:8080
echo   API:       http://localhost:8000
echo   Test Page: http://localhost:8080/simple.html
echo.
echo Commands:
echo   pm2 status    - Show service status
echo   pm2 logs      - View logs
echo   pm2 restart all - Restart all services
echo   pm2 stop all  - Stop all services
echo   pm2 monit     - Monitor resources
echo.
echo Opening frontend in browser...
timeout /t 3 /nobreak >nul
start http://localhost:8080

echo.
pause