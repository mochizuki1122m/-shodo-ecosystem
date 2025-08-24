"""
レート制限ミドルウェア - 単一実装（Single Point of Enforcement）
全エンドポイントのレート制限を一元管理
"""

import time
import hashlib
from typing import Dict, Optional, Tuple
from collections import defaultdict
import asyncio
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

from ..core.config import settings
from ..services.database import get_redis
from ..monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)

class RateLimitConfig:
    """エンドポイント別レート制限設定（settingsに一元化）"""
    
    @classmethod
    def get_limits(cls, path: str) -> Dict[str, int]:
        """パスに対するレート制限設定を取得"""
        endpoint_limits = settings.rate_limit_endpoint_limits or {}
        
        # 完全一致を優先
        if path in endpoint_limits:
            return endpoint_limits[path]
        
        # プレフィックスマッチ
        for endpoint, limits in endpoint_limits.items():
            if path.startswith(endpoint.rstrip("/")):
                return limits
        
        # デフォルト
        return {
            "per_minute": settings.rate_limit_per_minute,
            "per_hour": settings.rate_limit_per_hour,
            "burst": settings.rate_limit_burst,
        }

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
            "burst_tokens": settings.rate_limit_burst,
            "burst_reset": time.time()
        })
        
        # Redisクライアント（lazy初期化）
        self.redis = None
        self._redis_checked = False
    
    def _get_client_id(self, request: Request) -> str:
        """クライアント識別子を生成"""
        # 優先順位: LPR JTI > 認証ユーザーID > X-Forwarded-For+UA
        try:
            lpr_jti = getattr(request.state, "lpr_jti", None)
            if lpr_jti:
                return f"lpr:{lpr_jti}"
        except Exception:
            pass

        # 認証ユーザーがいれば使用
        if hasattr(request.state, "user") and request.state.user:
            try:
                uid = getattr(request.state.user, "user_id", None) or request.state.user.get("sub")
                if uid:
                    return f"user:{uid}"
            except Exception:
                return f"user:{request.state.user}"
        
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
    
    async def _ensure_redis_connection(self) -> bool:
        """Redis接続を確保（lazy initialization）"""
        if not self.use_redis:
            # 本番環境ではRedis必須
            from ..core.config import settings as _settings
            if _settings.is_production():
                return False
            return False
            
        if self.redis is None and not self._redis_checked:
            try:
                self.redis = get_redis()
                self._redis_checked = True
                if self.redis:
                    logger.info("Redis connection established for rate limiting")
                    return True
            except Exception as e:
                logger.warning(f"Redis not available for rate limiting: {e}")
                self._redis_checked = True
                # 本番環境ではフォールバック可否は設定で決定
                from ..core.config import settings as _settings2
                if _settings2.is_production() and not settings.rate_limit_fail_open:
                    self.use_redis = True  # 強制
                    return False
                self.use_redis = False
                return False
        
        # 定期的にRedis接続を再試行（60秒間隔）
        if self.redis is None and self._redis_checked:
            current_time = time.time()
            if not hasattr(self, '_last_redis_retry') or current_time - self._last_redis_retry > 60:
                self._last_redis_retry = current_time
                try:
                    self.redis = get_redis()
                    if self.redis:
                        logger.info("Redis connection re-established for rate limiting")
                        self.use_redis = True
                        return True
                except Exception as e:
                    logger.debug(f"Redis retry failed: {e}")
        
        return self.redis is not None

    async def _check_redis_limit(
        self, 
        client_id: str, 
        path: str, 
        limits: Dict[str, int]
    ) -> Tuple[bool, Dict[str, int]]:
        """Redis使用時のレート制限チェック"""
        if not await self._ensure_redis_connection():
            # 本番環境での挙動：Fail-Openが有効ならメモリにフォールバック
            from ..core.config import settings as _settings
            if _settings.is_production() and not settings.rate_limit_fail_open:
                logger.error("Rate limit denied: Redis unavailable in production and fail_open is disabled")
                return False, {"retry_after": 60}
            logger.debug("Falling back to memory-based rate limiting")
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
            else:
                # 初期化
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
            # Redis接続をリセットして次回再試行
            self.redis = None
            self._redis_checked = False
            # フォールバック to メモリ
            logger.info("Falling back to memory-based rate limiting due to Redis error")
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
        
        # Redis使用可能性を毎回チェック（接続復旧対応）
        if await self._ensure_redis_connection():
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
            try:
                client_type = "lpr" if getattr(request.state, "lpr_jti", None) else "ip"
                MetricsCollector.record_rate_limit_hit(endpoint=request.url.path, client_type=client_type)
            except Exception:
                pass
            
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
            
            # Degradedモードのヒント
            if settings.rate_limit_fail_open and settings.rate_limit_degraded_mode_headers:
                response.headers["X-RateLimit-Mode"] = "degraded"
        
        return response

# エクスポート
__all__ = ['RateLimitMiddleware', 'RateLimitConfig', 'RateLimiter']