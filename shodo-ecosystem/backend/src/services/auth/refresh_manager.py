"""
リフレッシュトークン管理
Redisに保存し、ローテーションと失効を提供
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import secrets
import json

from ...core.config import settings
from ...services.database import get_redis
from ...core.security import SecureTokenGenerator


class RefreshTokenManager:
    """Refresh Token storage backed by Redis."""

    def __init__(self):
        self.redis = get_redis()
        self.ttl_seconds = int(settings.refresh_token_ttl_days) * 24 * 3600
        self.cookie_name = settings.refresh_cookie_name

    def _key(self, token: str) -> str:
        return f"auth:refresh:{token}"

    def _user_set_key(self, user_id: str) -> str:
        return f"auth:refresh_user:{user_id}"

    async def generate(
        self,
        user_id: str,
        username: str,
        roles: list[str],
        device_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Generate a refresh token and store payload in Redis."""
        if not self.redis and settings.is_production():
            # 本番はRedis必須
            raise RuntimeError("Redis unavailable for refresh token storage")

        token = SecureTokenGenerator.generate_token(48)
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "username": username,
            "roles": roles,
            "device_id": device_id,
            "session_id": session_id,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.ttl_seconds)).isoformat(),
            "version": 1,
        }

        if self.redis:
            await self.redis.setex(self._key(token), self.ttl_seconds, json.dumps(payload))
            await self.redis.sadd(self._user_set_key(user_id), token)
        return token

    async def validate(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate and return payload of refresh token."""
        if not token:
            return None
        if not self.redis:
            return None
        data = await self.redis.get(self._key(token))
        if not data:
            return None
        try:
            payload = json.loads(data)
            # Exp check (defense-in-depth)
            if payload.get("expires_at"):
                exp = datetime.fromisoformat(payload["expires_at"])
                if exp < datetime.now(timezone.utc):
                    return None
            return payload
        except Exception:
            return None

    async def rotate(self, token: str) -> Optional[tuple[str, Dict[str, Any]]]:
        """Rotate refresh token and return (new_token, payload)."""
        payload = await self.validate(token)
        if not payload:
            return None
        # Invalidate old token
        await self.revoke(token, payload.get("user_id"))
        # Issue new token with same principal
        new_token = await self.generate(
            user_id=payload["user_id"],
            username=payload.get("username") or f"user_{payload['user_id']}",
            roles=payload.get("roles") or ["user"],
            device_id=payload.get("device_id"),
            session_id=payload.get("session_id"),
        )
        new_payload = await self.validate(new_token)
        return new_token, new_payload or {}

    async def revoke(self, token: str, user_id: Optional[str] = None):
        if not self.redis:
            return
        await self.redis.delete(self._key(token))
        if user_id:
            await self.redis.srem(self._user_set_key(user_id), token)

    async def revoke_all_for_user(self, user_id: str) -> int:
        if not self.redis:
            return 0
        tokens = await self.redis.smembers(self._user_set_key(user_id))
        count = 0
        for t in tokens:
            await self.redis.delete(self._key(t))
            count += 1
        await self.redis.delete(self._user_set_key(user_id))
        return count

