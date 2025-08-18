"""
共通スキーマ定義
"""

from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

T = TypeVar('T')

class StatusEnum(str, Enum):
    """ステータス列挙型"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ErrorLevel(str, Enum):
    """エラーレベル"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class BaseResponse(BaseModel, Generic[T]):
    """基本レスポンス型"""
    success: bool = Field(..., description="処理の成功/失敗")
    data: Optional[T] = Field(None, description="レスポンスデータ")
    error: Optional[str] = Field(None, description="エラーメッセージ")
    error_code: Optional[str] = Field(None, description="エラーコード")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="タイムスタンプ")
    request_id: Optional[str] = Field(None, description="リクエストID")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class PaginationParams(BaseModel):
    """ページネーションパラメータ"""
    page: int = Field(1, ge=1, description="ページ番号")
    per_page: int = Field(20, ge=1, le=100, description="1ページあたりの件数")
    sort_by: Optional[str] = Field(None, description="ソートフィールド")
    sort_order: str = Field("desc", regex="^(asc|desc)$", description="ソート順")

class PaginatedResponse(BaseModel, Generic[T]):
    """ページネーションレスポンス"""
    items: List[T] = Field(..., description="アイテムリスト")
    total: int = Field(..., description="総件数")
    page: int = Field(..., description="現在のページ")
    per_page: int = Field(..., description="1ページあたりの件数")
    pages: int = Field(..., description="総ページ数")
    has_next: bool = Field(..., description="次ページの有無")
    has_prev: bool = Field(..., description="前ページの有無")

class HealthCheck(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str = Field(..., description="サービスステータス")
    version: str = Field(..., description="APIバージョン")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, bool] = Field(..., description="各サービスの状態")
    
class ValidationError(BaseModel):
    """バリデーションエラー"""
    field: str = Field(..., description="エラーフィールド")
    message: str = Field(..., description="エラーメッセージ")
    code: str = Field(..., description="エラーコード")

class BatchOperationResult(BaseModel):
    """バッチ操作結果"""
    total: int = Field(..., description="総処理数")
    succeeded: int = Field(..., description="成功数")
    failed: int = Field(..., description="失敗数")
    errors: List[ValidationError] = Field(default_factory=list, description="エラーリスト")

class AuditLog(BaseModel):
    """監査ログ"""
    id: str = Field(..., description="ログID")
    user_id: str = Field(..., description="ユーザーID")
    action: str = Field(..., description="アクション")
    resource_type: str = Field(..., description="リソースタイプ")
    resource_id: str = Field(..., description="リソースID")
    changes: Optional[Dict[str, Any]] = Field(None, description="変更内容")
    ip_address: str = Field(..., description="IPアドレス")
    user_agent: str = Field(..., description="ユーザーエージェント")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class SessionInfo(BaseModel):
    """セッション情報"""
    session_id: str = Field(..., description="セッションID")
    user_id: str = Field(..., description="ユーザーID")
    created_at: datetime = Field(..., description="作成日時")
    expires_at: datetime = Field(..., description="有効期限")
    ip_address: str = Field(..., description="IPアドレス")
    user_agent: str = Field(..., description="ユーザーエージェント")
    is_active: bool = Field(True, description="アクティブ状態")