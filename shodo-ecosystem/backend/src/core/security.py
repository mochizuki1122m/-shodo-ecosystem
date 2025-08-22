"""
Enterprise Security Configuration
MUST requirements for production deployment
"""

from typing import List, Optional
from datetime import datetime, timedelta
import secrets
import hashlib
import json
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # OWASP recommendation
)

# JWT Configuration
class JWTConfig:
    ALGORITHM = "RS256"  # RSA with SHA-256
    ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour max
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    ISSUER = "shodo-ecosystem"
    AUDIENCE = "shodo-api"
    
class SecurityHeaders:
    """Security headers for all responses"""
    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
    }

class RateLimitConfig:
    """Rate limiting configuration"""
    DEFAULT_LIMIT = 100  # requests per minute
    BURST_LIMIT = 150    # burst allowance
    
    ENDPOINT_LIMITS = {
        "/api/v1/auth/login": 5,
        "/api/v1/auth/register": 3,
        "/api/v1/lpr/issue": 10,
        "/api/v1/nlp/analyze": 30,
    }

class InputSanitizer:
    """Input sanitization and validation"""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input (Unicode-friendly)
        - NULLや制御文字(カテゴリ=Cc/Cf)の除去
        - 最大長で切り詰め
        - 前後空白のトリム
        日本語・多言語文字は保持
        """
        if value is None:
            return ""
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                return ""
        
        # 長さ制限（先に軽く丸めて負荷低減）
        if len(value) > max_length * 2:
            value = value[: max_length * 2]
        
        # 制御文字の除去（Unicodeカテゴリ）
        import unicodedata
        cleaned_chars = []
        for ch in value:
            cat = unicodedata.category(ch)
            # Cc: Other, Control / Cf: Other, Format を除去。タブと改行は許可
            if ch in ('\n', '\t'):
                cleaned_chars.append(ch)
                continue
            if cat in ("Cc", "Cf"):
                continue
            cleaned_chars.append(ch)
        cleaned = "".join(cleaned_chars)
        
        # 最終的な長さ制限
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
        
        # 前後のホワイトスペースをトリム
        return cleaned.strip()
    
    @staticmethod
    def sanitize_json(data: dict) -> dict:
        """Recursively sanitize JSON data"""
        if not isinstance(data, dict):
            return {}
        
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = InputSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[key] = InputSanitizer.sanitize_json(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    InputSanitizer.sanitize_json(item) if isinstance(item, dict)
                    else InputSanitizer.sanitize_string(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized

class PIIMasking:
    """PII detection and masking"""
    
    PATTERNS = {
        'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'phone': r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,5}[-\s\.]?[0-9]{1,5}',
        'credit_card': r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'ip_address': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
    }
    
    @classmethod
    def mask_pii(cls, text: str) -> str:
        """Mask PII in text"""
        import re
        
        for pattern_name, pattern in cls.PATTERNS.items():
            text = re.sub(pattern, f'[REDACTED_{pattern_name.upper()}]', text)
        
        return text
    
    @classmethod
    def mask_dict(cls, data: dict, fields_to_mask: List[str] = None) -> dict:
        """Mask PII in dictionary"""
        if fields_to_mask is None:
            fields_to_mask = ['password', 'token', 'secret', 'api_key', 'email', 'phone']
        
        masked = {}
        for key, value in data.items():
            if any(field in key.lower() for field in fields_to_mask):
                masked[key] = '[REDACTED]'
            elif isinstance(value, str):
                masked[key] = cls.mask_pii(value)
            elif isinstance(value, dict):
                masked[key] = cls.mask_dict(value, fields_to_mask)
            else:
                masked[key] = value
        
        return masked

class SecureTokenGenerator:
    """Cryptographically secure token generation"""
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate URL-safe random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate API key with checksum"""
        prefix = "sk_live_"  # or sk_test_ for test environment
        token = secrets.token_hex(32)
        checksum = hashlib.sha256(token.encode()).hexdigest()[:8]
        return f"{prefix}{token}_{checksum}"
    
    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        """Verify API key checksum"""
        try:
            parts = api_key.rsplit('_', 1)
            if len(parts) != 2:
                return False
            
            key_part = parts[0].split('_', 2)[2]
            checksum = parts[1]
            expected_checksum = hashlib.sha256(key_part.encode()).hexdigest()[:8]
            
            return secrets.compare_digest(checksum, expected_checksum)
        except Exception:
            return False

class SessionManager:
    """Secure session management"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.session_ttl = 3600  # 1 hour
    
    async def create_session(self, user_id: str, metadata: dict = None) -> str:
        """Create secure session"""
        session_id = SecureTokenGenerator.generate_token()
        session_data = {
            'user_id': user_id,
            'created_at': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        
        await self.redis.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps(session_data)
        )
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data"""
        data = await self.redis.get(f"session:{session_id}")
        if data:
            return json.loads(data)
        return None
    
    async def invalidate_session(self, session_id: str):
        """Invalidate session"""
        await self.redis.delete(f"session:{session_id}")

# Export security utilities
__all__ = [
    'pwd_context',
    'JWTConfig',
    'SecurityHeaders',
    'RateLimitConfig',
    'InputSanitizer',
    'PIIMasking',
    'SecureTokenGenerator',
    'SessionManager'
]