"""
データベース接続管理
"""

import os
from typing import Tuple
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import redis.asyncio as redis
from contextlib import asynccontextmanager

# 統一設定から読み込み
from ..core.config import settings
DATABASE_URL = settings.database_url
REDIS_URL = settings.redis_url

# SQLAlchemy エンジン
engine = None
AsyncSessionLocal = None

# Redis クライアント
redis_client = None

async def init_db() -> Tuple[bool, bool]:
    """データベース初期化"""
    global engine, AsyncSessionLocal, redis_client
    
    try:
        # PostgreSQL接続
        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            poolclass=NullPool,  # 開発環境用
        )
        
        AsyncSessionLocal = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # テーブル作成（必要に応じて）
        # async with engine.begin() as conn:
        #     await conn.run_sync(Base.metadata.create_all)
        
        postgres_success = True
    except Exception as e:
        print(f"PostgreSQL initialization failed: {e}")
        postgres_success = False
    
    try:
        # Redis接続
        redis_client = await redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        redis_success = True
    except Exception as e:
        print(f"Redis initialization failed: {e}")
        redis_success = False
    
    return postgres_success, redis_success

async def close_db():
    """データベース接続クローズ"""
    global engine, redis_client
    
    if engine:
        await engine.dispose()
    
    if redis_client:
        await redis_client.close()

async def get_db():
    """データベースセッション取得"""
    if AsyncSessionLocal is None:
        await init_db()
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# 暫定的な互換性のためのエイリアス
get_db_session = get_db

def get_redis():
    """Redisクライアント取得"""
    return redis_client

async def check_all_connections() -> dict:
    """全接続状態チェック"""
    status = {
        "postgres": False,
        "redis": False,
        "overall": "unhealthy"
    }
    
    # PostgreSQL チェック
    if engine:
        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                status["postgres"] = True
        except:
            pass
    
    # Redis チェック
    if redis_client:
        try:
            await redis_client.ping()
            status["redis"] = True
        except:
            pass
    
    # 全体ステータス
    if status["postgres"] and status["redis"]:
        status["overall"] = "healthy"
    elif status["postgres"] or status["redis"]:
        status["overall"] = "partial"
    
    return status

@asynccontextmanager
async def get_session():
    """セッションコンテキストマネージャー"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()