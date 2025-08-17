@echo off
echo Starting Shodo Ecosystem Backend...

REM Pythonパスを設定
set PYTHONPATH=%cd%

REM 依存関係の確認
echo Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install fastapi uvicorn python-multipart python-dotenv
)

REM サーバーを起動
echo Starting server on http://localhost:8000
python run_server.py

pause