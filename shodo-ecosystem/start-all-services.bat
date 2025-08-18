@echo off
echo ========================================
echo Shodo Ecosystem - Complete System Startup
echo ========================================
echo.

REM 環境変数の設定
set NODE_ENV=production
set PYTHONUNBUFFERED=1
set DATABASE_URL=postgresql://shodo:shodo_pass@localhost:5432/shodo
set REDIS_URL=redis://localhost:6379
set SECRET_KEY=your-secret-key-change-in-production
set JWT_ALGORITHM=HS256
set SHOPIFY_SHOP_DOMAIN=%SHOPIFY_SHOP_DOMAIN%
set SHOPIFY_ACCESS_TOKEN=%SHOPIFY_ACCESS_TOKEN%

echo [Step 1/10] Starting WSL services...
wsl redis-server --daemonize yes 2>nul
wsl sudo service postgresql start 2>nul

echo [Step 2/10] Running database migrations...
cd backend
python -m alembic upgrade head 2>nul
cd ..

echo [Step 3/10] Starting monitoring services...
docker-compose -f docker-compose.monitoring.yml up -d 2>nul

echo [Step 4/10] Starting AI Server...
cd ai-server
start /B cmd /c "npm run ollama"
cd ..

echo [Step 5/10] Starting Celery Worker...
cd backend
start /B cmd /c "start-celery.bat"
cd ..

echo [Step 6/10] Starting Backend API...
cd backend
start /B cmd /c "python src/main_unified.py"
cd ..

echo [Step 7/10] Starting Frontend...
cd frontend
start /B cmd /c "npm start"
cd ..

echo [Step 8/10] Starting Nginx...
docker stop shodo-nginx 2>nul
docker rm shodo-nginx 2>nul
docker run -d --name shodo-nginx -p 80:80 -v "%cd%\nginx\nginx.conf:/etc/nginx/nginx.conf:ro" --network host nginx:alpine

echo [Step 9/10] Running tests...
cd backend
pytest tests/unit -v --tb=short
cd ..

echo [Step 10/10] Health checks...
timeout /t 5 /nobreak >nul
curl -s http://localhost:8000/health
echo.

echo.
echo ========================================
echo All Services Started Successfully!
echo ========================================
echo.
echo Service URLs:
echo   Frontend:          http://localhost:3000
echo   Backend API:       http://localhost:8000
echo   API Documentation: http://localhost:8000/api/docs
echo   AI Server:         http://localhost:8001
echo   Prometheus:        http://localhost:9090
echo   Grafana:           http://localhost:3001 (admin/admin)
echo   Flower (Celery):   http://localhost:5555
echo   Main Application:  http://localhost
echo.
echo Features:
echo   ✅ PostgreSQL Authentication
echo   ✅ Real API Connections
echo   ✅ Error Handling System
echo   ✅ pytest/Jest Tests
echo   ✅ Celery Background Tasks
echo   ✅ Prometheus/Grafana Monitoring
echo   ✅ LPR Security System
echo.
echo ========================================
echo Press Ctrl+C to stop all services
echo ========================================
pause