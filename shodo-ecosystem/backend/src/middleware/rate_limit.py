"""
レート制限ミドルウェア - 単一実装（Single Point of Enforcement）
全エンドポイントのレート制限を一元管理
"""

import time
import hashlib
from typing import Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

from ..core.config import settings
from ..services.database import get_redis

logger = logging.getLogger(__name__)

class RateLimitConfig:
    """エンドポイント別レート制限設定"""
    
    # デフォルト設定
    DEFAULT_LIMITS = {
        "per_minute": 60,
        "per_hour": 1000,
        "burst": 10
    }
    
    # エンドポイント別カスタム設定
    ENDPOINT_LIMITS = {
        # 認証エンドポイントは厳しく制限
        "/api/v1/auth/login": {"per_minute": 5, "per_hour": 20, "burst": 2},
        "/api/v1/auth/register": {"per_minute": 3, "per_hour": 10, "burst": 1},
        
        # LPR発行も制限
        "/api/v1/lpr/issue": {"per_minute": 10, "per_hour": 100, "burst": 3},
        
        # AI関連は処理が重いので制限
        "/api/v1/nlp/analyze": {"per_minute": 30, "per_hour": 500, "burst": 5},
        "/api/v1/preview/generate": {"per_minute": 20, "per_hour": 300, "burst": 3},
        
        # ヘルスチェックは制限なし
        "/health": {"per_minute": 9999, "per_hour": 99999, "burst": 999},
        "/metrics": {"per_minute": 9999, "per_hour": 99999, "burst": 999},
    }
    
    @classmethod
    def get_limits(cls, path: str) -> Dict[str, int]:
        """パスに対するレート制限設定を取得"""
        # 完全一致を優先
        if path in cls.ENDPOINT_LIMITS:
            return cls.ENDPOINT_LIMITS[path]
        
        # プレフィックスマッチ
        for endpoint, limits in cls.ENDPOINT_LIMITS.items():
            if path.startswith(endpoint.rstrip("/")):
                return limits
        
        # デフォルト
        return cls.DEFAULT_LIMITS

class RateLimiter:
    """レート制限実装クラス"""
    
    def __init__(self, use_redis: bool = True):
        """
        Args:
            use_redis: Redisを使用するか（False時はメモリ内管理）
        """
        self.use_redis = use_redis and settings.cache_enabled
        self.memory_store: Dict[str, Dict] = defaultdict(lambda: {
            "minute_count": 0,
            "minute_reset": time.time(),
            "hour_count": 0,
            "hour_reset": time.time(),
            "burst_tokens": 10,
            "burst_reset": time.time()
        })
        
        # Redisクライアント
        self.redis = None
        if self.use_redis:
            try:
                self.redis = get_redis()
            except Exception as e:
                logger.warning(f"Redis not available for rate limiting: {e}")
                self.use_redis = False
    
    def _get_client_id(self, request: Request) -> str:
        """クライアント識別子を生成"""
        # 優先順位: 認証ユーザーID > X-Forwarded-For > IPアドレス
        
        # 認証ユーザーがいれば使用
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.user_id}"
        
        # IPアドレスベース
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # User-Agentも考慮（同一IPからの異なるクライアント識別）
        user_agent = request.headers.get("User-Agent", "")
        client_str = f"{client_ip}:{user_agent[:50]}"
        
        # ハッシュ化して返す
        return hashlib.md5(client_str.encode()).hexdigest()[:16]
    
    async def _check_redis_limit(
        self, 
        client_id: str, 
        path: str, 
        limits: Dict[str, int]
    ) -> Tuple[bool, Dict[str, int]]:
        """Redis使用時のレート制限チェック"""
        if not self.redis:
            return await self._check_memory_limit(client_id, path, limits)
        
        try:
            now = time.time()
            
            # キー生成
            minute_key = f"rate:{client_id}:{path}:minute:{int(now // 60)}"
            hour_key = f"rate:{client_id}:{path}:hour:{int(now // 3600)}"
            burst_key = f"rate:{client_id}:{path}:burst"
            
            # パイプライン実行
            pipe = self.redis.pipeline()
            
            # 分単位カウント
            pipe.incr(minute_key)
            pipe.expire(minute_key, 60)
            
            # 時間単位カウント
            pipe.incr(hour_key)
            pipe.expire(hour_key, 3600)
            
            # バーストトークン（トークンバケット方式）
            pipe.get(burst_key)
            
            results = await pipe.execute() if asyncio.iscoroutinefunction(pipe.execute) else pipe.execute()
            
            minute_count = results[0]
            hour_count = results[2]
            burst_tokens = int(results[4] or limits["burst"])
            
            # バーストトークン補充（1秒に1トークン）
            last_refill = await self.redis.get(f"{burst_key}:time") if asyncio.iscoroutinefunction(self.redis.get) else self.redis.get(f"{burst_key}:time")
            if last_refill:
                elapsed = now - float(last_refill)
                tokens_to_add = int(elapsed)
                if tokens_to_add > 0:
                    burst_tokens = min(limits["burst"], burst_tokens + tokens_to_add)
                    if asyncio.iscoroutinefunction(self.redis.setex):
                        await self.redis.setex(burst_key, 60, burst_tokens)
                        await self.redis.setex(f"{burst_key}:time", 60, now)
                    else:
                        self.redis.setex(burst_key, 60, burst_tokens)
                        self.redis.setex(f"{burst_key}:time", 60, now)
            
            # 制限チェック
            if minute_count > limits["per_minute"]:
                return False, {"retry_after": 60 - (int(now) % 60)}
            
            if hour_count > limits["per_hour"]:
                return False, {"retry_after": 3600 - (int(now) % 3600)}
            
            if burst_tokens <= 0:
                return False, {"retry_after": 1}
            
            # バーストトークン消費
            if asyncio.iscoroutinefunction(self.redis.decr):
                await self.redis.decr(burst_key)
            else:
                self.redis.decr(burst_key)
            
            return True, {
                "minute_remaining": limits["per_minute"] - minute_count,
                "hour_remaining": limits["per_hour"] - hour_count,
                "burst_remaining": burst_tokens - 1
            }
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # フォールバック to メモリ
            return await self._check_memory_limit(client_id, path, limits)
    
    async def _check_memory_limit(
        self, 
        client_id: str, 
        path: str, 
        limits: Dict[str, int]
    ) -> Tuple[bool, Dict[str, int]]:
        """メモリ使用時のレート制限チェック"""
        now = time.time()
        key = f"{client_id}:{path}"
        state = self.memory_store[key]
        
        # 分単位リセット
        if now - state["minute_reset"] > 60:
            state["minute_count"] = 0
            state["minute_reset"] = now
        
        # 時間単位リセット
        if now - state["hour_reset"] > 3600:
            state["hour_count"] = 0
            state["hour_reset"] = now
        
        # バーストトークン補充
        if now - state["burst_reset"] > 1:
            tokens_to_add = int(now - state["burst_reset"])
            state["burst_tokens"] = min(limits["burst"], state["burst_tokens"] + tokens_to_add)
            state["burst_reset"] = now
        
        # 制限チェック
        if state["minute_count"] >= limits["per_minute"]:
            return False, {"retry_after": 60 - (int(now) % 60)}
        
        if state["hour_count"] >= limits["per_hour"]:
            return False, {"retry_after": 3600 - (int(now) % 3600)}
        
        if state["burst_tokens"] <= 0:
            return False, {"retry_after": 1}
        
        # カウント更新
        state["minute_count"] += 1
        state["hour_count"] += 1
        state["burst_tokens"] -= 1
        
        return True, {
            "minute_remaining": limits["per_minute"] - state["minute_count"],
            "hour_remaining": limits["per_hour"] - state["hour_count"],
            "burst_remaining": state["burst_tokens"]
        }
    
    async def check_rate_limit(
        self, 
        request: Request
    ) -> Tuple[bool, Optional[Dict[str, int]]]:
        """
        レート制限チェック
        
        Returns:
            (allowed, rate_info): 許可フラグと制限情報
        """
        if not settings.rate_limit_enabled:
            return True, None
        
        client_id = self._get_client_id(request)
        path = request.url.path
        limits = RateLimitConfig.get_limits(path)
        
        if self.use_redis:
            return await self._check_redis_limit(client_id, path, limits)
        else:
            return await self._check_memory_limit(client_id, path, limits)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """レート制限ミドルウェア"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.limiter = RateLimiter(use_redis=True)
    
    async def dispatch(self, request: Request, call_next):
        """リクエスト処理"""
        
        # レート制限チェック
        allowed, rate_info = await self.limiter.check_rate_limit(request)
        
        if not allowed:
            # 制限超過
            retry_after = rate_info.get("retry_after", 60)
            
            logger.warning(
                f"Rate limit exceeded for {request.client.host} on {request.url.path}"
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(RateLimitConfig.get_limits(request.url.path)["per_minute"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after)
                }
            )
        
        # レート情報をヘッダーに追加
        response = await call_next(request)
        
        if rate_info:
            response.headers["X-RateLimit-Limit-Minute"] = str(
                RateLimitConfig.get_limits(request.url.path)["per_minute"]
            )
            response.headers["X-RateLimit-Remaining-Minute"] = str(
                rate_info.get("minute_remaining", 0)
            )
            response.headers["X-RateLimit-Limit-Hour"] = str(
                RateLimitConfig.get_limits(request.url.path)["per_hour"]
            )
            response.headers["X-RateLimit-Remaining-Hour"] = str(
                rate_info.get("hour_remaining", 0)
            )
            response.headers["X-RateLimit-Burst-Remaining"] = str(
                rate_info.get("burst_remaining", 0)
            )
        
        return response

# エクスポート
__all__ = ['RateLimitMiddleware', 'RateLimitConfig', 'RateLimiter']