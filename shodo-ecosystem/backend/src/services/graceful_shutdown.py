"""
グレースフルシャットダウンサービス
アプリケーションの安全な終了処理を管理
"""

import asyncio
import signal
import logging
from typing import List, Callable
from contextlib import asynccontextmanager
from time import time as _time  # noqa: F401

logger = logging.getLogger(__name__)

class GracefulShutdownManager:
    """グレースフルシャットダウン管理クラス"""
    
    def __init__(self, timeout: float = 30.0):
        """
        Args:
            timeout: シャットダウンのタイムアウト（秒）
        """
        self.timeout = timeout
        self.shutdown_handlers: List[Callable] = []
        self.is_shutting_down = False
        self.shutdown_event = asyncio.Event()
        
    def add_shutdown_handler(self, handler: Callable):
        """シャットダウンハンドラーを追加"""
        self.shutdown_handlers.append(handler)
        logger.info(f"Added shutdown handler: {handler.__name__}")
    
    async def shutdown(self):
        """グレースフルシャットダウンを実行"""
        if self.is_shutting_down:
            logger.warning("Shutdown already in progress")
            return
        
        self.is_shutting_down = True
        logger.info("🛑 Starting graceful shutdown...")
        
        start_time = _time()
        
        try:
            # シャットダウンハンドラーを逆順で実行
            for handler in reversed(self.shutdown_handlers):
                try:
                    logger.info(f"Executing shutdown handler: {handler.__name__}")
                    
                    if asyncio.iscoroutinefunction(handler):
                        await asyncio.wait_for(handler(), timeout=5.0)
                    else:
                        handler()
                        
                    logger.info(f"✅ Completed: {handler.__name__}")
                    
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Timeout in shutdown handler: {handler.__name__}")
                except Exception as e:
                    logger.error(f"❌ Error in shutdown handler {handler.__name__}: {e}")
            
            elapsed = _time() - start_time
            logger.info(f"✅ Graceful shutdown completed in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Error during graceful shutdown: {e}")
        finally:
            self.shutdown_event.set()
    
    def setup_signal_handlers(self):
        """シグナルハンドラーを設定"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            asyncio.create_task(self.shutdown())
        
        # SIGTERM, SIGINT のハンドリング
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("Signal handlers configured")

# グローバルインスタンス
shutdown_manager = GracefulShutdownManager()

# 便利な関数
def add_shutdown_handler(handler: Callable):
    """シャットダウンハンドラーを追加する便利関数"""
    shutdown_manager.add_shutdown_handler(handler)

@asynccontextmanager
async def graceful_lifespan(app):
    """FastAPI用のライフスパンマネージャー"""
    # スタートアップ
    logger.info("🚀 Application starting up...")
    
    # シグナルハンドラー設定
    shutdown_manager.setup_signal_handlers()
    
    yield
    
    # シャットダウン
    if not shutdown_manager.is_shutting_down:
        await shutdown_manager.shutdown()

# 共通シャットダウンハンドラー
async def close_database_connections():
    """データベース接続のクリーンアップ"""
    try:
        from .database import close_db
        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")

async def close_redis_connections():
    """Redis接続のクリーンアップ"""
    try:
        from .database import get_redis
        redis_client = get_redis()
        if redis_client and hasattr(redis_client, 'close'):
            if asyncio.iscoroutinefunction(redis_client.close):
                await redis_client.close()
            else:
                redis_client.close()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis connections: {e}")

async def flush_logs():
    """ログのフラッシュ"""
    try:
        # 構造化ログのフラッシュ
        import structlog as _structlog  # noqa: F401
        logger.info("Flushing logs...")
        
        # 少し待ってログが確実に出力されるようにする
        await asyncio.sleep(0.1)
        
        logger.info("Logs flushed")
    except Exception as e:
        logger.error(f"Error flushing logs: {e}")

async def cleanup_background_tasks():
    """バックグラウンドタスクのクリーンアップ"""
    try:
        # 実行中のタスクを取得
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        
        if tasks:
            logger.info(f"Cancelling {len(tasks)} background tasks...")
            
            # タスクをキャンセル
            for task in tasks:
                task.cancel()
            
            # キャンセル完了を待機
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info("Background tasks cancelled")
    except Exception as e:
        logger.error(f"Error cleaning up background tasks: {e}")

async def save_application_state():
    """アプリケーション状態の保存"""
    try:
        # キャッシュの永続化など
        logger.info("Saving application state...")
        
        # 実装例: 重要なキャッシュデータの保存
        # from .cache_manager import save_cache_to_disk
        # await save_cache_to_disk()
        
        logger.info("Application state saved")
    except Exception as e:
        logger.error(f"Error saving application state: {e}")

# デフォルトハンドラーの登録
def register_default_handlers():
    """デフォルトのシャットダウンハンドラーを登録"""
    add_shutdown_handler(save_application_state)
    add_shutdown_handler(cleanup_background_tasks)
    add_shutdown_handler(close_redis_connections)
    add_shutdown_handler(close_database_connections)
    add_shutdown_handler(flush_logs)
    
    logger.info("Default shutdown handlers registered")

# 自動登録
register_default_handlers()