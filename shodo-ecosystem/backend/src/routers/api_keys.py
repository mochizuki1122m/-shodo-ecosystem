"""
APIキー管理エンドポイント
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from ..models.base import get_db
from ..models.api_key import APIKey, APIKeyStatus, ServiceType
from ..models.user import User
from ..services.auth.api_key_manager_db import DatabaseAPIKeyManager
from ..services.auth.auth_service import get_current_user
from ..tasks.api_key_tasks import rotate_api_key, check_api_health

router = APIRouter(prefix="/api/keys", tags=["API Keys"])

# リクエスト/レスポンスモデル
class OAuthInitiateRequest(BaseModel):
    service: str
    redirect_uri: str
    scopes: Optional[List[str]] = None

class OAuthCallbackRequest(BaseModel):
    service: str
    code: str
    state: str

class DirectAcquisitionRequest(BaseModel):
    service: str
    credentials: Dict[str, str]
    name: Optional[str] = None
    auto_renew: bool = True

class APIKeyResponse(BaseModel):
    id: str
    key_id: str
    service: str
    name: Optional[str]
    status: str
    created_at: datetime
    expires_at: Optional[datetime]
    permissions: List[str]
    auto_renew: bool

class UsageStatisticsResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    average_response_time_ms: Optional[float]
    last_used_at: Optional[datetime]
    most_used_endpoints: List[Dict[str, Any]]

@router.post("/oauth/initiate")
async def initiate_oauth_flow(
    request: OAuthInitiateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """OAuth認証フローを開始"""
    try:
        service = ServiceType[request.service.upper()]
    except KeyError:
        raise HTTPException(400, f"Invalid service type: {request.service}")
    
    manager = DatabaseAPIKeyManager(db)
    
    # ステートトークンを生成
    import secrets
    state = secrets.token_urlsafe(32)
    
    # セッションにステートを保存（実際の実装ではRedisなどを使用）
    # ここでは簡略化のため、レスポンスに含める
    
    auth_url = await manager.initiate_oauth_flow(
        service=service,
        state=state,
        additional_params={
            "redirect_uri": request.redirect_uri,
            "scopes": request.scopes
        }
    )
    
    return {
        "auth_url": auth_url,
        "state": state
    }

@router.post("/oauth/callback")
async def handle_oauth_callback(
    request: OAuthCallbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIKeyResponse:
    """OAuthコールバックを処理してトークンを交換"""
    try:
        service = ServiceType[request.service.upper()]
    except KeyError:
        raise HTTPException(400, f"Invalid service type: {request.service}")
    
    manager = DatabaseAPIKeyManager(db)
    
    # ステートを検証（実際の実装では保存されたステートと比較）
    if not request.state:
        raise HTTPException(400, "Invalid state parameter")
    
    try:
        config = await manager.exchange_code_for_token(
            service=service,
            code=request.code
        )
        
        # APIキーを保存
        await manager._persist_key(config, current_user.id)
        
        # APIキーを取得して返す
        result = await db.execute(
            select(APIKey).where(
                and_(
                    APIKey.user_id == current_user.id,
                    APIKey.service == service,
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            ).order_by(APIKey.created_at.desc())
        )
        api_key = result.scalars().first()
        
        if not api_key:
            raise HTTPException(500, "Failed to save API key")
        
        return APIKeyResponse(
            id=api_key.id,
            key_id=api_key.key_id,
            service=api_key.service.value,
            name=api_key.name,
            status=api_key.status.value,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            permissions=api_key.permissions or [],
            auto_renew=api_key.auto_renew
        )
        
    except Exception as e:
        raise HTTPException(400, f"Failed to exchange token: {str(e)}")

@router.post("/acquire")
async def acquire_api_key(
    request: DirectAcquisitionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIKeyResponse:
    """直接APIキーを取得"""
    try:
        service = ServiceType[request.service.upper()]
    except KeyError:
        raise HTTPException(400, f"Invalid service type: {request.service}")
    
    # 必須フィールドの検証
    required_fields = {
        ServiceType.STRIPE: ["api_key"],
        ServiceType.SHOPIFY: ["api_key", "shop_domain"],
        ServiceType.GITHUB: ["personal_access_token"]
    }
    
    if service in required_fields:
        missing = [f for f in required_fields[service] if f not in request.credentials]
        if missing:
            raise HTTPException(400, f"Missing required credentials: {', '.join(missing)}")
    
    manager = DatabaseAPIKeyManager(db)
    
    try:
        config = await manager.auto_acquire_key(
            service=service,
            credentials=request.credentials
        )
        
        # カスタム名を設定
        if request.name:
            config.name = request.name
        config.auto_renew = request.auto_renew
        
        # APIキーを保存
        await manager._persist_key(config, current_user.id)
        
        # 保存されたキーを取得
        result = await db.execute(
            select(APIKey).where(
                and_(
                    APIKey.user_id == current_user.id,
                    APIKey.service == service,
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            ).order_by(APIKey.created_at.desc())
        )
        api_key = result.scalars().first()
        
        if not api_key:
            raise HTTPException(500, "Failed to save API key")
        
        return APIKeyResponse(
            id=api_key.id,
            key_id=api_key.key_id,
            service=api_key.service.value,
            name=api_key.name,
            status=api_key.status.value,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            permissions=api_key.permissions or [],
            auto_renew=api_key.auto_renew
        )
        
    except Exception as e:
        raise HTTPException(400, f"Failed to acquire API key: {str(e)}")

@router.get("")
async def list_api_keys(
    service: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[APIKeyResponse]:
    """ユーザーのAPIキー一覧を取得"""
    query = select(APIKey).where(APIKey.user_id == current_user.id)
    
    if service:
        try:
            service_type = ServiceType[service.upper()]
            query = query.where(APIKey.service == service_type)
        except KeyError:
            raise HTTPException(400, f"Invalid service type: {service}")
    
    if status:
        try:
            key_status = APIKeyStatus[status.upper()]
            query = query.where(APIKey.status == key_status)
        except KeyError:
            raise HTTPException(400, f"Invalid status: {status}")
    
    result = await db.execute(query.order_by(APIKey.created_at.desc()))
    api_keys = result.scalars().all()
    
    return [
        APIKeyResponse(
            id=key.id,
            key_id=key.key_id,
            service=key.service.value,
            name=key.name,
            status=key.status.value,
            created_at=key.created_at,
            expires_at=key.expires_at,
            permissions=key.permissions or [],
            auto_renew=key.auto_renew
        )
        for key in api_keys
    ]

@router.get("/{key_id}")
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """特定のAPIキーの詳細を取得"""
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.key_id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(404, "API key not found")
    
    # 期限切れチェック
    requires_refresh = False
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        requires_refresh = True
    
    return {
        "id": api_key.id,
        "key_id": api_key.key_id,
        "service": api_key.service.value,
        "name": api_key.name,
        "status": api_key.status.value,
        "created_at": api_key.created_at,
        "expires_at": api_key.expires_at,
        "permissions": api_key.permissions or [],
        "auto_renew": api_key.auto_renew,
        "requires_refresh": requires_refresh,
        "metadata": api_key.metadata or {}
    }

@router.post("/{key_id}/refresh")
async def refresh_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """APIキーを更新"""
    manager = DatabaseAPIKeyManager(db)
    
    # キーの所有権を確認
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.key_id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(404, "API key not found")
    
    try:
        await manager.refresh_key(key_id)
        
        # 更新されたキーを取得
        await db.refresh(api_key)
        
        return {
            "message": "Key refreshed successfully",
            "new_expires_at": api_key.expires_at
        }
    except Exception as e:
        raise HTTPException(400, f"Failed to refresh key: {str(e)}")

@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    reason: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """APIキーを無効化"""
    manager = DatabaseAPIKeyManager(db)
    
    try:
        await manager.revoke_key_by_id(key_id, current_user.id, reason)
        return {"message": "Key revoked successfully"}
    except Exception as e:
        raise HTTPException(400, f"Failed to revoke key: {str(e)}")

@router.post("/{key_id}/rotate")
async def rotate_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """APIキーをローテーション（バックグラウンドタスク）"""
    # キーの所有権を確認
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.key_id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(404, "API key not found")
    
    # バックグラウンドタスクを起動
    task = rotate_api_key.delay(key_id, current_user.id)
    
    return {
        "task_id": task.id,
        "status": "rotation_initiated"
    }

@router.get("/{key_id}/statistics")
async def get_key_statistics(
    key_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UsageStatisticsResponse:
    """APIキーの使用統計を取得"""
    manager = DatabaseAPIKeyManager(db)
    
    # デフォルトの期間（過去30日）
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # キーの所有権を確認
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.key_id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(404, "API key not found")
    
    stats = await manager.get_usage_statistics(
        user_id=current_user.id,
        api_key_id=api_key.id,
        start_date=start_date,
        end_date=end_date
    )
    
    return UsageStatisticsResponse(**stats)

@router.put("/{key_id}/permissions")
async def update_key_permissions(
    key_id: str,
    permissions: List[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """APIキーの権限を更新"""
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.key_id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(404, "API key not found")
    
    # 権限を更新
    api_key.permissions = permissions
    api_key.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(api_key)
    
    return {
        "key_id": api_key.key_id,
        "permissions": api_key.permissions
    }

@router.post("/{key_id}/usage")
async def record_usage(
    key_id: str,
    endpoint: str = Body(...),
    method: str = Body(...),
    status_code: Optional[int] = Body(None),
    response_time_ms: Optional[int] = Body(None),
    error_message: Optional[str] = Body(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """APIキーの使用を記録"""
    manager = DatabaseAPIKeyManager(db)
    
    # キーの所有権を確認
    result = await db.execute(
        select(APIKey).where(
            and_(
                APIKey.key_id == key_id,
                APIKey.user_id == current_user.id
            )
        )
    )
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(404, "API key not found")
    
    await manager.log_usage(
        api_key_id=api_key.id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        response_time_ms=response_time_ms,
        error_message=error_message
    )
    
    return {"message": "Usage recorded successfully"}

@router.get("/health/{service}")
async def check_service_health(
    service: str,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """外部サービスのヘルスチェック"""
    task = check_api_health.delay(service)
    result = task.get(timeout=10)
    
    return result