"""
セキュリティミドルウェア
"""

import time
import hashlib
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """レート制限ミドルウェア"""
    
    def __init__(self, app, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.request_counts: Dict[str, Dict] = {}
    
    def get_client_id(self, request: Request) -> str:
        """クライアント識別子を取得"""
        # IPアドレスとユーザーエージェントの組み合わせ
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        user_agent = request.headers.get("User-Agent", "unknown")
        client_id = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()
        return client_id
    
    def is_rate_limited(self, client_id: str) -> bool:
        """レート制限チェック"""
        current_time = time.time()
        
        if client_id not in self.request_counts:
            self.request_counts[client_id] = {
                "minute_count": 0,
                "minute_reset": current_time + 60,
                "hour_count": 0,
                "hour_reset": current_time + 3600
            }
        
        client_data = self.request_counts[client_id]
        
        # 分単位のリセット
        if current_time > client_data["minute_reset"]:
            client_data["minute_count"] = 0
            client_data["minute_reset"] = current_time + 60
        
        # 時間単位のリセット
        if current_time > client_data["hour_reset"]:
            client_data["hour_count"] = 0
            client_data["hour_reset"] = current_time + 3600
        
        # レート制限チェック
        if client_data["minute_count"] >= self.requests_per_minute:
            return True
        if client_data["hour_count"] >= self.requests_per_hour:
            return True
        
        # カウントを増やす
        client_data["minute_count"] += 1
        client_data["hour_count"] += 1
        
        return False
    
    async def dispatch(self, request: Request, call_next):
        """リクエスト処理"""
        # ヘルスチェックは除外
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        client_id = self.get_client_id(request)
        
        if self.is_rate_limited(client_id):
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
        
        response = await call_next(request)
        
        # レート制限情報をヘッダーに追加
        client_data = self.request_counts.get(client_id, {})
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, self.requests_per_minute - client_data.get("minute_count", 0))
        )
        
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """セキュリティヘッダーミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        """セキュリティヘッダーを追加"""
        response = await call_next(request)
        
        # セキュリティヘッダー
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' http://localhost:* ws://localhost:*"
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
    """セキュリティミドルウェアのセットアップ"""
    
    # レート制限
    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.rate_limit_per_minute,
            requests_per_hour=settings.rate_limit_per_hour
        )
    
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
    
    logger.info("Security middleware configured")