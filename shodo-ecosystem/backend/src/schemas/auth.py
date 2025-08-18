"""
認証関連スキーマ
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    """ユーザー作成"""
    username: str = Field(..., min_length=3, max_length=50, description="ユーザー名")
    email: EmailStr = Field(..., description="メールアドレス")
    password: str = Field(..., min_length=8, description="パスワード")

class UserLogin(BaseModel):
    """ユーザーログイン"""
    username: str = Field(..., description="ユーザー名")
    password: str = Field(..., description="パスワード")

class TokenResponse(BaseModel):
    """トークンレスポンス"""
    access_token: str = Field(..., description="アクセストークン")
    token_type: str = Field(default="bearer", description="トークンタイプ")
    expires_in: int = Field(default=1800, description="有効期限（秒）")

class UserResponse(BaseModel):
    """ユーザーレスポンス"""
    id: str = Field(..., description="ユーザーID")
    username: str = Field(..., description="ユーザー名")
    email: str = Field(..., description="メールアドレス")
    is_active: bool = Field(default=True, description="アクティブフラグ")
    created_at: datetime = Field(..., description="作成日時")