"""
ヘルスチェックエンドポイント
"""

from datetime import datetime
import os
from fastapi import APIRouter
import httpx

from src.schemas.common import HealthCheck
from src.services.database import check_all_connections

router = APIRouter()

@router.get("/health", response_model=HealthCheck)
async def health():
    connections = await check_all_connections()
    return HealthCheck(status=connections["overall"])

@router.get("/ready")
async def readiness_check():
    """
    レディネスチェック
    
    サービスがリクエストを受け付ける準備ができているか確認します。
    """
    # 必須サービスのチェック
    db_ready = await check_database_health()
    redis_ready = await check_redis_health()
    
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