"""
認証関連のAPIエンドポイント
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import jwt
import os

router = APIRouter()

# パスワードハッシュ化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT設定
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2スキーム
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# リクエスト/レスポンスモデル
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    created_at: datetime

# 簡易的なインメモリストレージ（本番環境ではDBを使用）
users_db = {}
user_id_counter = 1

def verify_password(plain_password, hashed_password):
    """パスワード検証"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """パスワードハッシュ化"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWTトークン生成"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """現在のユーザー取得"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        user = users_db.get(email)
        if user is None:
            raise credentials_exception
        return user
    except jwt.PyJWTError:
        raise credentials_exception

@router.post("/register", response_model=UserResponse)
async def register(user: UserRegister):
    """ユーザー登録"""
    global user_id_counter
    
    # メールアドレスの重複チェック
    if user.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # ユーザー作成
    hashed_password = get_password_hash(user.password)
    new_user = {
        "id": user_id_counter,
        "email": user.email,
        "name": user.name,
        "hashed_password": hashed_password,
        "created_at": datetime.utcnow()
    }
    users_db[user.email] = new_user
    user_id_counter += 1
    
    return UserResponse(
        id=new_user["id"],
        email=new_user["email"],
        name=new_user["name"],
        created_at=new_user["created_at"]
    )

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """ログイン"""
    user = users_db.get(form_data.username)  # username field contains email
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # トークン生成
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"]
        }
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """現在のユーザー情報取得"""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        created_at=current_user["created_at"]
    )

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """ログアウト"""
    # JWTトークンの場合、クライアント側でトークンを削除するだけで良い
    # サーバー側でブラックリスト管理する場合はここに実装
    return {"message": "Successfully logged out"}

@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """トークンリフレッシュ"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user["email"]}, expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        user={
            "id": current_user["id"],
            "email": current_user["email"],
            "name": current_user["name"]
        }
    )