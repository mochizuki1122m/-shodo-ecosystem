@echo off
echo ========================================
echo Shodo Ecosystem Unified Startup (Windows)
echo ========================================
echo.

REM 環境変数の設定
set NODE_ENV=development
set PYTHONUNBUFFERED=1
set DATABASE_URL=postgresql://shodo:shodo_pass@localhost:5432/shodo
set REDIS_URL=redis://localhost:6379
set SECRET_KEY=your-secret-key-change-in-production
set JWT_ALGORITHM=HS256

REM Redisの起動（WSL経由）
echo [1/6] Starting Redis via WSL...
wsl redis-server --daemonize yes 2>nul
if %errorlevel% neq 0 (
    echo Warning: Redis startup failed. Make sure WSL is installed.
)

REM PostgreSQLの起動（WSL経由）
echo [2/6] Starting PostgreSQL via WSL...
wsl sudo service postgresql start 2>nul
if %errorlevel% neq 0 (
    echo Warning: PostgreSQL startup failed. Make sure WSL and PostgreSQL are installed.
)

REM AIサーバーの起動
echo [3/6] Starting AI Server...
cd ai-server
start /B cmd /c "npm run ollama 2>nul"
cd ..

REM バックエンドの起動
echo [4/6] Starting Backend...
cd backend
start /B cmd /c "python src/main.py 2>nul"
cd ..

REM フロントエンドの起動
echo [5/6] Starting Frontend...
cd frontend
start /B cmd /c "npm start 2>nul"
cd ..

REM Nginxの起動（Docker経由）
echo [6/6] Starting Nginx...
docker stop shodo-nginx 2>nul
docker rm shodo-nginx 2>nul
docker run -d --name shodo-nginx -p 80:80 -v "%cd%\nginx\nginx.conf:/etc/nginx/nginx.conf:ro" --network host nginx:alpine 2>nul
if %errorlevel% neq 0 (
    echo Warning: Nginx startup failed. Make sure Docker is running.
)

echo.
echo ========================================
echo All services started!
echo ========================================
echo.
echo Access points:
echo   Frontend:     http://localhost:3000
echo   Backend API:  http://localhost:8000
echo   API Docs:     http://localhost:8000/api/docs
echo   AI Server:    http://localhost:8001
echo   Main App:     http://localhost
echo.
echo ========================================
echo Press Ctrl+C to stop all services
echo ========================================
pause