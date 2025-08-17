@echo off
REM ========================================
REM Shodo Ecosystem - Windows Quick Start
REM ========================================

echo.
echo ====================================================
echo   Shodo Ecosystem を起動します
echo ====================================================
echo.

REM Docker Desktop起動確認
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktopが起動していません
    echo.
    echo Docker Desktopを起動中...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo.
    echo Docker Desktopの起動を待機中（30秒）...
    timeout /t 30 >nul
    
    docker ps >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Docker Desktopの起動に失敗しました
        echo 手動でDocker Desktopを起動してから再実行してください
        pause
        exit /b 1
    )
)

echo [OK] Docker Desktop稼働中

REM 既存のコンテナを確認
echo.
echo 既存のコンテナを確認中...
docker-compose -f docker-compose.windows.yml ps

REM サービス起動
echo.
echo サービスを起動中...
docker-compose -f docker-compose.windows.yml up -d

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] サービスの起動に失敗しました
    echo.
    echo トラブルシューティング:
    echo 1. Docker Desktopが正常に動作しているか確認
    echo 2. ポート3000, 8000, 8001が使用されていないか確認
    echo 3. docker-compose.windows.ymlファイルが存在するか確認
    echo.
    pause
    exit /b 1
)

echo.
echo サービスの起動を待機中...
timeout /t 10 >nul

REM ステータス確認
echo.
echo ====================================================
echo   起動ステータス
echo ====================================================
echo.

docker-compose -f docker-compose.windows.yml ps

echo.
echo ====================================================
echo   アクセスURL
echo ====================================================
echo.
echo   フロントエンド:    http://localhost:3000
echo   バックエンドAPI:   http://localhost:8000
echo   APIドキュメント:   http://localhost:8000/docs
echo   AIサーバー:       http://localhost:8001/health
echo.
echo ====================================================
echo.

REM ブラウザを開く
choice /C YN /M "ブラウザを開きますか？"
if %errorlevel% equ 1 (
    start http://localhost:3000
)

echo.
echo 停止するには stop-windows.bat を実行してください
echo.
pause