"""
Shodo Ecosystem バックエンドAPIサーバー
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# ローカルインポート
from src.api.v1 import auth, nlp, preview, dashboard, mcp
from src.services.database import init_db, get_db
from src.utils.config import settings

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ライフサイクル管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時
    logger.info("Starting Shodo Ecosystem Backend...")
    
    try:
        db_status, redis_status = await init_db()
        if db_status and redis_status:
            logger.info("All services initialized successfully")
        elif db_status or redis_status:
            logger.warning("Running in degraded mode - some services unavailable")
        else:
            logger.error("No data stores available - running with in-memory storage only")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        logger.warning("Running without external services")
    
    yield
    
    # 終了時
    logger.info("Shutting down Shodo Ecosystem Backend...")
    try:
        from src.services.database import close_db
        await close_db()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# FastAPIアプリケーションの作成
app = FastAPI(
    title="Shodo Ecosystem API",
    description="AI-powered SaaS integration platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit-Minute", "X-RateLimit-Remaining-Minute"]
)

# セキュリティミドルウェアの設定
try:
    from src.middleware.security import setup_security_middleware
    setup_security_middleware(app, settings)
except ImportError:
    logger.warning("Security middleware not available")

# エラーハンドラー
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# ルートエンドポイント
@app.get("/")
async def root():
    return {
        "name": "Shodo Ecosystem API",
        "version": "1.0.0",
        "status": "running"
    }

# ヘルスチェック
@app.get("/health")
async def health_check():
    from src.services.database import check_all_connections
    import httpx
    
    # データベース/Redis接続チェック
    try:
        db_status = await check_all_connections()
    except:
        db_status = {
            "database": False,
            "redis": False,
            "overall": "unhealthy"
        }
    
    # AIサーバー接続チェック
    ai_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.vllm_url}/health", timeout=2.0)
            ai_status = "connected" if response.status_code == 200 else "error"
    except:
        ai_status = "disconnected"
    
    return {
        "status": db_status["overall"],
        "database": "connected" if db_status["database"] else "disconnected",
        "cache": "connected" if db_status["redis"] else "disconnected",
        "ai_server": ai_status,
        "timestamp": datetime.utcnow()
    }

# APIルーターの登録
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(nlp.router, prefix="/api/v1/nlp", tags=["NLP"])
app.include_router(preview.router, prefix="/api/v1/preview", tags=["Preview"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["MCP"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )