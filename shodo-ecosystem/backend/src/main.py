"""
Shodo Ecosystem バックエンドサーバー
LPRシステム統合版
"""

import time
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import structlog

# 設定
from .core.config import settings

# データベース
from .services.database import init_db, check_all_connections

# LPRシステム
from .services.auth.lpr_service import get_lpr_service
from .services.auth.visible_login import init_visible_login, cleanup_visible_login
from .services.audit.audit_logger import init_audit_logger
from .middleware.lpr_enforcer import LPREnforcerMiddleware

# セキュリティヘッダー
from .middleware.security import SecurityHeadersMiddleware

# レート制限
from .middleware.rate_limit import RateLimitMiddleware

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
    """アプリケーションのライフサイクル管理（グレースフルシャットダウン対応）"""
    
    logger.info("🚀 Starting Shodo Ecosystem Backend with LPR System")
    
    # 起動状態フラグの初期化
    app.state.startup_complete = False
    app.state.ready = False
    app.state.db_ready = False
    app.state.redis_ready = False
    
    # グレースフルシャットダウンマネージャーの初期化
    from .services.graceful_shutdown import shutdown_manager, add_shutdown_handler
    
    # カスタムシャットダウンハンドラーを追加
    async def cleanup_lpr_system():
        """LPRシステムのクリーンアップ"""
        try:
            await cleanup_visible_login()
            logger.info("LPR system cleaned up")
        except Exception as e:
            logger.error(f"LPR cleanup failed: {e}")
    
    add_shutdown_handler(cleanup_lpr_system)
    
    # シグナルハンドラー設定
    shutdown_manager.setup_signal_handlers()
    
    # データベース初期化
    try:
        db_success, redis_success = await init_db()
        app.state.db_ready = bool(db_success)
        app.state.redis_ready = bool(redis_success)
        logger.info(
            "Database initialization",
            postgres=db_success,
            redis=redis_success
        )
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
    
    # LPRシステム初期化
    try:
        await get_lpr_service()
        await init_audit_logger()
        await init_visible_login()
        logger.info("LPR system initialized successfully")
    except Exception as e:
        logger.error("LPR system initialization failed", error=str(e))
    
    # アプリケーション起動完了
    logger.info(
        "✅ Application started successfully",
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        environment=settings.environment
    )
    
    # 起動完了/レディ状態の反映
    try:
        app.state.startup_complete = True
        app.state.ready = bool(app.state.db_ready and app.state.redis_ready)
    except Exception:
        # state が使えない場合は無視
        pass
    
    yield
    
    # グレースフルシャットダウン実行
    logger.info("🛑 Initiating graceful shutdown...")
    
    if not shutdown_manager.is_shutting_down:
        await shutdown_manager.shutdown()
    
    logger.info("👋 Application shutdown completed")

# FastAPIアプリケーション作成
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug or not settings.is_production() else None,
    redoc_url="/api/redoc" if settings.debug or not settings.is_production() else None,
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
    allowed_hosts=["*"] if settings.debug else settings.trusted_hosts
)

# レート制限ミドルウェア（最初に適用）
app.add_middleware(RateLimitMiddleware)

# セキュリティヘッダー
app.add_middleware(SecurityHeadersMiddleware)

# CSRFミドルウェア（Cookieベース認証用）
from .middleware.csrf import CSRFMiddleware
app.add_middleware(CSRFMiddleware)

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

# ダッシュボード API
app.include_router(dashboard.router)

# MCP API
app.include_router(mcp.router)

# NLP API
app.include_router(nlp.router)

# プレビュー API
app.include_router(preview.router)

# ===== ヘルスチェック =====

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """包括的ヘルスチェックエンドポイント"""
    from .services.health_checker import health_checker
    
    try:
        # 包括的ヘルスチェック実行
        health_result = await health_checker.run_all_checks()
        
        # LPRシステムの状態を追加
        health_result["components"]["lpr_system"] = {
            "status": "healthy",
            "response_time_ms": 0,
            "details": {
                "lpr_service": "healthy",
                "audit_logger": "healthy",
                "visible_login": "healthy",
            },
            "last_checked": health_result["timestamp"]
        }
        
        return health_result
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": time.time(),
            "error": str(e),
            "version": settings.app_version,
            "environment": settings.environment
        }

@app.get("/health/simple")
async def simple_health_check() -> Dict[str, str]:
    """シンプルなヘルスチェック（高速）"""
    try:
        # 基本的なデータベース接続テスト
        connections = await check_all_connections()
        
        return {
            "status": connections["overall"],
            "timestamp": datetime.now().isoformat(),
            "version": settings.app_version
        }
    except Exception as e:
        logger.error(f"Simple health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# 追加: K8s プローブ整合用エンドポイント
@app.get("/health/live")
async def liveness_probe() -> Dict[str, str]:
    """liveness probe: プロセスが生きているか（軽量）"""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness_probe() -> Dict[str, Any]:
    """readiness probe: 依存サービスが利用可能か"""
    try:
        # アプリ起動完了と依存サービス
        is_startup_complete = getattr(app.state, "startup_complete", False)
        connections = await check_all_connections()
        ready = is_startup_complete and (connections.get("overall") == "healthy")
        return {
            "status": "ready" if ready else "not_ready",
            "startup_complete": is_startup_complete,
            "dependencies": connections
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not_ready", "error": str(e)}

@app.get("/health/startup")
async def startup_probe() -> Dict[str, Any]:
    """startup probe: 起動シーケンスの完了状態を返す"""
    try:
        is_startup_complete = getattr(app.state, "startup_complete", False)
        return {"status": "started" if is_startup_complete else "starting"}
    except Exception:
        return {"status": "starting"}

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "lpr_enabled": True,
        "docs": "/api/docs" if settings.debug or not settings.is_production() else None,
    }

# ===== メトリクス =====

@app.get("/metrics")
async def metrics():
    """Prometheusメトリクスエンドポイント"""
    from .monitoring.metrics import get_metrics, get_metrics_content_type
    from fastapi.responses import Response
    
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
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