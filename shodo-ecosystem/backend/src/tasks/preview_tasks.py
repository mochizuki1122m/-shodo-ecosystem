"""
プレビュー関連の非同期タスク
"""

from celery import Task
from ..tasks.celery_app import celery_app
import asyncio
from typing import Dict, Any

class PreviewTask(Task):
    """プレビュータスク基底クラス"""
    _engine = None
    
    @property
    def engine(self):
        if self._engine is None:
            from ..services.preview.sandbox_engine import SandboxPreviewEngine
            self._engine = SandboxPreviewEngine()
        return self._engine

@celery_app.task(base=PreviewTask, bind=True)
def generate_preview_async(
    self,
    source_type: str,
    source_id: str,
    modifications: list,
    user_id: str = None
) -> Dict[str, Any]:
    """非同期プレビュー生成"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            self.engine.generate_preview(
                source_type=source_type,
                source_id=source_id,
                modifications=modifications,
                user_id=user_id
            )
        )
        
        return {
            "preview_id": result.id,
            "visual": result.visual,
            "diff": result.diff,
            "confidence_score": result.confidence_score
        }
    finally:
        loop.close()

@celery_app.task(base=PreviewTask, bind=True)
def apply_changes_async(
    self,
    preview_id: str,
    user_id: str = None
) -> Dict[str, Any]:
    """非同期変更適用"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            self.engine.apply_preview(preview_id, user_id)
        )
        
        return {
            "success": result.get("success", False),
            "applied_changes": result.get("applied_changes", 0),
            "rollback_token": result.get("rollback_token")
        }
    finally:
        loop.close()

@celery_app.task
def cleanup_old_previews(days: int = 7) -> Dict[str, int]:
    """古いプレビューのクリーンアップ"""
    # TODO: データベースから古いプレビューを削除
    return {"cleaned": 0}

@celery_app.task
def generate_preview_report(user_id: str) -> Dict[str, Any]:
    """プレビュー使用状況レポート生成"""
    # TODO: ユーザーのプレビュー使用状況を集計
    return {
        "user_id": user_id,
        "total_previews": 0,
        "applied_previews": 0,
        "success_rate": 0.0
    }