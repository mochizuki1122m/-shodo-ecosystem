"""
API v1 ルーター
"""

from fastapi import APIRouter

from .auth import router as auth_router
from .nlp import router as nlp_router
from .preview import router as preview_router
from .health import router as health_router

# APIルーターの作成
api_router = APIRouter(prefix="/api/v1")

# 各ルーターの登録
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(nlp_router, prefix="/nlp", tags=["nlp"])
api_router.include_router(preview_router, prefix="/preview", tags=["preview"])

__all__ = ["api_router"]