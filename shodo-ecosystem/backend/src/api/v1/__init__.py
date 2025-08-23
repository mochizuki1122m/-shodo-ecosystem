"""
API v1 ルーター
"""

import os
from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# 軽量テスト時は重い依存を避ける
if os.getenv("LIGHT_TESTS") != "1":
    from src.api.v1.auth import router as auth_router
    from src.api.v1.nlp import router as nlp_router
    from src.api.v1.preview import router as preview_router
    from src.api.v1.health import router as health_router

    api_router.include_router(health_router, tags=["health"])
    api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
    api_router.include_router(nlp_router, prefix="/nlp", tags=["nlp"])
    api_router.include_router(preview_router, prefix="/preview", tags=["preview"])

__all__ = ["api_router"]