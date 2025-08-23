"""
認証システムのユニットテスト
"""

import pytest
from datetime import datetime, timedelta

from src.core.security import (
    get_password_hash,
    verify_password,
    JWTManager,
    generate_api_key,
    verify_api_key
)
from src.models.models import User
from src.services.auth.auth_service import AuthService
from src.schemas.auth import UserCreate, UserLogin

@pytest.mark.unit
class TestPasswordHashing:
    """パスワードハッシュ化テスト"""
    
    def test_password_hash(self):
        """パスワードハッシュ化の検証"""
        password = "test_password123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)
    
    def test_different_hashes(self):
        """同じパスワードでも異なるハッシュが生成されることを確認"""
        password = "test_password123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

@pytest.mark.unit
class TestJWTManager:
    """JWT管理テスト"""
    
    def test_create_access_token(self):
        """アクセストークン作成テスト"""
        data = {
            "sub": "user123",
            "username": "testuser",
            "roles": ["user"]
        }
        
        token = JWTManager.create_access_token(data)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_token_expiration(self):
        """トークン有効期限テスト"""
        data = {"sub": "user123"}
        
        # 短い有効期限でトークン作成
        token = JWTManager.create_access_token(
            data,
            expires_delta=timedelta(seconds=1)
        )
        
        # トークンが作成されることを確認
        assert token is not None

@pytest.mark.unit
class TestAPIKey:
    """APIキーテスト"""
    
    def test_generate_api_key(self):
        """APIキー生成テスト"""
        key = generate_api_key()
        
        assert key is not None
        assert isinstance(key, str)
        assert len(key) > 30
    
    def test_verify_api_key(self):
        """APIキー検証テスト"""
        import hashlib
        
        key = generate_api_key()
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        assert verify_api_key(key, key_hash)
        assert not verify_api_key("wrong_key", key_hash)

@pytest.mark.unit
@pytest.mark.asyncio
class TestAuthService:
    """認証サービステスト"""
    
    async def test_register_user(self, db_session):
        """ユーザー登録テスト"""
        auth_service = AuthService(db_session)
        
        user_data = UserCreate(
            username="newuser",
            email="newuser@example.com",
            password="password123"
        )
        
        user = await auth_service.register_user(user_data)
        
        assert user is not None
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.password_hash != "password123"
    
    async def test_duplicate_user_registration(self, db_session):
        """重複ユーザー登録テスト"""
        auth_service = AuthService(db_session)
        
        user_data = UserCreate(
            username="duplicate",
            email="duplicate@example.com",
            password="password123"
        )
        
        # 最初の登録は成功
        await auth_service.register_user(user_data)
        
        # 2回目の登録は失敗
        with pytest.raises(ValueError, match="User already exists"):
            await auth_service.register_user(user_data)
    
    async def test_authenticate_user(self, db_session):
        """ユーザー認証テスト"""
        auth_service = AuthService(db_session)
        
        # ユーザー登録
        user_data = UserCreate(
            username="authuser",
            email="authuser@example.com",
            password="password123"
        )
        await auth_service.register_user(user_data)
        
        # 正しい認証情報でログイン
        login_data = UserLogin(
            username="authuser",
            password="password123"
        )
        token_response = await auth_service.authenticate_user(login_data)
        
        assert token_response is not None
        assert token_response.access_token is not None
        assert token_response.token_type == "bearer"
    
    async def test_authenticate_with_wrong_password(self, db_session):
        """間違ったパスワードでの認証テスト"""
        auth_service = AuthService(db_session)
        
        # ユーザー登録
        user_data = UserCreate(
            username="wrongpass",
            email="wrongpass@example.com",
            password="correctpassword"
        )
        await auth_service.register_user(user_data)
        
        # 間違ったパスワードでログイン
        login_data = UserLogin(
            username="wrongpass",
            password="wrongpassword"
        )
        token_response = await auth_service.authenticate_user(login_data)
        
        assert token_response is None