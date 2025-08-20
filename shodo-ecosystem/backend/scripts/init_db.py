#!/usr/bin/env python3
"""
データベース初期化スクリプト
初回セットアップ時にテーブル作成とサンプルデータを投入
"""

import asyncio
import logging
import sys
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.services.database import get_db_engine, get_redis
from src.core.config import settings
from src.models.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_tables():
    """テーブル作成"""
    logger.info("Creating database tables...")
    
    engine = get_db_engine()
    if not engine:
        logger.error("Failed to get database engine")
        return False
    
    try:
        async with engine.begin() as conn:
            # 既存テーブルの確認
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            existing_tables = [row[0] for row in result]
            
            if existing_tables:
                logger.info(f"Found existing tables: {existing_tables}")
                
                # 強制再作成の確認
                if "--force" in sys.argv:
                    logger.warning("Dropping all existing tables...")
                    await conn.execute(text("DROP SCHEMA public CASCADE"))
                    await conn.execute(text("CREATE SCHEMA public"))
                    await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
                else:
                    logger.info("Tables already exist. Use --force to recreate.")
                    return True
            
            # テーブル作成
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False

async def create_initial_data():
    """初期データの投入"""
    logger.info("Creating initial data...")
    
    engine = get_db_engine()
    if not engine:
        logger.error("Failed to get database engine")
        return False
    
    try:
        async with engine.begin() as conn:
            # 管理者ユーザーの作成
            admin_user_sql = """
                INSERT INTO users (
                    user_id, email, username, full_name, 
                    is_active, is_superuser, created_at
                ) VALUES (
                    gen_random_uuid(),
                    'admin@shodo.local',
                    'admin',
                    'System Administrator',
                    true,
                    true,
                    NOW()
                ) ON CONFLICT (email) DO NOTHING
            """
            await conn.execute(text(admin_user_sql))
            
            # デフォルトサービス設定
            services_sql = """
                INSERT INTO services (
                    service_id, name, type, status, 
                    config, created_at
                ) VALUES 
                (
                    'shopify-default',
                    'Shopify Store',
                    'shopify',
                    'configured',
                    '{"store_url": "example.myshopify.com", "api_version": "2023-10"}',
                    NOW()
                ),
                (
                    'stripe-default',
                    'Stripe Payments',
                    'stripe',
                    'configured',
                    '{"api_version": "2023-10-16", "webhook_enabled": true}',
                    NOW()
                ),
                (
                    'gmail-default',
                    'Gmail Integration',
                    'gmail',
                    'configured',
                    '{"scopes": ["https://www.googleapis.com/auth/gmail.readonly"]}',
                    NOW()
                )
                ON CONFLICT (service_id) DO NOTHING
            """
            await conn.execute(text(services_sql))
            
            # NLPパターンの初期データ
            nlp_patterns_sql = """
                INSERT INTO nlp_patterns (
                    pattern_id, pattern, intent, confidence,
                    service_type, created_at
                ) VALUES
                (
                    gen_random_uuid(),
                    '(エクスポート|出力|ダウンロード)',
                    'export',
                    0.9,
                    'universal',
                    NOW()
                ),
                (
                    gen_random_uuid(),
                    '(商品|プロダクト).*?(追加|作成|登録)',
                    'create_product',
                    0.85,
                    'shopify',
                    NOW()
                ),
                (
                    gen_random_uuid(),
                    '(注文|オーダー).*?(確認|チェック|見る)',
                    'view_orders',
                    0.8,
                    'shopify',
                    NOW()
                ),
                (
                    gen_random_uuid(),
                    '(メール|メッセージ).*?(送信|送る)',
                    'send_email',
                    0.85,
                    'gmail',
                    NOW()
                ),
                (
                    gen_random_uuid(),
                    '(売上|収益|支払い).*?(確認|チェック)',
                    'view_revenue',
                    0.8,
                    'stripe',
                    NOW()
                )
                ON CONFLICT (pattern_id) DO NOTHING
            """
            await conn.execute(text(nlp_patterns_sql))
            
            logger.info("✅ Initial data created successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create initial data: {e}")
        return False

async def test_connections():
    """接続テスト"""
    logger.info("Testing database and Redis connections...")
    
    # データベース接続テスト
    engine = get_db_engine()
    if engine:
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
                logger.info("✅ Database connection successful")
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    else:
        logger.error("❌ Failed to get database engine")
        return False
    
    # Redis接続テスト
    try:
        redis_client = get_redis()
        if redis_client:
            if hasattr(redis_client, 'ping'):
                if asyncio.iscoroutinefunction(redis_client.ping):
                    await redis_client.ping()
                else:
                    redis_client.ping()
                logger.info("✅ Redis connection successful")
            else:
                logger.info("✅ Redis client created (ping not available)")
        else:
            logger.warning("⚠️ Redis not available (degraded mode)")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e} (degraded mode)")
    
    return True

async def create_extensions():
    """PostgreSQL拡張機能の有効化"""
    logger.info("Creating PostgreSQL extensions...")
    
    engine = get_db_engine()
    if not engine:
        return False
    
    try:
        async with engine.begin() as conn:
            # UUID拡張
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            
            # 暗号化拡張
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            
            # 全文検索拡張
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            
            # 統計拡張
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))
            
            logger.info("✅ PostgreSQL extensions created successfully")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create extensions: {e}")
        return False

async def main():
    """メイン処理"""
    logger.info("🚀 Starting Shodo Ecosystem database initialization...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database URL: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'masked'}")
    
    try:
        # 1. 接続テスト
        if not await test_connections():
            logger.error("❌ Connection tests failed")
            return False
        
        # 2. PostgreSQL拡張機能の有効化
        if not await create_extensions():
            logger.error("❌ Failed to create extensions")
            return False
        
        # 3. テーブル作成
        if not await create_tables():
            logger.error("❌ Failed to create tables")
            return False
        
        # 4. 初期データ投入
        if not await create_initial_data():
            logger.error("❌ Failed to create initial data")
            return False
        
        logger.info("🎉 Database initialization completed successfully!")
        
        # 初期化完了の確認
        engine = get_db_engine()
        async with engine.begin() as conn:
            # テーブル数確認
            result = await conn.execute(text("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            table_count = result.scalar()
            
            # ユーザー数確認
            try:
                result = await conn.execute(text("SELECT COUNT(*) FROM users"))
                user_count = result.scalar()
                logger.info(f"📊 Tables created: {table_count}, Users: {user_count}")
            except:
                logger.info(f"📊 Tables created: {table_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize Shodo Ecosystem database")
    parser.add_argument("--force", action="store_true", help="Force recreate all tables")
    args = parser.parse_args()
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)