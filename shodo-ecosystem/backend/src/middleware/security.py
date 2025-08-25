"""
セキュリティミドルウェア
"""

import time
import hashlib
from typing import Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)

class LegacyRateLimitMiddleware(BaseHTTPMiddleware):
    """[REMOVED] 旧レート制限ミドルウェア
    本ミドルウェアは統一実装 `middleware/rate_limit.py` に置き換えられました。
    誤用防止のため、初期化時に例外を送出します。
    """
    def __init__(self, app, *args, **kwargs):
        raise RuntimeError("LegacyRateLimitMiddleware is removed. Use RateLimitMiddleware instead.")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """セキュリティヘッダーミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        """セキュリティヘッダーを追加"""
        response = await call_next(request)
        
        # セキュリティヘッダー（最新推奨）
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        # X-XSS-Protection は現行ブラウザでは非推奨のため付与しない
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        connect_src = " ".join(settings.csp_connect_src)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            f"connect-src {connect_src}; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
        # Permissions-Policy（サンプル。必要に応じて有効化域を調整）
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), fullscreen=(self)"
        )
        
        return response

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """リクエスト検証ミドルウェア"""
    
    def __init__(self, app, max_content_length: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_content_length = max_content_length
    
    async def dispatch(self, request: Request, call_next):
        """リクエストの検証"""
        # Content-Lengthチェック
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > self.max_content_length:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large"}
            )
        
        # Content-Typeチェック（POSTリクエストの場合）
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("Content-Type", "")
            if not content_type:
                return JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={"detail": "Content-Type header is required"}
                )
        
        response = await call_next(request)
        return response

class APIKeyMiddleware(BaseHTTPMiddleware):
    """APIキー認証ミドルウェア（オプション）"""
    
    def __init__(self, app, api_keys: Optional[Dict[str, str]] = None):
        super().__init__(app)
        self.api_keys = api_keys or {}
    
    async def dispatch(self, request: Request, call_next):
        """APIキー検証"""
        # 公開エンドポイントは除外
        public_paths = ["/", "/health", "/docs", "/openapi.json", "/api/v1/auth/login", "/api/v1/auth/register"]
        if request.url.path in public_paths:
            return await call_next(request)
        
        # APIキーが設定されている場合のみチェック
        if self.api_keys:
            api_key = request.headers.get("X-API-Key")
            if not api_key or api_key not in self.api_keys.values():
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing API key"}
                )
        
        response = await call_next(request)
        return response

def setup_security_middleware(app, settings):
    """セキュリティミドルウェアのセットアップ（レート制限は統一ミドルウェアで実施）"""
    
    # レート制限は middleware/rate_limit.py の実装を使用（main側で追加済み）
    # LegacyRateLimitMiddleware は非推奨のため追加しないこと
    
    # セキュリティヘッダー
    app.add_middleware(SecurityHeadersMiddleware)
    
    # リクエスト検証
    app.add_middleware(
        RequestValidationMiddleware,
        max_content_length=10 * 1024 * 1024  # 10MB
    )
    
    # APIキー認証（必要に応じて有効化）
    # api_keys = {"service1": "key1", "service2": "key2"}
    # app.add_middleware(APIKeyMiddleware, api_keys=api_keys)
    
    logger.info("Security middleware configured (rate limit unified)")