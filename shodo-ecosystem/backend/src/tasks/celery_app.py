"""
Celeryタスクキュー設定（Windows対応）
"""

from celery import Celery
import os

# Windows環境用の設定
os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

# Celeryアプリケーション
celery_app = Celery(
    "shodo_ecosystem",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["src.tasks.nlp_tasks", "src.tasks.preview_tasks"]
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    # Windows対応
    worker_pool='threads' if os.name == 'nt' else 'prefork',
)

# キュー設定
celery_app.conf.task_routes = {
    "src.tasks.nlp_tasks.*": {"queue": "nlp"},
    "src.tasks.preview_tasks.*": {"queue": "preview"},
    "src.tasks.sync_tasks.*": {"queue": "sync"},
}