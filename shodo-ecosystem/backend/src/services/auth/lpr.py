"""
LPR (Limited Proxy Rights) トークン管理サービス

このモジュールは、限定的な代理権限を持つトークンの発行、検証、失効を管理します。
セキュリティ原則：
- 最小権限の原則
- ゼロトラスト
- 多層防御
- 監査性
- データ最小化
"""

import json
import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
import logging

from jwcrypto import jwk, jws
from jwcrypto.common import json_encode
import aioredis
from pydantic import BaseModel, Field, validator
import structlog

from ...utils.config import settings

# 構造化ログの設定
logger = structlog.get_logger()

# 定数
LPR_VERSION = "1.0.0"
LPR_TTL_SECONDS = 3600  # デフォルト1時間
LPR_MAX_TTL_SECONDS = 86400  # 最大24時間
LPR_MIN_TTL_SECONDS = 300  # 最小5分
REVOCATION_CHECK_INTERVAL = 60  # 失効チェック間隔（秒）

class LPRScope(BaseModel):
    """LPRスコープ定義"""
    method: str = Field(..., regex="^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    url_pattern: str = Field(..., min_length=1)
    description: Optional[str] = None
    
    def matches(self, method: str, url: str) -> bool:
        """リクエストがスコープに一致するか確認"""
        import re
        
        if method.upper() != self.method.upper():
            return False
        
        # URLパターンをregexに変換（簡易版）
        pattern = self.url_pattern.replace("*", ".*")
        pattern = f"^{pattern}$"
        
        return bool(re.match(pattern, url))

class LPRPolicy(BaseModel):
    """LPRポリシー定義"""
    rate_limit_rps: float = Field(default=1.0, ge=0.1, le=100)  # リクエスト/秒
    rate_limit_burst: int = Field(default=10, ge=1, le=1000)
    human_speed_jitter: bool = Field(default=True)  # 人間的な速度のゆらぎ
    require_device_match: bool = Field(default=True)  # デバイス指紋の一致を要求
    allow_concurrent: bool = Field(default=False)  # 並行リクエストを許可
    max_request_size: int = Field(default=10485760)  # 最大リクエストサイズ（10MB）
    
class DeviceFingerprint(BaseModel):
    """デバイス指紋"""
    user_agent: str
    accept_language: str
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    platform: Optional[str] = None
    hardware_concurrency: Optional[int] = None
    memory: Optional[int] = None
    canvas_fp: Optional[str] = None  # Canvas fingerprint
    webgl_fp: Optional[str] = None  # WebGL fingerprint
    audio_fp: Optional[str] = None  # Audio fingerprint
    
    def calculate_hash(self) -> str:
        """指紋のハッシュを計算"""
        # 重要な属性のみを使用してハッシュを生成
        core_attrs = {
            "user_agent": self.user_agent,
            "accept_language": self.accept_language,
            "platform": self.platform or "",
            "screen_resolution": self.screen_resolution or "",
        }
        
        # 安定したJSON表現
        json_str = json.dumps(core_attrs, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

@dataclass
class LPRToken:
    """LPRトークン"""
    jti: str  # JWT ID (unique identifier)
    version: str
    subject_pseudonym: str  # 仮名化された主体ID
    issued_at: datetime
    expires_at: datetime
    device_fingerprint_hash: str
    origin_allowlist: List[str]
    scope_allowlist: List[LPRScope]
    policy: LPRPolicy
    correlation_id: str  # 監査用相関ID
    parent_session_id: Optional[str] = None  # 元のセッションID（監査用）
    revoked: bool = False
    revocation_reason: Optional[str] = None
    
    def to_jws(self, key: jwk.JWK) -> str:
        """JWS形式に変換"""
        payload = {
            "jti": self.jti,
            "ver": self.version,
            "sub": self.subject_pseudonym,
            "iat": int(self.issued_at.timestamp()),
            "exp": int(self.expires_at.timestamp()),
            "dfp": self.device_fingerprint_hash,
            "origins": self.origin_allowlist,
            "scopes": [
                {
                    "method": s.method,
                    "url": s.url_pattern,
                    "desc": s.description
                }
                for s in self.scope_allowlist
            ],
            "policy": self.policy.dict(),
            "cid": self.correlation_id,
            "psid": self.parent_session_id,
        }
        
        # JWS作成（ES256署名）
        token = jws.JWS(json_encode(payload))
        token.add_signature(key, None, json_encode({"alg": "ES256"}))
        
        return token.serialize(compact=True)
    
    @classmethod
    def from_jws(cls, token_str: str, key: jwk.JWK) -> "LPRToken":
        """JWSから復元"""
        token = jws.JWS()
        token.deserialize(token_str)
        
        # 署名検証
        token.verify(key)
        
        payload = json.loads(token.payload)
        
        # スコープを復元
        scopes = [
            LPRScope(
                method=s["method"],
                url_pattern=s["url"],
                description=s.get("desc")
            )
            for s in payload["scopes"]
        ]
        
        # ポリシーを復元
        policy = LPRPolicy(**payload["policy"])
        
        return cls(
            jti=payload["jti"],
            version=payload["ver"],
            subject_pseudonym=payload["sub"],
            issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            device_fingerprint_hash=payload["dfp"],
            origin_allowlist=payload["origins"],
            scope_allowlist=scopes,
            policy=policy,
            correlation_id=payload["cid"],
            parent_session_id=payload.get("psid"),
        )

class LPRService:
    """LPRトークン管理サービス"""
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.signing_key: Optional[jwk.JWK] = None
        self._init_keys()
    
    def _init_keys(self):
        """署名鍵の初期化"""
        # 本番環境では環境変数やKMSから鍵を取得
        # ここではデモ用に新規生成
        self.signing_key = jwk.JWK.generate(kty='EC', crv='P-256')
    
    async def connect_redis(self, redis_url: str):
        """Redis接続"""
        self.redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def issue_token(
        self,
        user_id: str,
        device_fingerprint: DeviceFingerprint,
        scopes: List[LPRScope],
        origins: List[str],
        policy: Optional[LPRPolicy] = None,
        ttl_seconds: int = LPR_TTL_SECONDS,
        parent_session_id: Optional[str] = None,
    ) -> Tuple[LPRToken, str]:
        """LPRトークンを発行"""
        
        # TTL検証
        ttl_seconds = max(LPR_MIN_TTL_SECONDS, min(ttl_seconds, LPR_MAX_TTL_SECONDS))
        
        # デフォルトポリシー
        if policy is None:
            policy = LPRPolicy()
        
        # トークン生成
        now = datetime.now(timezone.utc)
        token = LPRToken(
            jti=secrets.token_urlsafe(32),
            version=LPR_VERSION,
            subject_pseudonym=self._pseudonymize_user_id(user_id),
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            device_fingerprint_hash=device_fingerprint.calculate_hash(),
            origin_allowlist=origins,
            scope_allowlist=scopes,
            policy=policy,
            correlation_id=secrets.token_urlsafe(16),
            parent_session_id=parent_session_id,
        )
        
        # JWS形式に変換
        token_str = token.to_jws(self.signing_key)
        
        # Redisに保存（メタデータのみ）
        await self._store_token_metadata(token)
        
        # 監査ログ
        await self._audit_log(
            "lpr_issued",
            {
                "jti": token.jti,
                "subject": token.subject_pseudonym,
                "scopes": len(token.scope_allowlist),
                "ttl": ttl_seconds,
                "correlation_id": token.correlation_id,
            }
        )
        
        logger.info(
            "LPR token issued",
            jti=token.jti,
            subject=token.subject_pseudonym,
            ttl=ttl_seconds,
        )
        
        return token, token_str
    
    async def verify_token(
        self,
        token_str: str,
        request_method: str,
        request_url: str,
        request_origin: str,
        device_fingerprint: Optional[DeviceFingerprint] = None,
    ) -> Tuple[bool, Optional[LPRToken], Optional[str]]:
        """LPRトークンを検証"""
        
        try:
            # JWSから復元
            token = LPRToken.from_jws(token_str, self.signing_key)
            
            # 有効期限チェック
            now = datetime.now(timezone.utc)
            if now > token.expires_at:
                return False, None, "Token expired"
            
            # 失効チェック
            is_revoked = await self._check_revocation(token.jti)
            if is_revoked:
                return False, None, "Token revoked"
            
            # オリジンチェック
            if not self._check_origin(request_origin, token.origin_allowlist):
                await self._audit_log(
                    "lpr_origin_mismatch",
                    {
                        "jti": token.jti,
                        "request_origin": request_origin,
                        "allowed_origins": token.origin_allowlist,
                    }
                )
                return False, None, "Origin not allowed"
            
            # スコープチェック
            if not self._check_scope(request_method, request_url, token.scope_allowlist):
                await self._audit_log(
                    "lpr_scope_mismatch",
                    {
                        "jti": token.jti,
                        "request_method": request_method,
                        "request_url": request_url,
                    }
                )
                return False, None, "Scope not allowed"
            
            # デバイス指紋チェック（ポリシーで要求される場合）
            if token.policy.require_device_match and device_fingerprint:
                if device_fingerprint.calculate_hash() != token.device_fingerprint_hash:
                    await self._audit_log(
                        "lpr_device_mismatch",
                        {
                            "jti": token.jti,
                            "expected_hash": token.device_fingerprint_hash,
                            "actual_hash": device_fingerprint.calculate_hash(),
                        }
                    )
                    return False, None, "Device fingerprint mismatch"
            
            # レート制限チェック
            rate_ok = await self._check_rate_limit(token)
            if not rate_ok:
                await self._audit_log(
                    "lpr_rate_limit_exceeded",
                    {"jti": token.jti}
                )
                return False, None, "Rate limit exceeded"
            
            # 成功
            await self._audit_log(
                "lpr_verified",
                {
                    "jti": token.jti,
                    "method": request_method,
                    "url": request_url,
                    "correlation_id": token.correlation_id,
                }
            )
            
            return True, token, None
            
        except Exception as e:
            logger.error("Token verification failed", error=str(e))
            return False, None, f"Verification failed: {str(e)}"
    
    async def revoke_token(
        self,
        jti: str,
        reason: str,
        revoked_by: Optional[str] = None
    ) -> bool:
        """トークンを失効"""
        
        if not self.redis_client:
            logger.error("Redis not connected")
            return False
        
        # 失効リストに追加
        revocation_key = f"lpr:revoked:{jti}"
        revocation_data = {
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "revoked_by": revoked_by or "system",
        }
        
        # 失効情報を保存（元のTTLより長く保持）
        await self.redis_client.setex(
            revocation_key,
            LPR_MAX_TTL_SECONDS * 2,  # 最大TTLの2倍保持
            json.dumps(revocation_data)
        )
        
        # Pub/Subで全ノードに通知
        await self.redis_client.publish(
            "lpr:revocation",
            json.dumps({"jti": jti, **revocation_data})
        )
        
        # 監査ログ
        await self._audit_log(
            "lpr_revoked",
            {
                "jti": jti,
                "reason": reason,
                "revoked_by": revoked_by,
            }
        )
        
        logger.info("LPR token revoked", jti=jti, reason=reason)
        return True
    
    async def get_token_status(self, jti: str) -> Dict[str, Any]:
        """トークンのステータスを取得"""
        
        # 失効チェック
        is_revoked = await self._check_revocation(jti)
        
        # メタデータ取得
        metadata = await self._get_token_metadata(jti)
        
        if metadata:
            return {
                "jti": jti,
                "status": "revoked" if is_revoked else "active",
                "issued_at": metadata.get("issued_at"),
                "expires_at": metadata.get("expires_at"),
                "subject": metadata.get("subject"),
                "scopes": metadata.get("scopes"),
            }
        
        return {
            "jti": jti,
            "status": "not_found",
        }
    
    # ===== プライベートメソッド =====
    
    def _pseudonymize_user_id(self, user_id: str) -> str:
        """ユーザーIDを仮名化"""
        # HMAC-SHA256で仮名化（鍵は環境変数から取得すべき）
        secret = settings.jwt_secret_key.encode()
        h = hashlib.blake2b(user_id.encode(), key=secret, digest_size=16)
        return h.hexdigest()
    
    def _check_origin(self, request_origin: str, allowlist: List[str]) -> bool:
        """オリジンチェック"""
        import fnmatch
        
        for allowed in allowlist:
            if fnmatch.fnmatch(request_origin, allowed):
                return True
        return False
    
    def _check_scope(
        self,
        method: str,
        url: str,
        scopes: List[LPRScope]
    ) -> bool:
        """スコープチェック"""
        for scope in scopes:
            if scope.matches(method, url):
                return True
        return False
    
    async def _check_revocation(self, jti: str) -> bool:
        """失効チェック"""
        if not self.redis_client:
            return False
        
        revocation_key = f"lpr:revoked:{jti}"
        result = await self.redis_client.get(revocation_key)
        return result is not None
    
    async def _check_rate_limit(self, token: LPRToken) -> bool:
        """レート制限チェック"""
        if not self.redis_client:
            return True  # Redisなしの場合は通す
        
        # トークンごとのレート制限キー
        rate_key = f"lpr:rate:{token.jti}"
        
        # 現在のカウント取得
        current = await self.redis_client.get(rate_key)
        current_count = int(current) if current else 0
        
        # バースト制限チェック
        if current_count >= token.policy.rate_limit_burst:
            return False
        
        # カウントアップ
        pipe = self.redis_client.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, 1)  # 1秒でリセット
        await pipe.execute()
        
        # ヒューマンスピードジッター（オプション）
        if token.policy.human_speed_jitter:
            import random
            delay = random.uniform(0.1, 0.5)  # 100-500ms
            await asyncio.sleep(delay)
        
        return True
    
    async def _store_token_metadata(self, token: LPRToken):
        """トークンメタデータを保存"""
        if not self.redis_client:
            return
        
        metadata_key = f"lpr:metadata:{token.jti}"
        metadata = {
            "issued_at": token.issued_at.isoformat(),
            "expires_at": token.expires_at.isoformat(),
            "subject": token.subject_pseudonym,
            "scopes": len(token.scope_allowlist),
            "origins": token.origin_allowlist,
            "device_fp": token.device_fingerprint_hash,
        }
        
        ttl = int((token.expires_at - datetime.now(timezone.utc)).total_seconds())
        await self.redis_client.setex(
            metadata_key,
            max(ttl, 1),
            json.dumps(metadata)
        )
    
    async def _get_token_metadata(self, jti: str) -> Optional[Dict]:
        """トークンメタデータを取得"""
        if not self.redis_client:
            return None
        
        metadata_key = f"lpr:metadata:{jti}"
        result = await self.redis_client.get(metadata_key)
        
        if result:
            return json.loads(result)
        return None
    
    async def _audit_log(self, event: str, data: Dict[str, Any]):
        """監査ログ記録"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data,
        }
        
        # 構造化ログ出力
        logger.info(f"AUDIT: {event}", **data)
        
        # Redisストリームに追加（append-only）
        if self.redis_client:
            stream_key = "audit:lpr"
            await self.redis_client.xadd(
                stream_key,
                {"entry": json.dumps(log_entry)},
                maxlen=100000  # 最大10万エントリ
            )

# シングルトンインスタンス
lpr_service = LPRService()

async def init_lpr_service():
    """LPRサービスの初期化"""
    await lpr_service.connect_redis(settings.redis_url)
    logger.info("LPR service initialized")

async def get_lpr_service() -> LPRService:
    """LPRサービスインスタンスを取得"""
    return lpr_service