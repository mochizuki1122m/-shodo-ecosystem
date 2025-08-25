"""
認証関連のAPIエンドポイント
SSOT準拠、BaseResponse統一、JWT標準化実装
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import uuid
import hashlib
from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel, EmailStr, Field, validator
from passlib.context import CryptContext
from jose import jwt
from pathlib import Path

from ...schemas.base import BaseResponse
from ...core.config import settings
from ...services.database import get_db_session
from ...middleware.auth import get_current_user, CurrentUser
from ...services.auth.refresh_manager import RefreshTokenManager
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# パスワードハッシュ設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ===== リクエスト/レスポンスモデル =====

class UserRegisterRequest(BaseModel):
    """ユーザー登録リクエスト"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    
    @validator('password')
    def validate_password(cls, v):
        """パスワード強度検証"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserLoginRequest(BaseModel):
    """ログインリクエスト"""
    email: EmailStr
    password: str
    device_fingerprint: Optional[str] = None  # デバイス識別用

class TokenResponse(BaseModel):
    """トークンレスポンス"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # 秒単位
    refresh_token: Optional[str] = None  # 将来の実装用

class RefreshRequest(BaseModel):
    """リフレッシュ用ボディ（OpenAPI整合）。Cookie優先で、未設定時に参照。"""
    refresh_token: Optional[str] = None
    
class UserResponse(BaseModel):
    """ユーザー情報レスポンス"""
    user_id: str
    email: str
    username: str
    full_name: Optional[str] = None
    roles: list[str] = []
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None

class AuthResponse(BaseModel):
    """認証成功レスポンス"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

# ===== ヘルパー関数 =====

def create_access_token(
    user_id: str,
    username: str,
    roles: list[str] = [],
    device_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None
) -> tuple[str, int]:
    """
    アクセストークン生成
    RS256署名、標準クレーム準拠
    """
    # 有効期限設定（デフォルト: 1時間）
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
    
    expires_in = int((expire - datetime.now(timezone.utc)).total_seconds())
    
    # JWT ID生成（リプレイ攻撃防止）
    jti = str(uuid.uuid4())
    
    # 標準クレーム構築
    claims = {
        "sub": user_id,  # Subject
        "username": username,
        "roles": roles,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": jti,
        "aud": getattr(settings, 'jwt_audience', 'shodo-ecosystem'),
        "iss": getattr(settings, 'jwt_issuer', 'shodo-auth'),
    }
    
    # デバイスIDがあれば追加
    if device_id:
        claims["device_id"] = device_id
    
    # トークン生成
    algorithm = getattr(settings, 'jwt_algorithm', 'HS256')
    
    if algorithm == 'RS256':
        # 本番: RS256 with private key (env value or file path)
        private_key = getattr(settings, 'jwt_private_key', None)
        if not private_key and getattr(settings, 'jwt_private_key_path', None):
            try:
                private_key = Path(settings.jwt_private_key_path).read_text(encoding='utf-8')
            except Exception:
                private_key = None
        if not private_key:
            # フォールバック
            algorithm = 'HS256'
            secret = (settings.secret_key.get_secret_value() if hasattr(settings, 'secret_key') else settings.jwt_secret_key.get_secret_value())
            token = jwt.encode(claims, secret, algorithm=algorithm)
        else:
            token = jwt.encode(claims, private_key, algorithm='RS256')
    else:
        # 開発: HS256
        secret = (settings.secret_key.get_secret_value() if hasattr(settings, 'secret_key') else settings.jwt_secret_key.get_secret_value())
        token = jwt.encode(claims, secret, algorithm='HS256')
    
    return token, expires_in

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワード検証"""
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """パスワードハッシュ化"""
    return pwd_context.hash(password)

def generate_device_fingerprint(request: Request) -> str:
    """デバイスフィンガープリント生成"""
    # User-Agent、Accept-Language、IPアドレスなどから生成
    components = [
        request.headers.get("user-agent", ""),
        request.headers.get("accept-language", ""),
        request.client.host if request.client else "",
    ]
    fingerprint_str = "|".join(components)
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:16]

# ===== APIエンドポイント =====

@router.post("/register", response_model=BaseResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def register(
    request: UserRegisterRequest,
    db = Depends(get_db_session)
):
    """
    新規ユーザー登録
    """
    try:
        # メールアドレスの重複チェック
        # TODO: 実際のDBクエリに置き換え
        
        # パスワードのハッシュ化
        _ = hash_password(request.password)  # 実DB保存実装時に使用
        
        # ユーザー作成
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        
        # TODO: 実際のDB保存処理
        user_data = UserResponse(
            user_id=user_id,
            email=request.email,
            username=request.username,
            full_name=request.full_name,
            roles=["user"],  # デフォルトロール
            is_active=True,
            created_at=created_at,
            last_login=None
        )
        
        logger.info(f"New user registered: {user_id}")
        
        return BaseResponse(
            success=True,
            data=user_data,
            message="User registered successfully"
        )
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login", response_model=BaseResponse[AuthResponse])
async def login(
    request: UserLoginRequest,
    req: Request,
    db = Depends(get_db_session)
):
    """
    ユーザーログイン
    access_tokenキーで統一されたレスポンス
    """
    try:
        # デバイスフィンガープリント生成
        device_id = request.device_fingerprint or generate_device_fingerprint(req)
        
        # TODO: 実際のDB認証処理
        # 開発用のダミー認証
        if request.email == "admin@example.com" and request.password == "admin":
            user_id = "admin-user-id"
            username = "admin"
            roles = ["admin", "user"]
        elif request.email == "user@example.com" and request.password == "password":
            user_id = "normal-user-id"
            username = "user"
            roles = ["user"]
        else:
            logger.warning(f"Failed login attempt for {request.email}")
            return BaseResponse(
                success=False,
                error="Invalid email or password",
                message="Authentication failed"
            )
        
        # アクセストークン生成
        access_token, expires_in = create_access_token(
            user_id=user_id,
            username=username,
            roles=roles,
            device_id=device_id,
            expires_delta=timedelta(minutes=30)
        )
        
        # ユーザー情報構築
        user_data = UserResponse(
            user_id=user_id,
            email=request.email,
            username=username,
            full_name="Test User" if username == "user" else "Administrator",
            roles=roles,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            last_login=datetime.now(timezone.utc)
        )
        
        # 統一レスポンス形式
        auth_data = AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_data
        )
        
        logger.info(f"User logged in: {user_id}")
        
        # HttpOnly/SameSite Cookie 設定
        from fastapi.responses import JSONResponse
        from ...core.config import settings as _settings
        refresh_mgr = RefreshTokenManager()
        # リフレッシュトークンを発行（Redis必須。開発ではRedis無しならCookie未設定）
        refresh_token_value = None
        try:
            refresh_token_value = await refresh_mgr.generate(
                user_id=user_id,
                username=username,
                roles=roles,
                device_id=device_id,
            )
        except Exception as e:
            logger.warning(f"Refresh token generation skipped: {e}")
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=BaseResponse(
                success=True,
                data=auth_data,
                message="Login successful"
            ).model_dump()
        )
        # アクセストークン（HttpOnly）
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=_settings.is_production(),
            samesite=_settings.csrf_cookie_samesite,
            max_age=expires_in,
            path="/"
        )
        # リフレッシュトークン（HttpOnly、長寿命、ローテーション）
        if refresh_token_value:
            response.set_cookie(
                key=_settings.refresh_cookie_name,
                value=refresh_token_value,
                httponly=True,
                secure=_settings.is_production(),
                samesite=_settings.csrf_cookie_samesite,
                max_age=_settings.refresh_token_ttl_days * 24 * 3600,
                path="/api/v1/auth"
            )
        # CSRFトークン（非HttpOnly）
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            key=_settings.csrf_cookie_name,
            value=csrf_token,
            httponly=False,
            secure=_settings.is_production() and _settings.csrf_cookie_secure,
            samesite=_settings.csrf_cookie_samesite,
            max_age=expires_in,
            path="/"
        )
        return response
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return BaseResponse(
            success=False,
            error=str(e),
            message="Login failed"
        )

@router.post("/logout", response_model=BaseResponse[Dict])
async def logout(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    ユーザーログアウト
    JTIをブラックリストに追加（将来実装）
    """
    try:
        # TODO: JTIをRedisブラックリストに追加
        # TODO: セッション無効化
        
        logger.info(f"User logged out: {current_user.user_id}")
        
        from fastapi.responses import JSONResponse
        from ...core.config import settings as _settings
        # すべてのリフレッシュトークンを無効化
        try:
            mgr = RefreshTokenManager()
            await mgr.revoke_all_for_user(current_user.user_id)
        except Exception as e:
            logger.warning(f"Failed to revoke refresh tokens: {e}")
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=BaseResponse(
                success=True,
                data={"user_id": current_user.user_id},
                message="Logout successful"
            ).model_dump()
        )
        # クッキー削除
        response.delete_cookie("access_token", path="/")
        response.delete_cookie(_settings.csrf_cookie_name, path="/")
        response.delete_cookie(_settings.refresh_cookie_name, path="/api/v1/auth")
        return response
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/refresh", response_model=BaseResponse[TokenResponse])
async def refresh_token(
    req: Request,
    body: RefreshRequest | None = None,
    db = Depends(get_db_session)
):
    """
    トークンリフレッシュ
    - HttpOnly Cookieのリフレッシュトークンを検証
    - ローテーションして新しいアクセストークンと新しいリフレッシュトークンを発行
    """
    try:
        from ...core.security import InputSanitizer
        mgr = RefreshTokenManager()
        cookie_name = settings.refresh_cookie_name
        token_in_cookie = req.cookies.get(cookie_name)
        token_from_body = (body.refresh_token if body else None)
        token_value = token_from_body or token_in_cookie
        payload = await mgr.validate(token_value)
        if not payload:
            return BaseResponse(
                success=False,
                error="Invalid refresh token",
                message="Authentication failed"
            )
        # 新しいアクセストークン
        access_token, expires_in = create_access_token(
            user_id=payload["user_id"],
            username=payload.get("username", f"user_{payload['user_id']}"),
            roles=payload.get("roles", ["user"]),
            device_id=payload.get("device_id"),
            expires_delta=timedelta(minutes=30)
        )
        # リフレッシュトークンをローテーション
        rotated = await mgr.rotate(token_value)
        if not rotated:
            return BaseResponse(
                success=False,
                error="Rotation failed",
                message="Authentication failed"
            )
        new_refresh, new_payload = rotated
        # レスポンス
        from fastapi.responses import JSONResponse
        resp = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=BaseResponse(
                success=True,
                data=TokenResponse(
                    access_token=access_token,
                    token_type="bearer",
                    expires_in=expires_in
                ),
                message="Token refreshed"
            ).model_dump()
        )
        # アクセストークンを更新
        resp.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=settings.is_production(),
            samesite=settings.csrf_cookie_samesite,
            max_age=expires_in,
            path="/"
        )
        # 新しいリフレッシュトークンCookie
        resp.set_cookie(
            key=cookie_name,
            value=new_refresh,
            httponly=True,
            secure=settings.is_production(),
            samesite=settings.csrf_cookie_samesite,
            max_age=settings.refresh_token_ttl_days * 24 * 3600,
            path="/api/v1/auth"
        )
        return resp
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/me", response_model=BaseResponse[UserResponse])
async def get_me(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    現在のユーザー情報取得
    """
    try:
        user_data = UserResponse(
            user_id=current_user.user_id,
            email=current_user.email,
            username=current_user.username,
            full_name=None,  # TODO: DBから取得
            roles=current_user.roles,
            is_active=current_user.is_active,
            created_at=datetime.now(timezone.utc),  # TODO: DBから取得
            last_login=datetime.now(timezone.utc)  # TODO: DBから取得
        )
        
        return BaseResponse(
            success=True,
            data=user_data,
            message="User information retrieved"
        )
        
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/verify", response_model=BaseResponse[Dict])
async def verify_token(
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    トークン検証エンドポイント
    """
    return BaseResponse(
        success=True,
        data={
            "valid": True,
            "user_id": current_user.user_id,
            "roles": current_user.roles
        },
        message="Token is valid"
    )

@router.get("/csrf", response_model=BaseResponse[Dict])
async def issue_csrf_token():
    """
    CSRFトークン発行エンドポイント
    - Double Submit Cookie 用トークンをCookieに設定
    - クライアントはヘッダ X-CSRF-Token に同値を送信
    """
    from fastapi.responses import JSONResponse
    import secrets

    token = secrets.token_urlsafe(32)

    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content=BaseResponse(
            success=True,
            data={"csrf_token": token},
            message="CSRF token issued"
        ).model_dump()
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        httponly=False,
        secure=settings.is_production() and settings.csrf_cookie_secure,
        samesite=settings.csrf_cookie_samesite,
        path="/"
    )
    return response