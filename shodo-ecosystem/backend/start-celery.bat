@echo off
echo ========================================
echo Starting Celery Worker (Windows)
echo ========================================

REM 環境変数設定
set FORKED_BY_MULTIPROCESSING=1
set CELERY_BROKER_URL=redis://localhost:6379/0
set CELERY_RESULT_BACKEND=redis://localhost:6379/0

REM Celeryワーカー起動（Windows用threadプール）
celery -A src.tasks.celery_app worker --loglevel=info --pool=threads --concurrency=4

pause