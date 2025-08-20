"""
ヘルスチェックエンドポイント
"""

from fastapi import APIRouter, Depends
from typing import Dict
import os
import httpx
from datetime import datetime

from ...schemas.common import HealthCheck

router = APIRouter()

async def check_database() -> bool:
    """データベース接続チェック"""
    try:
        # TODO: 実際のDB接続チェック
        return True
    except Exception:
        return False

async def check_redis() -> bool:
    """Redis接続チェック"""
    try:
        # TODO: 実際のRedis接続チェック
        return True
    except Exception:
        return False

async def check_vllm() -> bool:
    """vLLMサーバー接続チェック"""
    try:
        vllm_url = os.getenv("VLLM_URL", "http://vllm:8001")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{vllm_url}/health", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False

@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    ヘルスチェック
    
    システムの健全性を確認します。
    """
    services = {
        "database": await check_database(),
        "redis": await check_redis(),
        "vllm": await check_vllm(),
    }
    
    all_healthy = all(services.values())
    
    return HealthCheck(
        status="healthy" if all_healthy else "degraded",
        version="1.0.0",
        timestamp=datetime.utcnow(),
        services=services
    )

@router.get("/ready")
async def readiness_check():
    """
    レディネスチェック
    
    サービスがリクエストを受け付ける準備ができているか確認します。
    """
    # 必須サービスのチェック
    db_ready = await check_database()
    redis_ready = await check_redis()
    
    if db_ready and redis_ready:
        return {"status": "ready"}
    else:
        return {"status": "not_ready"}, 503

@router.get("/live")
async def liveness_check():
    """
    ライブネスチェック
    
    プロセスが生きているか確認します。
    """
    return {"status": "alive"}