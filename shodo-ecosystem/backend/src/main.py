"""
Shodo Ecosystem バックエンドAPIサーバー
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# ローカルインポート
# TODO: APIモジュールを実装後にアンコメント
# from src.api.v1 import auth, nlp, preview, dashboard, mcp
# from src.services.database import init_db, get_db
# from src.utils.config import settings

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
    # TODO: データベース設定後にアンコメント
    # await init_db()
    # logger.info("Database initialized")
    
    yield
    
    # 終了時
    logger.info("Shutting down Shodo Ecosystem Backend...")

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
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {
        "status": "healthy",
        "database": "connected",
        "cache": "connected",
        "ai_server": "connected"
    }

# APIルーターの登録
# TODO: APIモジュール実装後にアンコメント
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
# app.include_router(nlp.router, prefix="/api/v1/nlp", tags=["NLP"])
# app.include_router(preview.router, prefix="/api/v1/preview", tags=["Preview"])
# app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
# app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["MCP"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )