"""
Shodo Ecosystem バックエンドサーバー
統合版（Windows対応）
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Windows環境でのパス問題を解決
if sys.platform == "win32":
	import asyncio
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 環境変数設定
os.environ.setdefault("SECRET_KEY", "your-secret-key-change-in-production")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://shodo:shodo_pass@localhost:5432/shodo")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

LIGHT_TESTS = os.getenv("LIGHT_TESTS") == "1"

# データベース
from .services.database import init_db, close_db, check_all_connections

# APIルーター（LIGHT_TESTSでは重いルーターの読み込みを避ける）
if not LIGHT_TESTS:
	from .api.v1 import auth, dashboard, mcp, nlp, preview, lpr

# モニタリング
from .monitoring.metrics import get_metrics, get_metrics_json

# Celery（LIGHT_TESTSでは読み込まない）
if not LIGHT_TESTS:
	from .tasks.celery_app import celery_app

@asynccontextmanager
async def lifespan(app: FastAPI):
	"""アプリケーションのライフサイクル管理"""
	print("Starting Shodo Ecosystem Backend...")
	
	# データベース初期化
	try:
		db_success, redis_success = await init_db()
		print(f"Database initialization - PostgreSQL: {db_success}, Redis: {redis_success}")
	except Exception as e:
		print(f"Database initialization failed: {e}")
	
	yield
	
	# クリーンアップ
	print("Shutting down application...")
	await close_db()

# FastAPIアプリケーション作成
app = FastAPI(
	title="Shodo Ecosystem API",
	version="1.0.0",
	lifespan=lifespan,
	docs_url="/api/docs",
	redoc_url="/api/redoc",
)

# ミドルウェア設定
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],  # 開発環境用
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.add_middleware(
	TrustedHostMiddleware,
	allowed_hosts=["*"]  # 開発環境用
)

# エラーハンドラー
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
	"""グローバル例外ハンドラー"""
	return JSONResponse(
		status_code=500,
		content={
			"error": "Internal server error",
			"message": str(exc) if os.getenv("DEBUG") else "An error occurred",
		}
	)

# APIルーター登録（LIGHT_TESTS時はスキップしてテスト側のスタブに委譲）
if not LIGHT_TESTS:
	app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
	app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
	app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["mcp"])
	app.include_router(nlp.router, prefix="/api/v1/nlp", tags=["nlp"])
	app.include_router(preview.router, prefix="/api/v1/preview", tags=["preview"])
	app.include_router(lpr.router, prefix="/api/v1/lpr", tags=["lpr"])

# ヘルスチェック
@app.get("/health")
async def health_check():
	"""ヘルスチェックエンドポイント"""
	connections = await check_all_connections()
	return {
		"status": connections["overall"],
		"version": "1.0.0",
		"connections": connections
	}

# ルートエンドポイント
@app.get("/")
async def root():
	"""ルートエンドポイント"""
	return {
		"name": "Shodo Ecosystem API",
		"version": "1.0.0",
		"status": "running",
		"docs": "/api/docs"
	}

# メトリクスエンドポイント
@app.get("/metrics")
async def metrics():
	"""Prometheusメトリクスエンドポイント"""
	return Response(content=get_metrics(), media_type="text/plain")

@app.get("/api/v1/metrics")
async def metrics_json():
	"""JSONメトリクスエンドポイント"""
	return get_metrics_json()

# Celeryステータス（LIGHT_TESTSではモック応答）
@app.get("/api/v1/tasks/status")
async def celery_status():
	"""Celeryワーカーステータス"""
	if LIGHT_TESTS:
		return {"active": {}, "scheduled": {}, "stats": {}}
	try:
		i = celery_app.control.inspect()
		return {
			"active": i.active() if i else {},
			"scheduled": i.scheduled() if i else {},
			"stats": i.stats() if i else {}
		}
	except Exception as e:
		return {
			"error": str(e),
			"message": "Celery worker may not be running"
		}

# 管理エンドポイント
@app.post("/api/admin/cleanup")
async def cleanup_old_data():
	"""古いデータのクリーンアップ"""
	# TODO: 実装
	return {"message": "Cleanup completed", "cleaned": 0}

if __name__ == "__main__":
	# Windows環境での実行
	uvicorn.run(
		"main_unified:app" if __name__ != "__main__" else app,
		host="0.0.0.0",
		port=8000,
		reload=True,
		log_level="info"
	)