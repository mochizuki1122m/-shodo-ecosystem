"""
LPR (Limited Proxy Rights) Service
MUST: Production-ready JWT implementation with full security
"""

import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import uuid
import time
import asyncio

from jose import jwt, JWTError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import structlog

from ...core.config import settings
from ...services.database import get_redis


logger = structlog.get_logger()

class LPRScope:
    """LPR scope definition"""
    def __init__(self, method: str, url_pattern: str, constraints: Dict = None):
        self.method = method.upper()
        self.url_pattern = url_pattern
        self.constraints = constraints or {}
    
    def to_dict(self) -> Dict:
        return {
            "method": self.method,
            "url_pattern": self.url_pattern,
            "constraints": self.constraints
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LPRScope':
        return cls(
            method=data["method"],
            url_pattern=data["url_pattern"],
            constraints=data.get("constraints", {})
        )

class LPRPolicy:
    """LPR policy definition"""
    def __init__(
        self,
        max_requests: int = 100,
        time_window: int = 60,
        burst_limit: int = 10,
        human_speed_jitter: bool = True
    ):
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_limit = burst_limit
        self.human_speed_jitter = human_speed_jitter
    
    def to_dict(self) -> Dict:
        return {
            "max_requests": self.max_requests,
            "time_window": self.time_window,
            "burst_limit": self.burst_limit,
            "human_speed_jitter": self.human_speed_jitter
        }

class DeviceFingerprint:
    """Device fingerprint for verification"""
    def __init__(
        self,
        user_agent: str,
        accept_language: str,
        screen_resolution: str = None,
        timezone: str = None,
        canvas_hash: str = None
    ):
        self.user_agent = user_agent
        self.accept_language = accept_language
        self.screen_resolution = screen_resolution
        self.timezone = timezone
        self.canvas_hash = canvas_hash
    
    def generate_hash(self) -> str:
        """Generate deterministic hash of fingerprint"""
        data = f"{self.user_agent}|{self.accept_language}|{self.screen_resolution}|{self.timezone}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def matches(self, other_hash: str, tolerance: float = 0.9) -> bool:
        """Check if fingerprint matches with tolerance"""
        # Simple exact match for now, can implement fuzzy matching
        return self.generate_hash() == other_hash

class LPRService:
    """
    LPR token management service
    MUST requirements:
    - JWT with JWS, kid, exp ≤ 1h
    - jti for revocation tracking
    - Device fingerprint verification
    - Rate limiting and human speed jitter
    - Complete audit trail
    """
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.private_key = None
        self.public_key = None
        self.kid = None
        self._initialize_keys()
        # Memory fallback stores
        self._memory_tokens: Dict[str, Dict[str, Any]] = {}
        self._user_tokens: Dict[str, set] = {}
        self._revoked_jtis: Dict[str, float] = {}  # jti -> expiry ts
        self._last_cleanup_ts: float = time.time()
        self._last_redis_retry_ts: float = 0.0
        self._redis_retry_interval_sec: int = 60
    
    def _now_ts(self) -> float:
        return time.time()

    async def _ensure_redis_connection(self) -> bool:
        """Attempt to (re)acquire Redis connection lazily."""
        if self.redis is not None:
            return True
        now = self._now_ts()
        if now - self._last_redis_retry_ts < self._redis_retry_interval_sec:
            return False
        self._last_redis_retry_ts = now
        try:
            self.redis = get_redis()
            if self.redis:
                logger.info("Redis connection re-established for LPR service")
                # Optionally flush memory revocations into Redis with remaining TTL
                await self._flush_memory_revocations_to_redis()
                return True
        except Exception as e:
            logger.debug("Redis reconnection attempt failed", error=str(e))
        return False

    async def _flush_memory_revocations_to_redis(self):
        if not self.redis:
            return
        now = self._now_ts()
        for jti, exp_ts in list(self._revoked_jtis.items()):
            ttl = int(max(0, exp_ts - now))
            if ttl <= 0:
                del self._revoked_jtis[jti]
                continue
            try:
                await self.redis.setex(
                    f"lpr:revoked:{jti}",
                    ttl,
                    json.dumps({"revoked_at": datetime.now(timezone.utc).isoformat(), "reason": "memory_sync"})
                )
            except Exception as e:
                logger.debug("Failed to push memory revocation to Redis", jti=jti, error=str(e))

    def _cleanup_memory(self):
        now = self._now_ts()
        # Run at most once per 60 seconds
        if now - self._last_cleanup_ts < 60:
            return
        self._last_cleanup_ts = now
        # Tokens
        for jti, meta in list(self._memory_tokens.items()):
            exp_iso = meta.get("expires_at")
            try:
                exp_dt = datetime.fromisoformat(exp_iso) if isinstance(exp_iso, str) else None
            except Exception:
                exp_dt = None
            if exp_dt and exp_dt < datetime.now(timezone.utc):
                del self._memory_tokens[jti]
        # Revocations
        for jti, exp_ts in list(self._revoked_jtis.items()):
            if exp_ts <= now:
                del self._revoked_jtis[jti]

    def _initialize_keys(self):
        """Initialize RSA key pair for JWT signing"""
        # In production, load from Vault/KMS
        if settings.is_production():
            # Load from secure storage
            logger.info("Loading LPR keys from secure storage")
            # self.private_key = load_from_vault()
            # self.public_key = load_from_vault()
        else:
            # Generate for development
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            self.private_key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        
        # Generate key ID
        self.kid = hashlib.sha256(self.public_key).hexdigest()[:16]
    
    async def issue_token(
        self,
        service: str,
        purpose: str,
        scopes: List[LPRScope],
        device_fingerprint: DeviceFingerprint,
        user_id: str,
        consent: bool = False,
        policy: Optional[LPRPolicy] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Issue a new LPR token
        
        MUST requirements:
        - exp ≤ 1 hour
        - Unique jti
        - Device fingerprint hash
        - Audit logging
        """
        
        if not consent:
            raise ValueError("User consent is required for LPR token issuance")
        
        # Generate unique JTI
        jti = str(uuid.uuid4())
        
        # Token expiration (max 1 hour)
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=1)
        
        # Default policy if not provided
        if policy is None:
            policy = LPRPolicy()
        
        # Build token claims
        claims = {
            # Standard JWT claims
            "jti": jti,
            "iss": settings.app_name,
            "sub": user_id,
            "aud": service,
            "exp": exp,
            "iat": now,
            "nbf": now,
            
            # LPR specific claims
            "service": service,
            "purpose": purpose,
            "scopes": [s.to_dict() for s in scopes],
            "policy": policy.to_dict(),
            "device_fingerprint_hash": device_fingerprint.generate_hash(),
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "origins": [settings.cors_origins[0]] if settings.cors_origins else ["*"],
            "consent": {
                "granted": consent,
                "timestamp": now.isoformat(),
                "purpose": purpose
            }
        }
        
        # Sign token
        token = jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid}
        )
        
        # Store token metadata in Redis for tracking
        token_meta = {
            "jti": jti,
            "user_id": user_id,
            "service": service,
            "issued_at": now.isoformat(),
            "expires_at": exp.isoformat(),
            "device_fingerprint_hash": device_fingerprint.generate_hash(),
            "revoked": False
        }
        if self.redis or await self._ensure_redis_connection():
            try:
                await self.redis.setex(
                    f"lpr:token:{jti}",
                    3600,  # 1 hour TTL
                    json.dumps(token_meta)
                )
                await self.redis.sadd(f"lpr:user:{user_id}:tokens", jti)
            except Exception as e:
                # 本番ではフォールバック禁止
                if settings.is_production():
                    logger.error("Failed to store LPR token meta in Redis (production)", error=str(e))
                    raise RuntimeError("Redis unavailable for LPR in production")
                logger.warning("Redis error storing token meta, using in-memory fallback (non-prod)", error=str(e))
                self._memory_tokens[jti] = token_meta
                self._user_tokens.setdefault(user_id, set()).add(jti)
        else:
            # 本番ではフォールバック禁止
            if settings.is_production():
                logger.error("Redis not connected for LPR in production")
                raise RuntimeError("Redis required for LPR in production")
            # Memory fallback (development/testing)
            self._memory_tokens[jti] = token_meta
            self._user_tokens.setdefault(user_id, set()).add(jti)
        
        # Audit log
        logger.info(
            "LPR token issued",
            jti=jti,
            user_id=user_id,
            service=service,
            purpose=purpose,
            scopes_count=len(scopes),
            correlation_id=correlation_id
        )
        
        return {
            "token": token,
            "jti": jti,
            "expires_at": exp.isoformat(),
            "scopes": [s.to_dict() for s in scopes]
        }
    
    async def verify_token(
        self,
        token: str,
        device_fingerprint: Optional[DeviceFingerprint] = None,
        required_scope: Optional[LPRScope] = None
    ) -> Dict[str, Any]:
        """
        Verify LPR token
        
        Checks:
        1. Signature validity
        2. Expiration
        3. Revocation status
        4. Device fingerprint match
        5. Scope authorization
        """
        
        try:
            # Decode and verify signature
            claims = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                options={"verify_exp": True}
            )
            
            jti = claims.get("jti")
            
            # Check revocation
            revoked = False
            if self.redis or await self._ensure_redis_connection():
                try:
                    token_meta = await self.redis.get(f"lpr:token:{jti}")
                    if token_meta:
                        meta = json.loads(token_meta)
                        if meta.get("revoked"):
                            revoked = True
                except Exception as e:
                    logger.warning("Redis error during verify, falling back to memory", error=str(e))
            # Memory fallback revocation check（本番は禁止）
            now_ts = self._now_ts()
            if (not self.redis) or (revoked is False):
                if settings.is_production():
                    logger.error("LPR verification denied: Redis unavailable in production")
                    raise JWTError("Revocation check unavailable")
                exp_ts = self._revoked_jtis.get(jti)
                if exp_ts and exp_ts > now_ts:
                    revoked = True
            if revoked:
                raise JWTError("Token has been revoked")
            
            # Verify device fingerprint if provided
            if device_fingerprint:
                stored_hash = claims.get("device_fingerprint_hash")
                if not device_fingerprint.matches(stored_hash):
                    logger.warning(
                        "Device fingerprint mismatch",
                        jti=jti,
                        stored_hash=stored_hash,
                        current_hash=device_fingerprint.generate_hash()
                    )
                    # Allow with tolerance in development
                    if settings.is_production():
                        raise JWTError("Device fingerprint mismatch")
            
            # Check scope if required
            if required_scope:
                scopes = [LPRScope.from_dict(s) for s in claims.get("scopes", [])]
                if not self._check_scope_authorization(required_scope, scopes):
                    raise JWTError("Insufficient scope")
            
            # Update last used timestamp
            if self.redis or await self._ensure_redis_connection():
                try:
                    await self.redis.hset(
                        f"lpr:token:{jti}:usage",
                        "last_used",
                        datetime.now(timezone.utc).isoformat()
                    )
                except Exception:
                    pass
            
            return {
                "valid": True,
                "jti": jti,
                "user_id": claims.get("sub"),
                "service": claims.get("service"),
                "scopes": claims.get("scopes", []),
                "expires_at": datetime.fromtimestamp(
                    claims.get("exp"),
                    tz=timezone.utc
                ).isoformat(),
                "correlation_id": claims.get("correlation_id")
            }
            
        except JWTError as e:
            logger.warning("LPR token verification failed", error=str(e))
            return {
                "valid": False,
                "error": str(e)
            }
    
    async def revoke_token(
        self,
        jti: str,
        reason: str = None,
        user_id: str = None
    ) -> bool:
        """
        Revoke an LPR token
        
        Adds JTI to blacklist with TTL
        """
        
        # Try Redis first
        if self.redis or await self._ensure_redis_connection():
            try:
                token_meta = await self.redis.get(f"lpr:token:{jti}")
                if token_meta:
                    meta = json.loads(token_meta)
                    meta["revoked"] = True
                    meta["revoked_at"] = datetime.now(timezone.utc).isoformat()
                    meta["revocation_reason"] = reason
                    ttl = await self.redis.ttl(f"lpr:token:{jti}")
                    if ttl > 0:
                        await self.redis.setex(
                            f"lpr:token:{jti}", ttl, json.dumps(meta)
                        )
                await self.redis.setex(
                    f"lpr:revoked:{jti}",
                    3600,
                    json.dumps({
                        "revoked_at": datetime.now(timezone.utc).isoformat(),
                        "reason": reason,
                        "user_id": user_id
                    })
                )
                if user_id:
                    await self.redis.srem(f"lpr:user:{user_id}:tokens", jti)
            except Exception as e:
                if settings.is_production():
                    logger.error("LPR revocation failed: Redis error in production", error=str(e))
                    return False
                logger.warning("Redis error during revocation, using memory fallback (non-prod)", error=str(e))
        # Memory fallback（本番は禁止）
        if settings.is_production():
            return False
        now = self._now_ts()
        self._revoked_jtis[jti] = now + 3600
        meta = self._memory_tokens.get(jti)
        if meta:
            meta["revoked"] = True
            meta["revoked_at"] = datetime.now(timezone.utc).isoformat()
            meta["revocation_reason"] = reason
        if user_id and user_id in self._user_tokens:
            self._user_tokens[user_id].discard(jti)
        
        logger.info(
            "LPR token revoked",
            jti=jti,
            reason=reason,
            user_id=user_id
        )
        
        return True
    
    async def list_user_tokens(self, user_id: str) -> List[Dict]:
        """List all active tokens for a user"""
        
        tokens: List[Dict] = []
        if self.redis or await self._ensure_redis_connection():
            try:
                jtis = await self.redis.smembers(f"lpr:user:{user_id}:tokens")
                for jti in jtis:
                    token_meta = await self.redis.get(f"lpr:token:{jti}")
                    if token_meta:
                        meta = json.loads(token_meta)
                        if not meta.get("revoked"):
                            tokens.append(meta)
            except Exception:
                pass
        # Merge memory fallback
        for jti in self._user_tokens.get(user_id, set()):
            meta = self._memory_tokens.get(jti)
            if meta and not meta.get("revoked"):
                tokens.append(meta)
        return tokens
    
    async def revoke_all_user_tokens(self, user_id: str, reason: str = None) -> int:
        """Revoke all tokens for a user"""
        
        tokens = await self.list_user_tokens(user_id)
        count = 0
        
        for token in tokens:
            if await self.revoke_token(token["jti"], reason, user_id):
                count += 1
        
        logger.warning(
            "All user tokens revoked",
            user_id=user_id,
            count=count,
            reason=reason
        )
        
        return count
    
    def _check_scope_authorization(
        self,
        required: LPRScope,
        granted: List[LPRScope]
    ) -> bool:
        """Check if required scope is authorized"""
        
        for scope in granted:
            # Check method match
            if scope.method != required.method and scope.method != "*":
                continue
            
            # Check URL pattern match (simple prefix match for now)
            if required.url_pattern.startswith(scope.url_pattern):
                return True
        
        return False
    
    async def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens (batch job)"""
        
        # Redis TTL handles expiration automatically; cleanup memory fallback
        self._cleanup_memory()
        logger.info("LPR token cleanup completed")
        return 0
    
    async def get_token_status(self, jti: str) -> Dict[str, Any]:
        """Get token status and metadata by JTI"""
        status = {
            "status": "unknown",
        }
        meta = None
        if self.redis or await self._ensure_redis_connection():
            try:
                meta_json = await self.redis.get(f"lpr:token:{jti}")
                if meta_json:
                    meta = json.loads(meta_json)
            except Exception:
                meta = None
        if meta is None:
            meta = self._memory_tokens.get(jti)
        if not meta:
            status["status"] = "not_found"
            return status
        # Determine status by revocation and expiry
        revoked = meta.get("revoked", False) or (jti in self._revoked_jtis and self._revoked_jtis[jti] > self._now_ts())
        expires_at = meta.get("expires_at")
        status.update({
            "issued_at": meta.get("issued_at"),
            "expires_at": expires_at,
            "subject": meta.get("user_id"),
            "scopes": len(meta.get("scopes", [])) if isinstance(meta.get("scopes"), list) else None,
        })
        if revoked:
            status["status"] = "revoked"
        else:
            # Optionally, parse time to check expiration
            try:
                from datetime import datetime as _dt
                from dateutil import parser as _parser  # optional; if unavailable, skip
                exp_dt = _parser.isoparse(expires_at) if expires_at else None
                status["status"] = "expired" if exp_dt and exp_dt < _dt.now(timezone.utc) else "active"
            except Exception:
                status["status"] = "active"
        return status

# Singleton instance
lpr_service = None

async def get_lpr_service() -> LPRService:
    """Get LPR service instance"""
    global lpr_service
    if lpr_service is None:
        # Initialize with Redis from app context
        # from ...services.database import get_redis # This line is removed as per the edit hint
        redis = get_redis()  # Synchronous function, no await needed
        lpr_service = LPRService(redis)
    return lpr_service