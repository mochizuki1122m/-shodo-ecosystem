@echo off
echo Starting Shodo Ecosystem on Windows...

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    call pnpm install
)

REM Check if build exists
if not exist "frontend\build" (
    echo Building frontend...
    call pnpm build
)

REM Start with PM2
echo Starting services with PM2...
call npx pm2 delete all 2>nul
call npx pm2 start ecosystem.config.js

REM Show status
call npx pm2 status

echo.
echo ====================================
echo Services are running!
echo Frontend: http://localhost:3000
echo Backend API: http://localhost:8000
echo ====================================
echo.
echo Press any key to view logs...
pause >nul
call npx pm2 logs