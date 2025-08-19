"""
認証関連のAPIエンドポイント（JSONベース、BaseResponse統一）
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import jwt
import os

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# 統一レスポンスモデル
class BaseResponse(BaseModel):
    """統一レスポンス形式"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None

# リクエストモデル
class UserLogin(BaseModel):
    """JSONベースのログインリクエスト"""
    email: EmailStr
    password: str

@router.post("/login", response_model=BaseResponse)
async def login(user_login: UserLogin):
    """ログイン（JSONベース、BaseResponse形式）"""
    # 簡易認証（本番環境では適切な認証を実装）
    if user_login.email == "admin@example.com" and user_login.password == "admin":
        # access_tokenキーで統一
        return BaseResponse(
            success=True,
            data={
                "access_token": "dummy-token-12345",
                "token_type": "bearer",
                "user": {
                    "id": "1",
                    "email": user_login.email,
                    "name": "Admin User"
                }
            },
            message="Login successful"
        )
    
    return BaseResponse(
        success=False,
        error="Incorrect email or password"
    )
