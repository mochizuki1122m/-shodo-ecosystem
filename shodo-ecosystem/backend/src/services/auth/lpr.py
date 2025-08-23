"""
LPR (Limited Proxy Rights) システム実装
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Any, Tuple
import json
import uuid

from src.core.security import JWTManager

@dataclass
class LPRScope:
    method: str
    url_pattern: str
    description: str | None = None

@dataclass
class LPRPolicy:
    rate_limit_rps: float = 2.0
    rate_limit_burst: int = 20
    human_speed_jitter: bool = True
    require_device_match: bool = True
    allow_concurrent: bool = False
    max_request_size: int = 5 * 1024 * 1024

@dataclass
class DeviceFingerprint:
    user_agent: str | None = None
    accept_language: str | None = None
    screen_resolution: str | None = None
    timezone: str | None = None
    platform: str | None = None
    hardware_concurrency: int | None = None
    memory: int | None = None
    canvas_fp: str | None = None
    webgl_fp: str | None = None
    audio_fp: str | None = None

    def calculate_hash(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

@dataclass
class LPRToken:
    jti: str
    subject_pseudonym: str
    device_fingerprint_hash: str
    scope_allowlist: List[LPRScope]
    origins_allowlist: List[str]
    issued_at: datetime
    expires_at: datetime

class LPRService:
    """簡易LPRサービス（テスト用にメモリ実装）"""
    def __init__(self):
        self.revoked: Dict[str, Dict[str, Any]] = {}

    async def issue_token(
        self,
        user_id: str,
        device_fingerprint: DeviceFingerprint,
        scopes: List[LPRScope],
        origins: List[str],
        policy: Optional[LPRPolicy] = None,
        ttl_seconds: int = 3600,
    ) -> Tuple[LPRToken, str]:
        now = datetime.now(timezone.utc)
        jti = str(uuid.uuid4())
        token = LPRToken(
            jti=jti,
            subject_pseudonym=hashlib.sha256(user_id.encode()).hexdigest(),
            device_fingerprint_hash=device_fingerprint.calculate_hash(),
            scope_allowlist=scopes,
            origins_allowlist=origins,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        claims = {
            "jti": jti,
            "sub": token.subject_pseudonym,
            "dfp": token.device_fingerprint_hash,
            "exp": int(token.expires_at.timestamp()),
            "iat": int(now.timestamp()),
            "scopes": [s.__dict__ for s in scopes],
            "origins": origins,
        }
        token_str = JWTManager.create_access_token(claims)
        return token, token_str

    async def verify_token(
        self,
        token_str: str,
        request_method: str,
        request_url: str,
        request_origin: str,
        device_fingerprint: DeviceFingerprint,
    ) -> Tuple[bool, Optional[LPRToken], Optional[str]]:
        try:
            data = JWTManager.verify_token(type("Creds", (), {"credentials": token_str}))
        except Exception as e:
            return False, None, str(e)
        jti = data.user_id or ""
        if jti in self.revoked:
            return False, None, "revoked"
        now = datetime.now(timezone.utc)
        try:
            payload = json.loads(json.dumps(data.__dict__, default=str))
        except Exception:
            payload = data.__dict__
        exp = payload.get("exp")
        if exp and now.timestamp() > float(exp):
            return False, None, "expired"
        dfp_hash = device_fingerprint.calculate_hash()
        if payload.get("dfp") and payload.get("dfp") != dfp_hash:
            return False, None, "device mismatch"
        scopes = [LPRScope(**s) for s in payload.get("scopes", [])]
        allowed = any(
            s.method.upper() == request_method.upper() and self._url_match(s.url_pattern, request_url)
            for s in scopes
        )
        if not allowed:
            return False, None, "scope violation"
        token = LPRToken(
            jti=payload.get("jti", ""),
            subject_pseudonym=payload.get("sub", ""),
            device_fingerprint_hash=payload.get("dfp", ""),
            scope_allowlist=scopes,
            origins_allowlist=payload.get("origins", []),
            issued_at=datetime.fromtimestamp(payload.get("iat", now.timestamp()), tz=timezone.utc),
            expires_at=datetime.fromtimestamp(payload.get("exp", now.timestamp()), tz=timezone.utc),
        )
        return True, token, None

    async def revoke_token(self, jti: str, reason: str, revoked_by: str) -> bool:
        self.revoked[jti] = {
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "revoked_by": revoked_by,
        }
        return True

    def _url_match(self, pattern: str, url: str) -> bool:
        if pattern.endswith("*"):
            return url.startswith(pattern[:-1])
        return pattern == url

def get_lpr_service() -> LPRService:
    return LPRService()
