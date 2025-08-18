"""
セキュリティコアモジュール
"""

import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from pydantic import BaseModel
import hashlib
import hmac
import secrets
import os

# 環境変数から設定を読み込み
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# パスワードハッシュ設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTPBearer
security = HTTPBearer()

class TokenData(BaseModel):
    """トークンデータ"""
    user_id: str
    username: str
    roles: List[str] = []
    exp: datetime

class JWTManager:
    """JWT管理クラス"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        """アクセストークンの作成"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
        """トークンの検証"""
        token = credentials.credentials
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return TokenData(
                user_id=user_id,
                username=payload.get("username"),
                roles=payload.get("roles", []),
                exp=datetime.fromtimestamp(payload.get("exp"))
            )
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
    """入力サニタイザー"""
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """HTMLタグの除去"""
        # 簡易的な実装（本番環境ではbleachを使用推奨）
        import re
        return re.sub('<.*?>', '', text)
    
    @staticmethod
    def sanitize_json(data: Any) -> Any:
        """JSON データのサニタイズ"""
        if isinstance(data, str):
            return InputSanitizer.sanitize_html(data)
        elif isinstance(data, dict):
            return {k: InputSanitizer.sanitize_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [InputSanitizer.sanitize_json(item) for item in data]
        return data
    
    @staticmethod
    def validate_prompt(text: str, max_length: int = 10000) -> str:
        """プロンプトの検証"""
        if len(text) > max_length:
            raise ValueError(f"Text exceeds maximum length of {max_length}")
        return InputSanitizer.sanitize_html(text)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワードの検証"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """パスワードのハッシュ化"""
    return pwd_context.hash(password)

def generate_api_key() -> str:
    """APIキーの生成"""
    return secrets.token_urlsafe(32)

def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """APIキーの検証"""
    return hmac.compare_digest(
        hashlib.sha256(api_key.encode()).hexdigest(),
        stored_hash
    )

# 簡易的なレート制限実装（本番環境ではslowapi推奨）
class RateLimiter:
    """レート制限クラス"""
    
    def __init__(self):
        self.requests = {}
    
    def check_rate_limit(self, client_id: str, limit: int = 60, window: int = 60) -> bool:
        """レート制限チェック"""
        current_time = datetime.utcnow()
        
        if client_id not in self.requests:
            self.requests[client_id] = []
        
        # 古いリクエストを削除
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if (current_time - req_time).seconds < window
        ]
        
        # リクエスト数チェック
        if len(self.requests[client_id]) >= limit:
            return False
        
        # 新しいリクエストを記録
        self.requests[client_id].append(current_time)
        return True

# グローバルインスタンス
limiter = RateLimiter()