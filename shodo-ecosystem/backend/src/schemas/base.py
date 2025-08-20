"""
基本レスポンススキーマ - API契約の一貫性
全APIエンドポイントで使用される統一レスポンス形式
"""

from typing import TypeVar, Generic, Optional, Any, List
from pydantic import BaseModel
from datetime import datetime

T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    """
    統一APIレスポンス形式
    全エンドポイントがこの形式に準拠
    """
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
    correlation_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class PaginatedResponse(BaseModel, Generic[T]):
    """ページネーション対応レスポンス"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

class ErrorDetail(BaseModel):
    """エラー詳細情報"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Any] = None

class ErrorResponse(BaseModel):
    """エラーレスポンス形式"""
    success: bool = False
    error: str
    error_details: Optional[List[ErrorDetail]] = None
    timestamp: datetime = datetime.utcnow()
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None

# 標準エラーコード
class ErrorCode:
    """標準エラーコード定義"""
    AUTHENTICATION_FAILED = "AUTH_001"
    AUTHORIZATION_FAILED = "AUTH_002"
    TOKEN_EXPIRED = "AUTH_003"
    TOKEN_INVALID = "AUTH_004"
    RATE_LIMIT_EXCEEDED = "RATE_001"
    VALIDATION_ERROR = "VAL_001"
    RESOURCE_NOT_FOUND = "RES_001"
    RESOURCE_CONFLICT = "RES_002"
    INTERNAL_ERROR = "INT_001"
    SERVICE_UNAVAILABLE = "SVC_001"