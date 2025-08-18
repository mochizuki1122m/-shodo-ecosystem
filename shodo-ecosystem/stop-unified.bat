@echo off
echo ========================================
echo Stopping all Shodo Ecosystem services...
echo ========================================
echo.

REM Node.jsプロセスの終了
echo [1/4] Stopping Node.js processes...
taskkill /F /IM node.exe 2>nul
if %errorlevel% eq 0 (
    echo Node.js processes stopped.
) else (
    echo No Node.js processes found.
)

REM Pythonプロセスの終了
echo [2/4] Stopping Python processes...
taskkill /F /IM python.exe 2>nul
if %errorlevel% eq 0 (
    echo Python processes stopped.
) else (
    echo No Python processes found.
)

REM Dockerコンテナの停止
echo [3/4] Stopping Docker containers...
docker stop shodo-nginx 2>nul
docker rm shodo-nginx 2>nul
if %errorlevel% eq 0 (
    echo Docker containers stopped.
) else (
    echo No Docker containers found.
)

REM WSLサービスの停止
echo [4/4] Stopping WSL services...
wsl redis-cli shutdown 2>nul
wsl sudo service postgresql stop 2>nul
if %errorlevel% eq 0 (
    echo WSL services stopped.
) else (
    echo WSL services may already be stopped.
)

echo.
echo ========================================
echo All services stopped successfully!
echo ========================================
pause