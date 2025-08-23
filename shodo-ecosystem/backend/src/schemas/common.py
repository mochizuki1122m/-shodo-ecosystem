"""
共通スキーマ定義
"""

from typing import TypeVar, Generic, Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

T = TypeVar('T')

class StatusEnum(str, Enum):
    """ステータス列挙型"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BaseResponse(BaseModel, Generic[T]):
    """基本レスポンス"""
    success: bool = Field(default=True, description="処理成功フラグ")
    data: Optional[T] = Field(default=None, description="レスポンスデータ")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    request_id: Optional[str] = Field(default=None, description="リクエストID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="タイムスタンプ")

class PaginationParams(BaseModel):
    """ページネーションパラメータ"""
    page: int = Field(default=1, ge=1, description="ページ番号")
    limit: int = Field(default=20, ge=1, le=100, description="1ページあたりの件数")
    sort_by: Optional[str] = Field(default=None, description="ソートフィールド")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="ソート順")

class PaginatedResponse(BaseModel, Generic[T]):
    """ページネーションレスポンス"""
    items: List[T] = Field(default_factory=list, description="アイテムリスト")
    total: int = Field(default=0, description="総件数")
    page: int = Field(default=1, description="現在のページ")
    pages: int = Field(default=1, description="総ページ数")
    limit: int = Field(default=20, description="1ページあたりの件数")

class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    error: str = Field(..., description="エラーメッセージ")
    detail: Optional[Any] = Field(default=None, description="詳細情報")
    status_code: int = Field(..., description="HTTPステータスコード")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="タイムスタンプ")

class HealthCheck(BaseModel):
    """ヘルスチェック用の簡易スキーマ"""
    status: str = Field(..., description="overall/healthy/partial/degraded など")
    version: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Optional[dict] = None