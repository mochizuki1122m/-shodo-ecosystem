"""
JTI Revocation Store
- Access トークンの JTI を無効化（ブラックリスト）するためのストア
- 本番では Redis、開発ではメモリフォールバック
"""

from __future__ import annotations

import time
from typing import Optional

from ...services.database import get_redis
from ...core.config import settings


class JTIRevocationStore:
    """JTI 失効ストア（Redis優先、メモリフォールバック）"""

    def __init__(self) -> None:
        self.redis = get_redis()
        # メモリフォールバック: jti -> expiry_epoch_seconds
        self._memory_revoked: dict[str, float] = {}

    def _key(self, jti: str) -> str:
        return f"auth:revoked_jti:{jti}"

    def _now(self) -> float:
        return time.time()

    def _cleanup_memory(self) -> None:
        now = self._now()
        expired = [j for j, exp in self._memory_revoked.items() if exp <= now]
        for j in expired:
            self._memory_revoked.pop(j, None)

    async def revoke_jti(self, jti: Optional[str], *, exp_epoch: Optional[int] = None, ttl_seconds: Optional[int] = None) -> bool:
        """
        指定 JTI を失効登録する。

        Args:
            jti: トークンの JTI
            exp_epoch: トークン有効期限（Epoch秒）。指定時は TTL として使用
            ttl_seconds: 明示 TTL（秒）。exp_epoch より優先
        """
        if not jti:
            return False

        ttl: int = 0
        now = int(self._now())
        if ttl_seconds is not None and ttl_seconds > 0:
            ttl = int(ttl_seconds)
        elif exp_epoch is not None and exp_epoch > now:
            ttl = int(exp_epoch - now)
        else:
            # デフォルト 1 時間
            ttl = 3600

        if self.redis:
            try:
                # 値は簡易（監査は別途）
                await self.redis.setex(self._key(jti), ttl, "revoked")
                return True
            except Exception:
                # フォールバックに切り替え
                pass

        # メモリフォールバック（開発のみ想定）
        if settings.is_production():
            # 本番で Redis 不在時は失敗とする
            return False
        self._memory_revoked[jti] = now + ttl
        self._cleanup_memory()
        return True

    async def is_revoked(self, jti: Optional[str]) -> bool:
        """JTI が失効登録済みかを確認する。"""
        if not jti:
            return False

        if self.redis:
            try:
                exists = await self.redis.exists(self._key(jti))
                # redis-py returns int count
                return bool(exists)
            except Exception:
                # fall back to memory
                pass

        # メモリフォールバック
        self._cleanup_memory()
        return jti in self._memory_revoked


__all__ = ["JTIRevocationStore"]

