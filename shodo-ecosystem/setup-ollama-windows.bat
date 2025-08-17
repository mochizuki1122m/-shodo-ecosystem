@echo off
REM ========================================
REM Ollama for Windows セットアップ
REM ========================================

echo.
echo ====================================================
echo   Ollama セットアップ - Windows版
echo   ローカルLLMを使用するための設定
echo ====================================================
echo.

REM Ollamaインストール確認
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Ollamaがインストールされていません
    echo.
    echo Ollamaをインストールします...
    echo.
    
    REM ダウンロードURL
    set OLLAMA_URL=https://ollama.com/download/OllamaSetup.exe
    set DOWNLOAD_PATH=%TEMP%\OllamaSetup.exe
    
    echo ダウンロード中...
    powershell -Command "Invoke-WebRequest -Uri '%OLLAMA_URL%' -OutFile '%DOWNLOAD_PATH%'"
    
    if exist "%DOWNLOAD_PATH%" (
        echo.
        echo インストーラーを起動します...
        echo インストール完了後、このウィンドウに戻ってEnterキーを押してください
        start /wait "" "%DOWNLOAD_PATH%"
        pause >nul
        
        REM インストール確認
        where ollama >nul 2>&1
        if %errorlevel% neq 0 (
            echo [ERROR] Ollamaのインストールに失敗しました
            echo 手動でインストールしてください: https://ollama.com/download/windows
            pause
            exit /b 1
        )
    ) else (
        echo [ERROR] ダウンロードに失敗しました
        echo ブラウザから手動でダウンロードしてください
        start https://ollama.com/download/windows
        pause
        exit /b 1
    )
)

echo [OK] Ollama検出

REM Ollamaサービス起動
echo.
echo Ollamaサービスを起動中...

REM 既存のOllamaプロセスを確認
tasklist | find "ollama.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Ollamaは既に起動しています
) else (
    start /min cmd /c "ollama serve"
    timeout /t 5 >nul
    echo [OK] Ollamaサービスを起動しました
)

REM 利用可能なモデルを確認
echo.
echo ====================================================
echo   利用可能なモデル
echo ====================================================
echo.

ollama list

echo.
echo ====================================================
echo   推奨モデルのインストール
echo ====================================================
echo.
echo 以下のモデルから選択してください：
echo.
echo 1. mistral (7B) - バランス型、推奨
echo 2. llama3 (8B) - 高品質
echo 3. phi3 (3.8B) - 軽量・高速
echo 4. qwen2.5 (7B) - 日本語対応良好
echo 5. gemma2 (9B) - Google製
echo 6. スキップ
echo.

choice /C 123456 /M "インストールするモデルを選択"
set MODEL_CHOICE=%errorlevel%

if %MODEL_CHOICE% equ 1 (
    set MODEL_NAME=mistral
    set MODEL_SIZE=4.1GB
) else if %MODEL_CHOICE% equ 2 (
    set MODEL_NAME=llama3
    set MODEL_SIZE=4.7GB
) else if %MODEL_CHOICE% equ 3 (
    set MODEL_NAME=phi3
    set MODEL_SIZE=2.3GB
) else if %MODEL_CHOICE% equ 4 (
    set MODEL_NAME=qwen2.5:7b
    set MODEL_SIZE=4.4GB
) else if %MODEL_CHOICE% equ 5 (
    set MODEL_NAME=gemma2
    set MODEL_SIZE=5.5GB
) else (
    echo モデルのインストールをスキップします
    goto :CONFIG
)

echo.
echo %MODEL_NAME% (%MODEL_SIZE%) をダウンロード中...
echo これには数分かかる場合があります...
echo.

ollama pull %MODEL_NAME%

if %errorlevel% neq 0 (
    echo [ERROR] モデルのダウンロードに失敗しました
    echo ネットワーク接続を確認してください
) else (
    echo.
    echo [OK] %MODEL_NAME% のインストール完了
)

:CONFIG
REM 設定ファイルの更新
echo.
echo ====================================================
echo   環境設定の更新
echo ====================================================
echo.

REM .envファイルが存在しない場合は作成
if not exist .env (
    if exist .env.windows (
        copy .env.windows .env >nul
    ) else if exist .env.example (
        copy .env.example .env >nul
    )
)

REM Ollama設定を.envに追加
echo.
echo .envファイルを更新中...

powershell -Command "(Get-Content .env) -replace 'LLM_PROVIDER=.*', 'LLM_PROVIDER=ollama' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'OPENAI_BASE_URL=.*', 'OPENAI_BASE_URL=http://host.docker.internal:11434/v1' | Set-Content .env"

if defined MODEL_NAME (
    powershell -Command "(Get-Content .env) -replace 'OLLAMA_MODEL=.*', 'OLLAMA_MODEL=%MODEL_NAME%' | Set-Content .env"
)

echo [OK] 環境設定を更新しました

REM テスト実行
echo.
echo ====================================================
echo   動作テスト
echo ====================================================
echo.

echo テストプロンプトを送信中...
curl -s http://localhost:11434/api/generate -d "{\"model\": \"%MODEL_NAME%\", \"prompt\": \"Hello\"}" | findstr "response" >nul 2>&1

if %errorlevel% equ 0 (
    echo [OK] Ollamaが正常に動作しています
) else (
    echo [WARNING] テストに失敗しました
    echo Ollamaサービスを再起動してみてください
)

echo.
echo ====================================================
echo   セットアップ完了
echo ====================================================
echo.
echo Ollamaの設定が完了しました！
echo.
echo 使用方法:
echo   1. start-windows.bat を実行してShodo Ecosystemを起動
echo   2. http://localhost:3000 にアクセス
echo   3. 自然言語で操作を入力
echo.
echo 管理コマンド:
echo   ollama list        - インストール済みモデル一覧
echo   ollama pull MODEL  - 新しいモデルをダウンロード
echo   ollama rm MODEL    - モデルを削除
echo   ollama serve       - Ollamaサービスを起動
echo.
echo ====================================================
echo.

pause