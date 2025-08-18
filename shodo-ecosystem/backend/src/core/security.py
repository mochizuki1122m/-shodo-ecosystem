"""
セキュリティ関連のコア機能
JWT認証、CORS設定、レート制限、入力検証など
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import wraps
import hashlib
import hmac

from fastapi import HTTPException, Security, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import jwt
from pydantic import BaseModel, Field, validator
import bleach
from cryptography.fernet import Fernet

# 環境変数から設定を読み込み
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

# セキュリティスキーム
security = HTTPBearer()

# レート制限の設定
limiter = Limiter(key_func=get_remote_address)

class SecurityConfig:
    """セキュリティ設定"""
    
    # CORS設定
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    ALLOWED_HEADERS = ["*"]
    ALLOW_CREDENTIALS = True
    
    # CSP設定
    CSP_DIRECTIVES = {
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline' 'unsafe-eval'",  # 開発環境用
        "style-src": "'self' 'unsafe-inline'",
        "img-src": "'self' data: https:",
        "font-src": "'self'",
        "connect-src": "'self'",
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'"
    }
    
    # セキュリティヘッダー
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    
    # 入力制限
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    MAX_TOKEN_LENGTH = 4096
    MAX_PROMPT_LENGTH = 2048

class TokenData(BaseModel):
    """JWTトークンのペイロード"""
    user_id: str
    username: str
    email: str
    roles: List[str] = Field(default_factory=list)
    exp: Optional[datetime] = None

class JWTManager:
    """JWT管理クラス"""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any]) -> str:
        """アクセストークンの生成"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> TokenData:
        """トークンの検証"""
        token = credentials.credentials
        
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            token_data = TokenData(**payload)
            
            # 有効期限チェック
            if token_data.exp and token_data.exp < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return token_data
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

class InputSanitizer:
    """入力のサニタイズ"""
    
    @staticmethod
    def sanitize_html(html: str) -> str:
        """HTMLのサニタイズ"""
        allowed_tags = [
            'div', 'span', 'p', 'a', 'img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody',
            'tr', 'th', 'td', 'strong', 'em', 'br', 'hr'
        ]
        
        allowed_attributes = {
            '*': ['class', 'id'],
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title']
        }
        
        return bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
    
    @staticmethod
    def sanitize_json(data: Any) -> Any:
        """JSONデータのサニタイズ"""
        if isinstance(data, str):
            return InputSanitizer.sanitize_html(data)
        elif isinstance(data, list):
            return [InputSanitizer.sanitize_json(item) for item in data]
        elif isinstance(data, dict):
            return {key: InputSanitizer.sanitize_json(value) for key, value in data.items()}
        return data
    
    @staticmethod
    def validate_prompt(prompt: str) -> str:
        """プロンプトの検証とサニタイズ"""
        if len(prompt) > SecurityConfig.MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt exceeds maximum length of {SecurityConfig.MAX_PROMPT_LENGTH}")
        
        # 危険なパターンの除去
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html'
        ]
        
        import re
        for pattern in dangerous_patterns:
            prompt = re.sub(pattern, '', prompt, flags=re.IGNORECASE)
        
        return prompt.strip()

class DataEncryption:
    """データ暗号化"""
    
    def __init__(self):
        self.cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
    
    def encrypt(self, data: str) -> str:
        """データの暗号化"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """データの復号化"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

class RateLimitManager:
    """レート制限管理"""
    
    @staticmethod
    def get_rate_limit_key(request: Request) -> str:
        """レート制限のキー生成"""
        # IPアドレスとユーザーIDの組み合わせ
        ip = get_remote_address(request)
        user_id = getattr(request.state, 'user_id', 'anonymous')
        return f"{ip}:{user_id}"
    
    @staticmethod
    def check_rate_limit(request: Request, limit: str = "100/hour"):
        """レート制限のチェック"""
        # slowapiのlimiterを使用
        return limiter.limit(limit)

def require_auth(required_roles: List[str] = None):
    """認証デコレータ"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # FastAPIの依存性注入を使用
            token_data = kwargs.get('token_data')
            
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # ロールチェック
            if required_roles:
                if not any(role in token_data.roles for role in required_roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def setup_security_middleware(app):
    """セキュリティミドルウェアの設定"""
    
    # CORS設定
    app.add_middleware(
        CORSMiddleware,
        allow_origins=SecurityConfig.ALLOWED_ORIGINS,
        allow_credentials=SecurityConfig.ALLOW_CREDENTIALS,
        allow_methods=SecurityConfig.ALLOWED_METHODS,
        allow_headers=SecurityConfig.ALLOWED_HEADERS,
    )
    
    # Trusted Hostミドルウェア
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "*.shodo-ecosystem.local"]
    )
    
    # レート制限エラーハンドラー
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # セキュリティヘッダーミドルウェア
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        
        # セキュリティヘッダーの追加
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # CSPヘッダーの追加
        csp_header = "; ".join([f"{key} {value}" for key, value in SecurityConfig.CSP_DIRECTIVES.items()])
        response.headers["Content-Security-Policy"] = csp_header
        
        return response
    
    # コンテンツサイズ制限
    @app.middleware("http")
    async def limit_content_size(request: Request, call_next):
        if request.headers.get("content-length"):
            content_length = int(request.headers["content-length"])
            if content_length > SecurityConfig.MAX_CONTENT_LENGTH:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Content too large. Maximum size is {SecurityConfig.MAX_CONTENT_LENGTH} bytes"
                )
        
        return await call_next(request)

# エクスポート
__all__ = [
    'SecurityConfig',
    'JWTManager',
    'InputSanitizer',
    'DataEncryption',
    'RateLimitManager',
    'require_auth',
    'setup_security_middleware',
    'TokenData',
    'security'
]