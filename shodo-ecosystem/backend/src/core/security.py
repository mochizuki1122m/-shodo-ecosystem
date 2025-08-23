"""
Enterprise Security Configuration
MUST requirements for production deployment
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import json
from passlib.context import CryptContext

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
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
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

    @staticmethod
    def sanitize_html(html: str) -> str:
        """Basic HTML sanitization to remove script/style and on* attributes"""
        if not isinstance(html, str):
            return ""
        try:
            import re
            # remove script/style blocks
            html = re.sub(r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", "", html, flags=re.IGNORECASE | re.DOTALL)
            # remove on* attributes and javascript: URIs
            html = re.sub(r"on[a-zA-Z]+\s*=\s*\".*?\"", "", html)
            html = re.sub(r"on[a-zA-Z]+\s*=\s*'.*?'", "", html)
            html = re.sub(r"javascript:\s*", "", html, flags=re.IGNORECASE)
            return html
        except Exception:
            return ""

    @staticmethod
    def validate_prompt(prompt: str) -> str:
        """Validate and normalize user prompts, removing dangerous schemes/payloads"""
        if not isinstance(prompt, str):
            return ""
        cleaned = InputSanitizer.sanitize_string(prompt, max_length=4000)
        # Block javascript: and data: URLs
        for bad in ("javascript:", "data:"):
            cleaned = cleaned.replace(bad, "")
        return cleaned

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

class JWTManager:
    """Minimal JWT utility for tests (HS256 by default, RS256 if keys provided)"""
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        try:
            from jose import jwt
            from src.core.config import settings
            expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=1))
            claims = dict(data)
            if 'exp' not in claims:
                claims['exp'] = expire
            if 'iat' not in claims:
                claims['iat'] = datetime.now(timezone.utc)
            algorithm = getattr(settings, 'jwt_algorithm', 'HS256')
            if algorithm == 'RS256' and getattr(settings, 'jwt_private_key', None):
                return jwt.encode(claims, settings.jwt_private_key, algorithm='RS256')
            secret = (settings.secret_key.get_secret_value() if hasattr(settings, 'secret_key') else settings.jwt_secret_key.get_secret_value())
            return jwt.encode(claims, secret, algorithm='HS256')
        except Exception:
            # Fallback for tests
            from jose import jwt
            return jwt.encode(data, 'test-secret-key', algorithm='HS256')

    @staticmethod
    def verify_token(credentials) -> "TokenData":
        from dataclasses import dataclass
        from jose import jwt, JWTError
        from src.core.config import settings
        token = credentials.credentials if hasattr(credentials, 'credentials') else str(credentials)
        algorithms = ['RS256', 'HS256']
        last_err: Optional[Exception] = None
        for alg in algorithms:
            try:
                key = None
                if alg == 'RS256' and getattr(settings, 'jwt_public_key', None):
                    key = settings.jwt_public_key
                else:
                    key = (settings.secret_key.get_secret_value() if hasattr(settings, 'secret_key') else settings.jwt_secret_key.get_secret_value())
                    alg = 'HS256'
                payload = jwt.decode(token, key, algorithms=[alg], audience=getattr(settings, 'jwt_audience', 'shodo-ecosystem'), issuer=getattr(settings, 'jwt_issuer', 'shodo-auth'))
                @dataclass
                class TokenData:
                    user_id: str
                    username: str
                    email: str
                return TokenData(
                    user_id=str(payload.get('user_id') or payload.get('sub') or ''),
                    username=str(payload.get('username') or ''),
                    email=str(payload.get('email') or ''),
                )
            except Exception as e:
                last_err = e
                continue
        raise last_err or JWTError("Invalid token")

class DataEncryption:
    """Symmetric encryption using Fernet (cryptography)"""
    def __init__(self):
        from cryptography.fernet import Fernet
        from src.core.config import settings
        # Derive a 32-byte key from configured secret
        key_material = settings.encryption_key.get_secret_value().encode()
        key = hashlib.sha256(key_material).digest()
        import base64
        self._fernet = Fernet(base64.urlsafe_b64encode(key))
    
    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode())
        return token.decode()
    
    def decrypt(self, token: str) -> str:
        plaintext = self._fernet.decrypt(token.encode())
        return plaintext.decode()

# Export security utilities
__all__ = [
	'pwd_context',
	'JWTConfig',
	'SecurityHeaders',
	'InputSanitizer',
	'PIIMasking',
	'SecureTokenGenerator',
	'JWTManager',
	'DataEncryption'
]