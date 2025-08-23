"""
CSRF対策ミドルウェア（Double Submit Cookie パターン）
- 状態変更メソッド(POST/PUT/PATCH/DELETE)で、CookieのCSRFトークンとヘッダ一致を検証
- 環境変数で有効/無効、Cookie属性、ヘッダ名を設定可能
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from ..core.config import settings

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not settings.csrf_enabled:
            return await call_next(request)
        
        # 安全なメソッドは検証不要
        if request.method.upper() in SAFE_METHODS:
            return await call_next(request)
        
        # 認証不要な公開エンドポイントは除外（必要に応じて拡張）
        public_paths = {"/health", "/api/v1/auth/login", "/api/v1/auth/register"}
        if request.url.path in public_paths:
            return await call_next(request)
        
        csrf_cookie_name = settings.csrf_cookie_name
        csrf_header_name = settings.csrf_header_name
        
        cookie_token = request.cookies.get(csrf_cookie_name)
        header_token = request.headers.get(csrf_header_name)
        
        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "CSRF token missing or invalid",
                    "code": "CSRF_FAILED"
                }
            )
        
        return await call_next(request)

__all__ = ["CSRFMiddleware"]