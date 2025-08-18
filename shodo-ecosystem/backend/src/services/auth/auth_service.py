"""
認証サービス
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets
import hashlib

from ...models.models import User, Session, APIKey
from ...core.security import get_password_hash, verify_password, JWTManager
from ...schemas.auth import UserCreate, UserLogin, TokenResponse

class AuthService:
    """認証サービスクラス"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def register_user(self, user_data: UserCreate) -> User:
        """ユーザー登録"""
        # 既存ユーザーチェック
        result = await self.db.execute(
            select(User).where(
                (User.username == user_data.username) | 
                (User.email == user_data.email)
            )
        )
        if result.scalar_one_or_none():
            raise ValueError("User already exists")
        
        # ユーザー作成
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password)
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def authenticate_user(self, login_data: UserLogin) -> Optional[TokenResponse]:
        """ユーザー認証"""
        result = await self.db.execute(
            select(User).where(User.username == login_data.username)
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(login_data.password, user.password_hash):
            return None
        
        # トークン生成
        access_token = JWTManager.create_access_token(
            data={
                "sub": user.id,
                "username": user.username,
                "roles": ["user", "admin"] if user.is_superuser else ["user"]
            }
        )
        
        # セッション作成
        session = Session(
            user_id=user.id,
            token=access_token,
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )
        self.db.add(session)
        await self.db.commit()
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=1800
        )
    
    async def create_api_key(self, user_id: str, name: str, service: str) -> str:
        """APIキー生成"""
        api_key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        api_key_obj = APIKey(
            user_id=user_id,
            name=name,
            service=service,
            key_hash=key_hash,
            expires_at=datetime.utcnow() + timedelta(days=365)
        )
        self.db.add(api_key_obj)
        await self.db.commit()
        
        return api_key
    
    async def revoke_api_key(self, key_id: str) -> bool:
        """APIキー無効化"""
        result = await self.db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()
        
        if api_key:
            api_key.is_active = False
            await self.db.commit()
            return True
        return False
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """ユーザー取得"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_user_password(self, user_id: str, new_password: str) -> bool:
        """パスワード更新"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            user.password_hash = get_password_hash(new_password)
            user.updated_at = datetime.utcnow()
            await self.db.commit()
            return True
        return False