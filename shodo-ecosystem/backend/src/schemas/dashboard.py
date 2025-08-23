"""
ダッシュボード関連スキーマ
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ServiceStatus(str, Enum):
    """サービスステータス"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING = "pending"

class ServiceInfo(BaseModel):
    """サービス情報"""
    id: str = Field(..., description="サービスID")
    name: str = Field(..., description="サービス名")
    status: ServiceStatus = Field(..., description="ステータス")
    icon: Optional[str] = Field(default=None, description="アイコンURL")
    connected_at: Optional[datetime] = Field(default=None, description="接続日時")
    last_sync: Optional[datetime] = Field(default=None, description="最終同期日時")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="メタデータ")

class DashboardStats(BaseModel):
    """ダッシュボード統計"""
    total_services: int = Field(default=0, description="総サービス数")
    connected_services: int = Field(default=0, description="接続済みサービス数")
    total_operations: int = Field(default=0, description="総操作数")
    today_operations: int = Field(default=0, description="本日の操作数")
    api_calls_saved: int = Field(default=0, description="節約されたAPIコール数")
    cost_saved: float = Field(default=0.0, description="節約されたコスト")

class ServiceMetrics(BaseModel):
    """サービスメトリクス"""
    service_id: str = Field(..., description="サービスID")
    request_count: int = Field(default=0, description="リクエスト数")
    error_count: int = Field(default=0, description="エラー数")
    average_response_time: float = Field(default=0.0, description="平均レスポンス時間")
    uptime_percentage: float = Field(default=100.0, description="稼働率")