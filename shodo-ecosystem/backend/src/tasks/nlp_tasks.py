"""
NLP非同期タスク
"""

from celery import Task
from ..tasks.celery_app import celery_app
from ..services.nlp.dual_path_engine import DualPathEngine
import asyncio

class NLPTask(Task):
    """NLPタスク基底クラス"""
    _engine = None
    
    @property
    def engine(self):
        if self._engine is None:
            self._engine = DualPathEngine({})
        return self._engine

@celery_app.task(base=NLPTask, bind=True)
def analyze_text_async(self, text: str, context: dict = None):
    """非同期テキスト解析"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            self.engine.analyze(text, context)
        )
        return {
            "intent": result.intent,
            "confidence": result.confidence,
            "entities": result.entities,
            "service": result.service,
            "processing_time_ms": result.processing_time_ms
        }
    finally:
        loop.close()

@celery_app.task
def batch_analyze(texts: list):
    """バッチ解析"""
    results = []
    for text in texts:
        result = analyze_text_async.delay(text)
        results.append(result.id)
    return results

@celery_app.task
def cleanup_old_analyses(days: int = 30):
    """古い解析結果のクリーンアップ"""
    # TODO: データベースから古いレコードを削除
    return {"cleaned": 0}