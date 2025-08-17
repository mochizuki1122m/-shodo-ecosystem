"""
Celeryアプリケーション設定
"""

import os
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue

# Redis URL
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Celeryアプリケーションの作成
celery_app = Celery(
    'shodo_ecosystem',
    broker=f"{REDIS_URL}/0",
    backend=f"{REDIS_URL}/1",
    include=[
        'src.tasks.api_key_tasks',
        'src.tasks.notification_tasks',
        'src.tasks.sync_tasks',
    ]
)

# Celery設定
celery_app.conf.update(
    # タスク設定
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # 結果の有効期限（24時間）
    result_expires=86400,
    
    # タスクの実行時間制限
    task_soft_time_limit=300,  # 5分
    task_time_limit=600,  # 10分
    
    # ワーカー設定
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # エラーハンドリング
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # キュー設定
    task_default_queue='default',
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('critical', Exchange('critical'), routing_key='critical'),
        Queue('periodic', Exchange('periodic'), routing_key='periodic'),
        Queue('reports', Exchange('reports'), routing_key='reports'),
    ),
    
    # ルーティング
    task_routes={
        'src.tasks.api_key_tasks.refresh_expiring_keys': {'queue': 'critical'},
        'src.tasks.api_key_tasks.cleanup_expired_sessions': {'queue': 'periodic'},
        'src.tasks.api_key_tasks.generate_usage_report': {'queue': 'reports'},
        'src.tasks.sync_tasks.*': {'queue': 'periodic'},
    },
    
    # 定期タスク（Celery Beat）
    beat_schedule={
        # APIキーの自動更新（1時間ごと）
        'refresh-expiring-keys': {
            'task': 'src.tasks.api_key_tasks.refresh_expiring_keys',
            'schedule': crontab(minute=0),  # 毎時0分
            'options': {
                'queue': 'critical',
                'priority': 9,
            }
        },
        
        # 期限切れセッションのクリーンアップ（6時間ごと）
        'cleanup-expired-sessions': {
            'task': 'src.tasks.api_key_tasks.cleanup_expired_sessions',
            'schedule': crontab(minute=0, hour='*/6'),
            'options': {
                'queue': 'periodic',
                'priority': 5,
            }
        },
        
        # 使用レポート生成（毎日午前2時）
        'generate-daily-report': {
            'task': 'src.tasks.api_key_tasks.generate_usage_report',
            'schedule': crontab(minute=0, hour=2),
            'kwargs': {'report_type': 'daily'},
            'options': {
                'queue': 'reports',
                'priority': 3,
            }
        },
        
        # 週次レポート（毎週月曜日午前3時）
        'generate-weekly-report': {
            'task': 'src.tasks.api_key_tasks.generate_usage_report',
            'schedule': crontab(minute=0, hour=3, day_of_week=1),
            'kwargs': {'report_type': 'weekly'},
            'options': {
                'queue': 'reports',
                'priority': 3,
            }
        },
        
        # サービス接続の同期（30分ごと）
        'sync-service-connections': {
            'task': 'src.tasks.api_key_tasks.sync_service_connections',
            'schedule': crontab(minute='*/30'),
            'options': {
                'queue': 'periodic',
                'priority': 6,
            }
        },
    },
    
    # Beat設定
    beat_scheduler='celery.beat:PersistentScheduler',
    beat_schedule_filename='celerybeat-schedule.db',
)

# タスクの自動検出
celery_app.autodiscover_tasks()