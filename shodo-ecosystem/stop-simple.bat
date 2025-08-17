@echo off
echo Stopping Shodo Ecosystem services...

REM Pythonプロセスを停止
taskkill /F /IM python.exe /FI "MEMUSAGE gt 1000" >nul 2>&1

REM 特定のウィンドウタイトルのプロセスを停止
taskkill /FI "WindowTitle eq Shodo Backend*" /T /F >nul 2>&1
taskkill /FI "WindowTitle eq Shodo Frontend*" /T /F >nul 2>&1

echo Services stopped.
pause