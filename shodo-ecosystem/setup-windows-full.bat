@echo off
REM ========================================
REM Shodo Ecosystem - Windows フル機能版セットアップ
REM ========================================

echo.
echo ====================================================
echo   Shodo Ecosystem - Windows Full Setup
echo   フル機能版セットアップを開始します
echo ====================================================
echo.

REM 管理者権限チェック
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 管理者権限が必要です
    echo 右クリックして「管理者として実行」を選択してください
    pause
    exit /b 1
)

REM 必要なツールの確認
echo [1/8] 必要なツールを確認中...
echo.

REM Docker Desktop確認
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker Desktopがインストールされていません
    echo.
    echo Docker Desktopをインストールしてください:
    echo https://www.docker.com/products/docker-desktop
    echo.
    echo インストール後、このスクリプトを再実行してください
    pause
    exit /b 1
) else (
    echo [OK] Docker Desktop検出
)

REM Docker起動確認
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker Desktopが起動していません
    echo Docker Desktopを起動してください
    pause
    exit /b 1
) else (
    echo [OK] Docker Desktop稼働中
)

REM Git確認
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Gitがインストールされていません
    echo Gitのインストールを推奨します: https://git-scm.com/
) else (
    echo [OK] Git検出
)

REM Node.js確認
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Node.jsがインストールされていません
    echo Node.js LTSのインストールを推奨します: https://nodejs.org/
) else (
    echo [OK] Node.js検出
)

echo.
echo [2/8] 環境変数ファイルを作成中...

REM .envファイルの作成
if not exist .env (
    copy .env.example .env >nul 2>&1
    
    REM Windows用の設定を追加
    echo. >> .env
    echo # Windows環境用設定 >> .env
    echo PLATFORM=windows >> .env
    echo DOCKER_BUILDKIT=1 >> .env
    echo COMPOSE_DOCKER_CLI_BUILD=1 >> .env
    
    echo [OK] .envファイル作成完了
) else (
    echo [OK] .envファイル既存
)

echo.
echo [3/8] 必要なディレクトリを作成中...

REM ディレクトリ作成
if not exist models mkdir models
if not exist cache mkdir cache
if not exist logs mkdir logs
if not exist browser-data mkdir browser-data
if not exist data mkdir data

echo [OK] ディレクトリ作成完了

echo.
echo [4/8] Ollama設定（オプション）...

REM Ollamaのインストール確認
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Ollamaがインストールされていません
    echo ローカルLLMを使用する場合は、Ollamaをインストールしてください:
    echo https://ollama.com/download/windows
    echo.
    set /p INSTALL_OLLAMA="Ollamaをインストールしますか？ (y/n): "
    if /i "%INSTALL_OLLAMA%"=="y" (
        echo Ollamaダウンロードページを開きます...
        start https://ollama.com/download/windows
        echo インストール完了後、Enterキーを押してください...
        pause >nul
    )
) else (
    echo [OK] Ollama検出
    
    REM Ollamaサービス起動
    echo Ollamaサービスを起動中...
    start /min cmd /c "ollama serve"
    timeout /t 3 >nul
    
    REM モデルのダウンロード
    echo.
    set /p DOWNLOAD_MODEL="Mistralモデルをダウンロードしますか？（約4GB） (y/n): "
    if /i "%DOWNLOAD_MODEL%"=="y" (
        echo モデルをダウンロード中...
        ollama pull mistral
        echo [OK] モデルダウンロード完了
    )
)

echo.
echo [5/8] Docker環境をクリーンアップ中...

REM 既存のコンテナを停止
docker-compose -f docker-compose.windows.yml down >nul 2>&1

echo [OK] クリーンアップ完了

echo.
echo [6/8] Dockerイメージをビルド中...
echo これには10-20分かかる場合があります...
echo.

REM Dockerイメージのビルド
docker-compose -f docker-compose.windows.yml build --no-cache

if %errorlevel% neq 0 (
    echo [ERROR] Dockerイメージのビルドに失敗しました
    echo ログを確認してください
    pause
    exit /b 1
)

echo.
echo [OK] Dockerイメージビルド完了

echo.
echo [7/8] サービスを起動中...

REM サービス起動
docker-compose -f docker-compose.windows.yml up -d

if %errorlevel% neq 0 (
    echo [ERROR] サービスの起動に失敗しました
    pause
    exit /b 1
)

echo [OK] サービス起動完了

echo.
echo [8/8] ヘルスチェック中...

REM 起動待機
echo サービスの起動を待機中...
timeout /t 10 >nul

REM ヘルスチェック
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] バックエンドAPI: 正常
) else (
    echo [WARNING] バックエンドAPI: 応答なし
)

curl -s http://localhost:3000 >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] フロントエンド: 正常
) else (
    echo [WARNING] フロントエンド: 応答なし
)

curl -s http://localhost:8001/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] AIサーバー: 正常
) else (
    echo [WARNING] AIサーバー: 応答なし
)

echo.
echo ====================================================
echo   セットアップ完了！
echo ====================================================
echo.
echo アクセスURL:
echo   - フロントエンド: http://localhost:3000
echo   - API ドキュメント: http://localhost:8000/docs
echo   - ヘルスチェック: http://localhost:8000/health
echo.
echo 管理コマンド:
echo   - 停止: docker-compose -f docker-compose.windows.yml down
echo   - ログ: docker-compose -f docker-compose.windows.yml logs -f
echo   - 再起動: docker-compose -f docker-compose.windows.yml restart
echo.
echo ====================================================
echo.

REM ブラウザを開く
set /p OPEN_BROWSER="ブラウザを開きますか？ (y/n): "
if /i "%OPEN_BROWSER%"=="y" (
    start http://localhost:3000
)

echo.
echo セットアップスクリプトを終了します
pause