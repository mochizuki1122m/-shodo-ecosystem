@echo off
REM ========================================
REM Shodo Ecosystem - Windows Stop
REM ========================================

echo.
echo ====================================================
echo   Shodo Ecosystem を停止します
echo ====================================================
echo.

REM サービス停止
echo サービスを停止中...
docker-compose -f docker-compose.windows.yml down

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] 一部のサービスの停止に失敗した可能性があります
    echo.
    echo 強制停止を試みます...
    docker-compose -f docker-compose.windows.yml kill
    docker-compose -f docker-compose.windows.yml rm -f
)

echo.
echo [OK] サービスを停止しました

REM Ollamaの停止確認
tasklist | find "ollama.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    choice /C YN /M "Ollamaも停止しますか？"
    if %errorlevel% equ 1 (
        taskkill /IM ollama.exe /F >nul 2>&1
        echo [OK] Ollamaを停止しました
    )
)

echo.
echo ====================================================
echo   停止完了
echo ====================================================
echo.
pause