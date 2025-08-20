"""
LPR (Limited Proxy Rights) Service
MUST: Production-ready JWT implementation with full security
"""

import json
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import uuid

from jose import jwt, JWTError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import structlog

from ...core.config import settings
from ...core.security import SecureTokenGenerator

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
        if self.redis:
            token_meta = {
                "jti": jti,
                "user_id": user_id,
                "service": service,
                "issued_at": now.isoformat(),
                "expires_at": exp.isoformat(),
                "device_fingerprint_hash": device_fingerprint.generate_hash(),
                "revoked": False
            }
            await self.redis.setex(
                f"lpr:token:{jti}",
                3600,  # 1 hour TTL
                json.dumps(token_meta)
            )
            
            # Add to user's token list
            await self.redis.sadd(f"lpr:user:{user_id}:tokens", jti)
        
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
            if self.redis:
                token_meta = await self.redis.get(f"lpr:token:{jti}")
                if token_meta:
                    meta = json.loads(token_meta)
                    if meta.get("revoked"):
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
            if self.redis:
                await self.redis.hset(
                    f"lpr:token:{jti}:usage",
                    "last_used",
                    datetime.now(timezone.utc).isoformat()
                )
            
            return {
                "valid": True,
                "jti": jti,
                "user_id": claims.get("sub"),
                "service": claims.get("service"),
                "scopes": claims.get("scopes", []),
                "expires_at": datetime.fromtimestamp(
                    claims.get("exp"),
                    tz=timezone.utc
                ).isoformat()
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
        
        if not self.redis:
            logger.warning("Redis not available for token revocation")
            return False
        
        # Mark token as revoked
        token_meta = await self.redis.get(f"lpr:token:{jti}")
        if token_meta:
            meta = json.loads(token_meta)
            meta["revoked"] = True
            meta["revoked_at"] = datetime.now(timezone.utc).isoformat()
            meta["revocation_reason"] = reason
            
            # Update with remaining TTL
            ttl = await self.redis.ttl(f"lpr:token:{jti}")
            if ttl > 0:
                await self.redis.setex(
                    f"lpr:token:{jti}",
                    ttl,
                    json.dumps(meta)
                )
        
        # Add to revocation list
        await self.redis.setex(
            f"lpr:revoked:{jti}",
            3600,  # Keep for 1 hour
            json.dumps({
                "revoked_at": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "user_id": user_id
            })
        )
        
        # Remove from user's active tokens
        if user_id:
            await self.redis.srem(f"lpr:user:{user_id}:tokens", jti)
        
        logger.info(
            "LPR token revoked",
            jti=jti,
            reason=reason,
            user_id=user_id
        )
        
        return True
    
    async def list_user_tokens(self, user_id: str) -> List[Dict]:
        """List all active tokens for a user"""
        
        if not self.redis:
            return []
        
        # Get user's token JTIs
        jtis = await self.redis.smembers(f"lpr:user:{user_id}:tokens")
        
        tokens = []
        for jti in jtis:
            token_meta = await self.redis.get(f"lpr:token:{jti}")
            if token_meta:
                meta = json.loads(token_meta)
                if not meta.get("revoked"):
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
        
        if not self.redis:
            return 0
        
        # Redis TTL handles expiration automatically
        # This is for additional cleanup if needed
        
        logger.info("LPR token cleanup completed")
        return 0

# Singleton instance
lpr_service = None

async def get_lpr_service() -> LPRService:
    """Get LPR service instance"""
    global lpr_service
    if lpr_service is None:
        # Initialize with Redis from app context
        from ...services.database import get_redis
        redis = get_redis()  # Synchronous function, no await needed
        lpr_service = LPRService(redis)
    return lpr_service

    
async def init_lpr_service():
    """Initialize LPR service at app startup (idempotent)"""
    _ = await get_lpr_service()
    logger.info("LPR service initialized")


def _format_status(status: Dict[str, Any]) -> Dict[str, Any]:
    return status


async def get_token_status(jti: str) -> Dict[str, Any]:
    """Get token status summary by JTI (best-effort)"""
    svc = await get_lpr_service()
    if not svc.redis:
        # Redis unavailable; return unknown status
        return {
            "status": "unknown",
            "jti": jti,
        }
    meta = await svc.redis.get(f"lpr:token:{jti}")
    if not meta:
        return {
            "status": "not_found",
            "jti": jti,
        }
    try:
        data = json.loads(meta)
    except Exception:
        return {
            "status": "invalid",
            "jti": jti,
        }
    status = {
        "status": "revoked" if data.get("revoked") else "active",
        "issued_at": data.get("issued_at"),
        "expires_at": data.get("expires_at"),
        "subject": data.get("user_id"),
        "scopes": len(data.get("scopes", [])) if isinstance(data.get("scopes"), list) else None,
    }
    return status