#!/usr/bin/env python3
"""
サンプルデータ投入スクリプト
開発・テスト用のサンプルデータを投入
"""

import asyncio
import logging
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# プロジェクトルートをPythonパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.services.database import get_db_engine
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_sample_users():
    """サンプルユーザーの作成"""
    logger.info("Creating sample users...")
    
    engine = get_db_engine()
    async with engine.begin() as conn:
        users_sql = """
            INSERT INTO users (
                user_id, email, username, full_name,
                is_active, is_superuser, created_at
            ) VALUES
            (
                gen_random_uuid(),
                'demo@shodo.local',
                'demo',
                'Demo User',
                true,
                false,
                NOW()
            ),
            (
                gen_random_uuid(),
                'test@shodo.local',
                'testuser',
                'Test User',
                true,
                false,
                NOW()
            ),
            (
                gen_random_uuid(),
                'developer@shodo.local',
                'developer',
                'Developer User',
                true,
                true,
                NOW()
            )
            ON CONFLICT (email) DO NOTHING
        """
        await conn.execute(text(users_sql))
        logger.info("✅ Sample users created")

async def create_sample_sessions():
    """サンプルセッションの作成"""
    logger.info("Creating sample sessions...")
    
    engine = get_db_engine()
    async with engine.begin() as conn:
        # ユーザーIDを取得
        result = await conn.execute(text("SELECT user_id FROM users WHERE email = 'demo@shodo.local'"))
        user_row = result.first()
        if not user_row:
            logger.warning("Demo user not found, skipping session creation")
            return
        
        user_id = user_row[0]
        
        sessions_sql = """
            INSERT INTO user_sessions (
                session_id, user_id, session_data,
                expires_at, created_at, last_accessed
            ) VALUES (
                gen_random_uuid(),
                :user_id,
                '{"preferences": {"language": "ja", "theme": "light"}, "last_activity": "nlp_analysis"}',
                NOW() + INTERVAL '7 days',
                NOW(),
                NOW()
            ) ON CONFLICT DO NOTHING
        """
        await conn.execute(text(sessions_sql), {"user_id": user_id})
        logger.info("✅ Sample sessions created")

async def create_sample_nlp_history():
    """サンプルNLP解析履歴の作成"""
    logger.info("Creating sample NLP analysis history...")
    
    engine = get_db_engine()
    async with engine.begin() as conn:
        # ユーザーIDを取得
        result = await conn.execute(text("SELECT user_id FROM users WHERE email = 'demo@shodo.local'"))
        user_row = result.first()
        if not user_row:
            return
        
        user_id = user_row[0]
        
        sample_analyses = [
            {
                "input": "Shopifyの商品を一覧表示して",
                "intent": "view_products",
                "confidence": 0.92,
                "service": "shopify",
                "entities": {"action": "view", "target": "products"},
                "processing_path": "rule_primary"
            },
            {
                "input": "今月の売上を確認したい",
                "intent": "view_revenue",
                "confidence": 0.88,
                "service": "stripe",
                "entities": {"period": "this_month", "target": "revenue"},
                "processing_path": "ai_primary"
            },
            {
                "input": "未読メールをチェック",
                "intent": "view_emails",
                "confidence": 0.85,
                "service": "gmail",
                "entities": {"status": "unread", "target": "emails"},
                "processing_path": "merged"
            },
            {
                "input": "新しい商品を追加",
                "intent": "create_product",
                "confidence": 0.90,
                "service": "shopify",
                "entities": {"action": "create", "target": "product"},
                "processing_path": "rule_primary"
            }
        ]
        
        for i, analysis in enumerate(sample_analyses):
            nlp_sql = """
                INSERT INTO nlp_analysis_history (
                    analysis_id, user_id, input_text, intent,
                    confidence, entities, service, processing_path,
                    processing_time_ms, created_at
                ) VALUES (
                    gen_random_uuid(),
                    :user_id,
                    :input_text,
                    :intent,
                    :confidence,
                    :entities,
                    :service,
                    :processing_path,
                    :processing_time,
                    NOW() - INTERVAL ':days days'
                )
            """
            await conn.execute(text(nlp_sql), {
                "user_id": user_id,
                "input_text": analysis["input"],
                "intent": analysis["intent"],
                "confidence": analysis["confidence"],
                "entities": json.dumps(analysis["entities"]),
                "service": analysis["service"],
                "processing_path": analysis["processing_path"],
                "processing_time": 150 + i * 50,
                "days": i
            })
        
        logger.info("✅ Sample NLP history created")

async def create_sample_audit_logs():
    """サンプル監査ログの作成"""
    logger.info("Creating sample audit logs...")
    
    engine = get_db_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT user_id FROM users WHERE email = 'demo@shodo.local'"))
        user_row = result.first()
        if not user_row:
            return
        
        user_id = user_row[0]
        
        sample_logs = [
            {
                "action": "login",
                "resource": "auth",
                "details": {"ip": "192.168.1.100", "user_agent": "Mozilla/5.0"}
            },
            {
                "action": "nlp_analysis",
                "resource": "nlp",
                "details": {"input_length": 25, "confidence": 0.92, "service": "shopify"}
            },
            {
                "action": "service_connect",
                "resource": "shopify",
                "details": {"store_url": "demo-store.myshopify.com", "api_version": "2023-10"}
            },
            {
                "action": "preview_generate",
                "resource": "preview",
                "details": {"changes_count": 3, "service": "shopify"}
            }
        ]
        
        for i, log in enumerate(sample_logs):
            audit_sql = """
                INSERT INTO audit_logs (
                    log_id, user_id, action, resource,
                    details, ip_address, user_agent, created_at
                ) VALUES (
                    gen_random_uuid(),
                    :user_id,
                    :action,
                    :resource,
                    :details,
                    '192.168.1.100',
                    'Mozilla/5.0 (Demo Browser)',
                    NOW() - INTERVAL ':hours hours'
                )
            """
            await conn.execute(text(audit_sql), {
                "user_id": user_id,
                "action": log["action"],
                "resource": log["resource"],
                "details": json.dumps(log["details"]),
                "hours": i * 2
            })
        
        logger.info("✅ Sample audit logs created")

async def create_sample_service_configs():
    """サンプルサービス設定の作成"""
    logger.info("Creating sample service configurations...")
    
    engine = get_db_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT user_id FROM users WHERE email = 'demo@shodo.local'"))
        user_row = result.first()
        if not user_row:
            return
        
        user_id = user_row[0]
        
        configs_sql = """
            INSERT INTO user_service_configs (
                config_id, user_id, service_id, config_data,
                is_active, created_at, updated_at
            ) VALUES
            (
                gen_random_uuid(),
                :user_id,
                'shopify-default',
                '{"store_url": "demo-store.myshopify.com", "api_key": "demo_key", "webhook_url": "https://demo.shodo.local/webhooks/shopify"}',
                true,
                NOW(),
                NOW()
            ),
            (
                gen_random_uuid(),
                :user_id,
                'stripe-default',
                '{"publishable_key": "pk_test_demo", "webhook_endpoint": "https://demo.shodo.local/webhooks/stripe", "currency": "jpy"}',
                true,
                NOW(),
                NOW()
            ),
            (
                gen_random_uuid(),
                :user_id,
                'gmail-default',
                '{"email": "demo@gmail.com", "scopes": ["gmail.readonly", "gmail.send"], "auto_reply": false}',
                true,
                NOW(),
                NOW()
            )
            ON CONFLICT (user_id, service_id) DO NOTHING
        """
        await conn.execute(text(configs_sql), {"user_id": user_id})
        logger.info("✅ Sample service configurations created")

async def create_sample_metrics():
    """サンプルメトリクスの作成"""
    logger.info("Creating sample metrics...")
    
    engine = get_db_engine()
    async with engine.begin() as conn:
        # 過去7日間のサンプルメトリクス
        for i in range(7):
            date_offset = i
            metrics_sql = """
                INSERT INTO daily_metrics (
                    metric_id, date, total_requests, successful_requests,
                    error_requests, avg_response_time_ms, unique_users,
                    nlp_analyses, service_calls, created_at
                ) VALUES (
                    gen_random_uuid(),
                    CURRENT_DATE - INTERVAL ':days days',
                    :total_requests,
                    :successful_requests,
                    :error_requests,
                    :avg_response_time,
                    :unique_users,
                    :nlp_analyses,
                    :service_calls,
                    NOW()
                ) ON CONFLICT (date) DO NOTHING
            """
            await conn.execute(text(metrics_sql), {
                "days": date_offset,
                "total_requests": 1000 + i * 100,
                "successful_requests": 950 + i * 95,
                "error_requests": 50 + i * 5,
                "avg_response_time": 200 + i * 10,
                "unique_users": 50 + i * 5,
                "nlp_analyses": 300 + i * 30,
                "service_calls": 500 + i * 50
            })
        
        logger.info("✅ Sample metrics created")

async def main():
    """メイン処理"""
    logger.info("🌱 Starting sample data seeding...")
    
    try:
        await create_sample_users()
        await create_sample_sessions()
        await create_sample_nlp_history()
        await create_sample_audit_logs()
        await create_sample_service_configs()
        await create_sample_metrics()
        
        logger.info("🎉 Sample data seeding completed successfully!")
        
        # データ確認
        engine = get_db_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            
            result = await conn.execute(text("SELECT COUNT(*) FROM nlp_analysis_history"))
            analysis_count = result.scalar()
            
            result = await conn.execute(text("SELECT COUNT(*) FROM audit_logs"))
            audit_count = result.scalar()
            
            logger.info(f"📊 Data summary: Users: {user_count}, Analyses: {analysis_count}, Audit logs: {audit_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Sample data seeding failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)