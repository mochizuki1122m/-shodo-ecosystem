"""
Shodo Ecosystem バックエンドサーバー
LPRシステム統合版
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import structlog

# 設定
from .core.config import settings

# データベース
from .services.database import init_db, close_db, check_all_connections

# LPRシステム
from .services.auth.lpr import init_lpr_service
from .services.auth.visible_login import init_visible_login, cleanup_visible_login
from .services.audit.audit_logger import init_audit_logger
from .middleware.lpr_enforcer import LPREnforcerMiddleware

# APIルーター
from .api.v1 import auth, dashboard, mcp, nlp, preview, lpr

# 構造化ログの設定
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# ロガー
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    
    logger.info("Starting Shodo Ecosystem Backend with LPR System")
    
    # データベース初期化
    try:
        db_success, redis_success = await init_db()
        logger.info(
            "Database initialization",
            postgres=db_success,
            redis=redis_success
        )
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
    
    # LPRシステム初期化
    try:
        await init_lpr_service()
        await init_audit_logger()
        await init_visible_login()
        logger.info("LPR system initialized successfully")
    except Exception as e:
        logger.error("LPR system initialization failed", error=str(e))
    
    # アプリケーション起動完了
    logger.info(
        "Application started",
        host=settings.host,
        port=settings.port,
        debug=settings.debug
    )
    
    yield
    
    # クリーンアップ
    logger.info("Shutting down application")
    
    try:
        await cleanup_visible_login()
        await close_db()
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error("Cleanup failed", error=str(e))

# FastAPIアプリケーション作成
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# ===== ミドルウェア設定 =====

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-Process-Time"],
)

# 信頼できるホストの制限
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else [
        "localhost",
        "127.0.0.1",
        "shodo.local",
        "*.shodo.local",
    ]
)

# LPRエンフォーサーミドルウェア
app.add_middleware(LPREnforcerMiddleware)

# カスタムエラーハンドラー
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """グローバル例外ハンドラー"""
    logger.error(
        "Unhandled exception",
        path=str(request.url.path),
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred",
        }
    )

# ===== APIルーター登録 =====

# 認証API
app.include_router(auth.router)

# LPR API
app.include_router(lpr.router)

# ダッシュボードAPI
app.include_router(dashboard.router)

# MCP API（LPR保護）
app.include_router(mcp.router)

# NLP API（LPR保護）
app.include_router(nlp.router)

# プレビューAPI（LPR保護）
app.include_router(preview.router)

# ===== ヘルスチェック =====

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """ヘルスチェックエンドポイント"""
    
    # 接続状態をチェック
    connections = await check_all_connections()
    
    # LPRシステムの状態
    lpr_status = {
        "lpr_service": "healthy",
        "audit_logger": "healthy",
        "visible_login": "healthy",
    }
    
    return {
        "status": connections["overall"],
        "version": settings.app_version,
        "connections": connections,
        "lpr_system": lpr_status,
    }

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "lpr_enabled": True,
        "docs": "/api/docs" if settings.debug else None,
    }

# ===== メトリクス =====

@app.get("/metrics")
async def metrics():
    """Prometheusメトリクスエンドポイント"""
    
    # TODO: 実際のメトリクス収集
    metrics_data = {
        "lpr_tokens_issued": 0,
        "lpr_tokens_verified": 0,
        "lpr_tokens_revoked": 0,
        "audit_logs_written": 0,
        "visible_logins_attempted": 0,
        "visible_logins_successful": 0,
    }
    
    # Prometheus形式で返す
    lines = []
    for key, value in metrics_data.items():
        lines.append(f"# TYPE {key} counter")
        lines.append(f"{key} {value}")
    
    return Response(
        content="\n".join(lines),
        media_type="text/plain"
    )

# ===== 管理API =====

@app.post("/api/admin/lpr/cleanup")
async def cleanup_expired_tokens():
    """期限切れLPRトークンのクリーンアップ"""
    
    # TODO: 実装
    return {
        "message": "Cleanup completed",
        "cleaned": 0,
    }

@app.get("/api/admin/lpr/stats")
async def get_lpr_statistics():
    """LPRシステムの統計情報"""
    
    # TODO: 実装
    return {
        "total_tokens": 0,
        "active_tokens": 0,
        "revoked_tokens": 0,
        "expired_tokens": 0,
        "audit_logs": 0,
        "device_fingerprints": 0,
    }

# ===== デバッグエンドポイント（開発環境のみ） =====

if settings.debug:
    @app.get("/debug/config")
    async def debug_config():
        """設定情報（デバッグ用）"""
        return {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "debug": settings.debug,
            "cors_origins": settings.cors_origins,
            "rate_limit_enabled": settings.rate_limit_enabled,
        }
    
    @app.post("/debug/test-lpr")
    async def test_lpr_flow():
        """LPRフローのテスト"""
        return {
            "message": "Test endpoint for LPR flow",
            "steps": [
                "1. Call /api/v1/lpr/visible-login",
                "2. Call /api/v1/lpr/issue",
                "3. Use token for protected endpoints",
                "4. Call /api/v1/lpr/revoke",
            ]
        }

# ===== メイン実行 =====

if __name__ == "__main__":
    # ログレベル設定
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format=settings.log_format,
    )
    
    # サーバー起動
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )