"""
認証ミドルウェア - Single Source of Truth (SSOT) for Authentication
JWT検証とユーザー認証の中央管理
"""

from typing import Optional
from datetime import datetime, timezone
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

from ..core.config import settings
from ..services.database import get_db_session

logger = logging.getLogger(__name__)

# Bearer token security scheme
security = HTTPBearer(auto_error=False)

class TokenClaims(BaseModel):
    """標準化されたJWTクレーム構造"""
    sub: str  # Subject (user_id)
    roles: list[str] = []  # User roles
    exp: int  # Expiration time
    iat: int  # Issued at
    jti: str  # JWT ID (unique identifier)
    aud: str  # Audience
    iss: str  # Issuer
    device_id: Optional[str] = None  # Device fingerprint
    session_id: Optional[str] = None  # Session identifier

class CurrentUser(BaseModel):
    """現在のユーザー情報"""
    user_id: str
    username: str
    email: str
    roles: list[str]
    is_active: bool
    device_id: Optional[str] = None
    session_id: Optional[str] = None

async def verify_jwt_token(token: str) -> Optional[TokenClaims]:
    """
    JWT トークンの検証
    RS256署名、クレーム検証、有効期限チェック
    """
    try:
        # RS256での検証（本番環境では公開鍵を使用）
        # 開発環境ではHS256にフォールバック
        algorithm = settings.jwt_algorithm if hasattr(settings, 'jwt_algorithm') else 'HS256'
        
        if algorithm == 'RS256':
            # 本番: RS256 with public key
            public_key = getattr(settings, 'jwt_public_key', None)
            if not public_key:
                logger.error("RS256 specified but no public key configured")
                return None
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=settings.jwt_audience if hasattr(settings, 'jwt_audience') else 'shodo-ecosystem',
                issuer=settings.jwt_issuer if hasattr(settings, 'jwt_issuer') else 'shodo-auth'
            )
        else:
            # 開発: HS256 with secret
            secret_key = (settings.secret_key.get_secret_value() if hasattr(settings, 'secret_key') else settings.jwt_secret_key.get_secret_value())
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=['HS256']
            )
        
        # クレームの検証
        claims = TokenClaims(**payload)
        
        # 有効期限の追加チェック
        now = datetime.now(timezone.utc).timestamp()
        if claims.exp < now:
            logger.warning(f"Token expired for user {claims.sub}")
            return None
        
        # JTI（JWT ID）の検証 - リプレイ攻撃防止
        # TODO: Redis/DBでJTIのブラックリストチェック
        
        return claims
        
    except JWTError as e:
        if "expired" in str(e).lower():
            logger.warning("JWT token expired")
        else:
            logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"JWT verification error: {e}")
        return None

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db = Depends(get_db_session)
) -> CurrentUser:
    """
    現在の認証済みユーザーを取得
    全APIエンドポイントで共通使用されるSSOT実装
    """
    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    else:
        # Cookieベースのトークンを参照
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # トークン検証
    claims = await verify_jwt_token(token)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # データベースからユーザー情報取得
    # 注: 実際の実装ではユーザーモデルを使用
    try:
        if db:
            # ユーザー存在確認とアクティブステータスチェック
            # TODO: 実際のユーザーモデルクエリに置き換え
            user_data = {
                "user_id": claims.sub,
                "username": f"user_{claims.sub}",  # 実際はDBから取得
                "email": f"{claims.sub}@example.com",  # 実際はDBから取得
                "roles": claims.roles,
                "is_active": True,  # 実際はDBから取得
                "device_id": claims.device_id,
                "session_id": claims.session_id
            }
        else:
            # DBなしのフォールバック（開発環境）
            user_data = {
                "user_id": claims.sub,
                "username": f"user_{claims.sub}",
                "email": f"{claims.sub}@example.com",
                "roles": claims.roles,
                "is_active": True,
                "device_id": claims.device_id,
                "session_id": claims.session_id
            }
        
        current_user = CurrentUser(**user_data)
        
        # ユーザーがアクティブでない場合
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )
        
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching user information"
        )

async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """アクティブユーザーのみを許可"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user

def require_roles(required_roles: list[str]):
    """
    特定のロールを要求するデコレータ
    使用例: @require_roles(['admin', 'moderator'])
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        user_roles = set(current_user.roles)
        required = set(required_roles)
        
        if not required.intersection(user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {required_roles}"
            )
        
        return current_user
    
    return role_checker

# エクスポート
__all__ = [
    'get_current_user',
    'get_current_active_user',
    'require_roles',
    'CurrentUser',
    'TokenClaims'
]