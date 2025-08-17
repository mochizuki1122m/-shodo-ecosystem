"""
サービス接続関連のデータベースモデル
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel

class ServiceConnection(BaseModel):
    """
    サービス接続モデル
    ユーザーと外部サービスの接続情報を管理
    """
    __tablename__ = "service_connections"
    
    # 関連
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # サービス情報
    service_type = Column(String(50), nullable=False, index=True)
    service_name = Column(String(255), nullable=False)
    service_account_id = Column(String(255), nullable=True)  # 外部サービスのアカウントID
    service_account_name = Column(String(255), nullable=True)
    
    # 接続情報
    connection_status = Column(String(50), default="active", nullable=False)  # active, inactive, error
    connected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_sync_at = Column(DateTime, nullable=True)
    
    # 設定
    sync_enabled = Column(Boolean, default=True, nullable=False)
    sync_frequency = Column(String(50), default="hourly", nullable=False)  # realtime, hourly, daily
    
    # Webhook設定
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    webhook_events = Column(JSON, default=list, nullable=False)
    
    # メタデータ
    settings = Column(JSON, default=dict, nullable=False)
    capabilities = Column(JSON, default=list, nullable=False)  # 利用可能な機能
    limits = Column(JSON, default=dict, nullable=False)  # レート制限など
    
    # エラー情報
    last_error = Column(Text, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    
    # リレーション
    user = relationship("User", back_populates="service_connections")
    api_keys = relationship("APIKey", back_populates="service_connection", cascade="all, delete-orphan")
    
    # インデックス
    __table_args__ = (
        Index("idx_connections_user_service", "user_id", "service_type"),
        Index("idx_connections_status", "connection_status"),
    )
    
    def is_active(self) -> bool:
        """接続がアクティブかチェック"""
        return self.connection_status == "active"
    
    def needs_sync(self) -> bool:
        """同期が必要かチェック"""
        if not self.sync_enabled or not self.is_active():
            return False
        
        if not self.last_sync_at:
            return True
        
        # 同期頻度に基づいてチェック
        time_since_sync = datetime.utcnow() - self.last_sync_at
        
        if self.sync_frequency == "realtime":
            return False  # リアルタイムはWebhookで処理
        elif self.sync_frequency == "hourly":
            return time_since_sync.total_seconds() > 3600
        elif self.sync_frequency == "daily":
            return time_since_sync.total_seconds() > 86400
        
        return False
    
    def record_sync(self):
        """同期を記録"""
        self.last_sync_at = datetime.utcnow()
        self.error_count = 0  # 成功したらエラーカウントをリセット
    
    def record_error(self, error_message: str):
        """エラーを記録"""
        self.last_error = error_message
        self.last_error_at = datetime.utcnow()
        self.error_count += 1
        
        # エラーが多い場合は接続を無効化
        if self.error_count >= 10:
            self.connection_status = "error"