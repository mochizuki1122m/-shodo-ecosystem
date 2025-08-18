"""
データベース接続とヘルスチェック
"""

import os
import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# データベース設定
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://shodo:shodo_pass@localhost:5432/shodo")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# グローバル接続インスタンス
db_connection = None
redis_connection = None

class DatabaseConnection:
    """データベース接続管理"""
    
    def __init__(self, url: str):
        self.url = url
        self.pool = None
        self.is_connected = False
    
    async def connect(self):
        """データベースに接続"""
        try:
            # 実際の実装ではasyncpgやSQLAlchemyを使用
            # import asyncpg
            # self.pool = await asyncpg.create_pool(self.url)
            
            # モック実装
            await asyncio.sleep(0.1)  # 接続シミュレート
            self.is_connected = True
            logger.info(f"Connected to database: {self.url.split('@')[-1]}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """データベース接続を閉じる"""
        if self.pool:
            # await self.pool.close()
            pass
        self.is_connected = False
        logger.info("Disconnected from database")
    
    async def health_check(self) -> bool:
        """ヘルスチェック"""
        if not self.is_connected:
            return False
        
        try:
            # 実際の実装では簡単なクエリを実行
            # async with self.pool.acquire() as conn:
            #     await conn.fetchval("SELECT 1")
            await asyncio.sleep(0.01)
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

class RedisConnection:
    """Redis接続管理"""
    
    def __init__(self, url: str):
        self.url = url
        self.client = None
        self.is_connected = False
    
    async def connect(self):
        """Redisに接続"""
        try:
            # 実際の実装ではaioredisを使用
            # import aioredis
            # self.client = await aioredis.from_url(self.url)
            
            # モック実装
            await asyncio.sleep(0.05)
            self.is_connected = True
            logger.info(f"Connected to Redis: {self.url.split('@')[-1]}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Redis接続を閉じる"""
        if self.client:
            # await self.client.close()
            pass
        self.is_connected = False
        logger.info("Disconnected from Redis")
    
    async def health_check(self) -> bool:
        """ヘルスチェック"""
        if not self.is_connected:
            return False
        
        try:
            # 実際の実装ではPINGを送信
            # await self.client.ping()
            await asyncio.sleep(0.01)
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

async def init_db():
    """データベース初期化"""
    global db_connection, redis_connection
    
    # PostgreSQL接続
    db_connection = DatabaseConnection(DATABASE_URL)
    db_success = await db_connection.connect()
    
    if not db_success:
        logger.warning("Running without database connection (degraded mode)")
    
    # Redis接続
    redis_connection = RedisConnection(REDIS_URL)
    redis_success = await redis_connection.connect()
    
    if not redis_success:
        logger.warning("Running without Redis connection (cache disabled)")
    
    # 少なくとも1つは接続できていればOK
    if not db_success and not redis_success:
        logger.error("Failed to connect to any data store")
        # 本番環境では起動を停止する場合もある
        # raise RuntimeError("No data store available")
    
    return db_success, redis_success

async def close_db():
    """データベース接続を閉じる"""
    global db_connection, redis_connection
    
    if db_connection:
        await db_connection.disconnect()
    
    if redis_connection:
        await redis_connection.disconnect()

async def get_db():
    """データベース接続を取得"""
    global db_connection
    
    if not db_connection or not db_connection.is_connected:
        raise RuntimeError("Database not connected")
    
    return db_connection

async def get_redis():
    """Redis接続を取得"""
    global redis_connection
    
    if not redis_connection or not redis_connection.is_connected:
        raise RuntimeError("Redis not connected")
    
    return redis_connection

async def check_all_connections() -> dict:
    """すべての接続のヘルスチェック"""
    results = {
        "database": False,
        "redis": False,
        "overall": "unhealthy"
    }
    
    if db_connection:
        results["database"] = await db_connection.health_check()
    
    if redis_connection:
        results["redis"] = await redis_connection.health_check()
    
    # 全体のステータス判定
    if results["database"] and results["redis"]:
        results["overall"] = "healthy"
    elif results["database"] or results["redis"]:
        results["overall"] = "degraded"
    else:
        results["overall"] = "unhealthy"
    
    return results

@asynccontextmanager
async def get_db_session():
    """データベースセッションのコンテキストマネージャー"""
    # 実際の実装ではトランザクション管理を行う
    try:
        # async with db_connection.pool.acquire() as conn:
        #     async with conn.transaction():
        #         yield conn
        yield db_connection
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise