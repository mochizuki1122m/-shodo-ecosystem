"""
認証関連のスキーマ定義
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum

class UserRole(str, Enum):
    """ユーザーロール"""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    DEVELOPER = "developer"

class LoginRequest(BaseModel):
    """ログインリクエスト"""
    email: EmailStr = Field(..., description="メールアドレス")
    password: str = Field(..., min_length=8, description="パスワード")
    remember_me: bool = Field(False, description="ログイン状態を保持")
    
class LoginResponse(BaseModel):
    """ログインレスポンス"""
    access_token: str = Field(..., description="アクセストークン")
    refresh_token: Optional[str] = Field(None, description="リフレッシュトークン")
    token_type: str = Field("Bearer", description="トークンタイプ")
    expires_in: int = Field(..., description="有効期限（秒）")
    user: "UserInfo" = Field(..., description="ユーザー情報")
    
class RegisterRequest(BaseModel):
    """ユーザー登録リクエスト"""
    email: EmailStr = Field(..., description="メールアドレス")
    password: str = Field(..., min_length=8, max_length=128, description="パスワード")
    confirm_password: str = Field(..., description="パスワード確認")
    username: str = Field(..., min_length=3, max_length=50, description="ユーザー名")
    full_name: Optional[str] = Field(None, max_length=100, description="フルネーム")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """パスワードの一致確認"""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('password')
    def password_strength(cls, v):
        """パスワード強度の検証"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserInfo(BaseModel):
    """ユーザー情報"""
    user_id: str = Field(..., description="ユーザーID")
    email: EmailStr = Field(..., description="メールアドレス")
    username: str = Field(..., description="ユーザー名")
    full_name: Optional[str] = Field(None, description="フルネーム")
    roles: List[UserRole] = Field(default_factory=list, description="ロール")
    is_active: bool = Field(True, description="アクティブ状態")
    is_verified: bool = Field(False, description="メール確認済み")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")
    last_login: Optional[datetime] = Field(None, description="最終ログイン日時")
    
class PasswordResetRequest(BaseModel):
    """パスワードリセットリクエスト"""
    email: EmailStr = Field(..., description="メールアドレス")
    
class PasswordResetConfirm(BaseModel):
    """パスワードリセット確認"""
    token: str = Field(..., description="リセットトークン")
    new_password: str = Field(..., min_length=8, max_length=128, description="新しいパスワード")
    confirm_password: str = Field(..., description="パスワード確認")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """パスワードの一致確認"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class ChangePasswordRequest(BaseModel):
    """パスワード変更リクエスト"""
    current_password: str = Field(..., description="現在のパスワード")
    new_password: str = Field(..., min_length=8, max_length=128, description="新しいパスワード")
    confirm_password: str = Field(..., description="パスワード確認")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """パスワードの一致確認"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class TokenRefreshRequest(BaseModel):
    """トークンリフレッシュリクエスト"""
    refresh_token: str = Field(..., description="リフレッシュトークン")
    
class TokenRefreshResponse(BaseModel):
    """トークンリフレッシュレスポンス"""
    access_token: str = Field(..., description="新しいアクセストークン")
    refresh_token: Optional[str] = Field(None, description="新しいリフレッシュトークン")
    token_type: str = Field("Bearer", description="トークンタイプ")
    expires_in: int = Field(..., description="有効期限（秒）")

# 循環参照の解決
LoginResponse.model_rebuild()