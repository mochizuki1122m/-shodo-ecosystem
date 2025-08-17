"""
APIキー関連のバックグラウンドタスク
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from celery import Task
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .celery_app import celery_app
from ..models.base import AsyncSessionLocal
from ..models.api_key import APIKey, APIKeyStatus, ServiceType
from ..models.user import UserSession
from ..models.service_connection import ServiceConnection
from ..services.auth.api_key_manager_db import DatabaseAPIKeyManager

logger = logging.getLogger(__name__)

class AsyncTask(Task):
    """非同期タスクの基底クラス"""
    
    def run_async(self, coro):
        """非同期コルーチンを実行"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 既存のループがある場合は新しいタスクとして実行
            return asyncio.create_task(coro)
        else:
            # 新しいループで実行
            return asyncio.run(coro)

@celery_app.task(
    base=AsyncTask,
    bind=True,
    name='src.tasks.api_key_tasks.refresh_expiring_keys',
    max_retries=3,
    default_retry_delay=60
)
def refresh_expiring_keys(self):
    """
    期限切れ間近のAPIキーを自動更新
    
    Returns:
        更新結果のサマリー
    """
    async def _refresh_keys():
        async with AsyncSessionLocal() as db:
            manager = DatabaseAPIKeyManager(db)
            
            # 24時間以内に期限切れになるキーを取得
            expiry_threshold = datetime.utcnow() + timedelta(hours=24)
            
            result = await db.execute(
                select(APIKey).where(
                    and_(
                        APIKey.status == APIKeyStatus.ACTIVE,
                        APIKey.auto_renew == True,
                        APIKey.expires_at != None,
                        APIKey.expires_at <= expiry_threshold
                    )
                )
            )
            expiring_keys = result.scalars().all()
            
            results = {
                'total': len(expiring_keys),
                'refreshed': 0,
                'failed': 0,
                'errors': []
            }
            
            for api_key in expiring_keys:
                try:
                    # キーをリフレッシュ
                    await manager.refresh_key(api_key.key_id)
                    results['refreshed'] += 1
                    
                    logger.info(f"Refreshed API key: {api_key.key_id}")
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'key_id': api_key.key_id,
                        'error': str(e)
                    })
                    
                    logger.error(f"Failed to refresh key {api_key.key_id}: {e}")
                    
                    # エラーが多い場合はリトライ
                    if results['failed'] >= 5:
                        raise self.retry(exc=e)
            
            await db.commit()
            return results
    
    return self.run_async(_refresh_keys())

@celery_app.task(
    base=AsyncTask,
    bind=True,
    name='src.tasks.api_key_tasks.cleanup_expired_sessions',
    max_retries=3
)
def cleanup_expired_sessions(self):
    """
    期限切れセッションをクリーンアップ
    
    Returns:
        削除されたセッション数
    """
    async def _cleanup_sessions():
        async with AsyncSessionLocal() as db:
            # 期限切れセッションを取得
            result = await db.execute(
                select(UserSession).where(
                    UserSession.expires_at < datetime.utcnow()
                )
            )
            expired_sessions = result.scalars().all()
            
            deleted_count = len(expired_sessions)
            
            # セッションを削除
            for session in expired_sessions:
                await db.delete(session)
            
            await db.commit()
            
            logger.info(f"Cleaned up {deleted_count} expired sessions")
            return {'deleted_sessions': deleted_count}
    
    return self.run_async(_cleanup_sessions())

@celery_app.task(
    base=AsyncTask,
    bind=True,
    name='src.tasks.api_key_tasks.generate_usage_report',
    max_retries=2
)
def generate_usage_report(self, report_type: str = 'daily', user_id: Optional[str] = None):
    """
    使用レポートを生成
    
    Args:
        report_type: レポートタイプ（daily, weekly, monthly）
        user_id: 特定ユーザーのレポート（オプション）
    
    Returns:
        レポートデータ
    """
    async def _generate_report():
        async with AsyncSessionLocal() as db:
            manager = DatabaseAPIKeyManager(db)
            
            # 期間を計算
            end_date = datetime.utcnow()
            if report_type == 'daily':
                start_date = end_date - timedelta(days=1)
            elif report_type == 'weekly':
                start_date = end_date - timedelta(weeks=1)
            elif report_type == 'monthly':
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=1)
            
            # レポートデータを収集
            report = {
                'type': report_type,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'generated_at': datetime.utcnow().isoformat(),
                'data': {}
            }
            
            if user_id:
                # 特定ユーザーのレポート
                stats = await manager.get_usage_statistics(
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date
                )
                report['data'] = {user_id: stats}
            else:
                # 全ユーザーのサマリー
                from ..models.user import User
                
                result = await db.execute(select(User).where(User.is_active == True))
                users = result.scalars().all()
                
                total_stats = {
                    'total_users': len(users),
                    'total_requests': 0,
                    'total_errors': 0,
                    'services': {}
                }
                
                for user in users[:100]:  # 最初の100ユーザーのみ（パフォーマンスのため）
                    try:
                        stats = await manager.get_usage_statistics(
                            user_id=user.id,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        total_stats['total_requests'] += stats['total_requests']
                        total_stats['total_errors'] += stats['failed_requests']
                        
                    except Exception as e:
                        logger.error(f"Failed to get stats for user {user.id}: {e}")
                
                report['data'] = total_stats
            
            # レポートを保存（実際の実装では、S3やメール送信など）
            logger.info(f"Generated {report_type} report: {report}")
            
            return report
    
    return self.run_async(_generate_report())

@celery_app.task(
    base=AsyncTask,
    bind=True,
    name='src.tasks.api_key_tasks.sync_service_connections',
    max_retries=3
)
def sync_service_connections(self):
    """
    サービス接続を同期
    
    Returns:
        同期結果のサマリー
    """
    async def _sync_connections():
        async with AsyncSessionLocal() as db:
            # 同期が必要な接続を取得
            result = await db.execute(
                select(ServiceConnection).where(
                    and_(
                        ServiceConnection.sync_enabled == True,
                        ServiceConnection.connection_status == "active"
                    )
                )
            )
            connections = result.scalars().all()
            
            results = {
                'total': len(connections),
                'synced': 0,
                'failed': 0,
                'errors': []
            }
            
            for connection in connections:
                if not connection.needs_sync():
                    continue
                
                try:
                    # サービス別の同期処理
                    if connection.service_type == "shopify":
                        await _sync_shopify(connection)
                    elif connection.service_type == "stripe":
                        await _sync_stripe(connection)
                    # 他のサービスも同様に実装
                    
                    connection.record_sync()
                    results['synced'] += 1
                    
                    logger.info(f"Synced connection: {connection.id}")
                    
                except Exception as e:
                    connection.record_error(str(e))
                    results['failed'] += 1
                    results['errors'].append({
                        'connection_id': connection.id,
                        'service': connection.service_type,
                        'error': str(e)
                    })
                    
                    logger.error(f"Failed to sync connection {connection.id}: {e}")
            
            await db.commit()
            return results
    
    return self.run_async(_sync_connections())

async def _sync_shopify(connection: ServiceConnection):
    """Shopifyデータを同期"""
    # TODO: Shopify APIを使用してデータを同期
    pass

async def _sync_stripe(connection: ServiceConnection):
    """Stripeデータを同期"""
    # TODO: Stripe APIを使用してデータを同期
    pass

@celery_app.task(
    name='src.tasks.api_key_tasks.rotate_api_key',
    max_retries=2
)
def rotate_api_key(key_id: str, user_id: str):
    """
    APIキーをローテーション（手動実行用）
    
    Args:
        key_id: キーID
        user_id: ユーザーID
    
    Returns:
        新しいキーID
    """
    async def _rotate_key():
        async with AsyncSessionLocal() as db:
            manager = DatabaseAPIKeyManager(db)
            
            # 既存のキーを無効化
            await manager.revoke_key_by_id(key_id, user_id, "rotation")
            
            # 新しいキーを生成（サービスによって異なる処理）
            # TODO: 実装
            
            logger.info(f"Rotated API key: {key_id}")
            return {'old_key_id': key_id, 'status': 'rotated'}
    
    return asyncio.run(_rotate_key())

@celery_app.task(
    name='src.tasks.api_key_tasks.check_api_health',
    max_retries=1
)
def check_api_health(service: str):
    """
    外部APIの健全性をチェック
    
    Args:
        service: サービス名
    
    Returns:
        ヘルスチェック結果
    """
    async def _check_health():
        import httpx
        
        health_endpoints = {
            'shopify': 'https://status.shopify.com/api/v2/status.json',
            'stripe': 'https://status.stripe.com/api/v2/status.json',
            'github': 'https://www.githubstatus.com/api/v2/status.json',
        }
        
        endpoint = health_endpoints.get(service)
        if not endpoint:
            return {'service': service, 'status': 'unknown', 'message': 'No health endpoint configured'}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, timeout=10.0)
                response.raise_for_status()
                
                data = response.json()
                
                return {
                    'service': service,
                    'status': data.get('status', {}).get('indicator', 'unknown'),
                    'description': data.get('status', {}).get('description', ''),
                    'checked_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Health check failed for {service}: {e}")
            return {
                'service': service,
                'status': 'error',
                'message': str(e),
                'checked_at': datetime.utcnow().isoformat()
            }
    
    return asyncio.run(_check_health())