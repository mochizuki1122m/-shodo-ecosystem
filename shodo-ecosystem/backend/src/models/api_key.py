"""
APIキー関連のデータベースモデル
"""

from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text, ForeignKey, Integer, Index, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum
from .base import BaseModel

class ServiceType(str, Enum):
    """サービスタイプ"""
    SHOPIFY = "shopify"
    STRIPE = "stripe"
    GMAIL = "gmail"
    SLACK = "slack"
    NOTION = "notion"
    GITHUB = "github"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    ZENDESK = "zendesk"
    MAILCHIMP = "mailchimp"

class APIKeyStatus(str, Enum):
    """APIキーステータス"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PENDING = "pending"
    ERROR = "error"

class APIKey(BaseModel):
    """
    APIキーモデル
    暗号化されたAPIキーと関連メタデータを保存
    """
    __tablename__ = "api_keys"
    
    # 基本情報
    key_id = Column(String(32), unique=True, nullable=False, index=True)
    service = Column(SQLEnum(ServiceType), nullable=False, index=True)
    status = Column(SQLEnum(APIKeyStatus), default=APIKeyStatus.ACTIVE, nullable=False)
    
    # 暗号化データ
    encrypted_key = Column(Text, nullable=False)
    encrypted_refresh_token = Column(Text, nullable=True)
    
    # 認証情報
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    service_connection_id = Column(String(36), ForeignKey("service_connections.id"), nullable=True)
    
    # 有効期限
    expires_at = Column(DateTime, nullable=True, index=True)
    last_refreshed_at = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, default=True, nullable=False)
    
    # 権限とメタデータ
    permissions = Column(JSON, default=list, nullable=False)
    extra_metadata = Column("metadata", JSON, default=dict, nullable=False)
    
    # OAuth情報
    oauth_state = Column(String(255), nullable=True)
    oauth_code_verifier = Column(String(255), nullable=True)  # PKCE用
    
    # 使用統計
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    # エラー情報
    error_message = Column(Text, nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    last_error_at = Column(DateTime, nullable=True)
    
    # リレーション
    user = relationship("User", back_populates="api_keys")
    service_connection = relationship("ServiceConnection", back_populates="api_keys")
    audit_logs = relationship("APIKeyAuditLog", back_populates="api_key", cascade="all, delete-orphan")
    usage_logs = relationship("APIKeyUsage", back_populates="api_key", cascade="all, delete-orphan")
    
    # インデックス
    __table_args__ = (
        Index("idx_api_keys_user_service", "user_id", "service"),
        Index("idx_api_keys_status_expires", "status", "expires_at"),
    )
    
    def is_expired(self) -> bool:
        """有効期限切れかチェック"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def needs_refresh(self) -> bool:
        """リフレッシュが必要かチェック"""
        if not self.auto_renew or not self.expires_at:
            return False
        
        # 有効期限の10%前にリフレッシュ
        if self.last_refreshed_at:
            total_duration = (self.expires_at - self.last_refreshed_at).total_seconds()
            remaining = (self.expires_at - datetime.utcnow()).total_seconds()
            return remaining < (total_duration * 0.1)
        
        return self.is_expired()
    
    def increment_usage(self):
        """使用回数をインクリメント"""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
    
    def record_error(self, error_message: str):
        """エラーを記録"""
        self.error_count += 1
        self.error_message = error_message
        self.last_error_at = datetime.utcnow()
        
        # エラーが多い場合はステータスを変更
        if self.error_count >= 5:
            self.status = APIKeyStatus.ERROR

class APIKeyAuditLog(BaseModel):
    """
    APIキー監査ログ
    すべてのAPIキー操作を記録
    """
    __tablename__ = "api_key_audit_logs"
    
    # 関連
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # 操作情報
    action = Column(String(50), nullable=False, index=True)  # create, read, update, delete, refresh, revoke
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # 詳細
    details = Column(JSON, default=dict, nullable=False)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # リレーション
    api_key = relationship("APIKey", back_populates="audit_logs")
    user = relationship("User")
    
    # インデックス
    __table_args__ = (
        Index("idx_audit_logs_api_key_action", "api_key_id", "action"),
        Index("idx_audit_logs_created", "created_at"),
    )

class APIKeyUsage(BaseModel):
    """
    APIキー使用ログ
    APIキーの使用状況を詳細に記録
    """
    __tablename__ = "api_key_usage"
    
    # 関連
    api_key_id = Column(String(36), ForeignKey("api_keys.id"), nullable=False, index=True)
    
    # 使用情報
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=True)
    
    # パフォーマンス
    response_time_ms = Column(Integer, nullable=True)
    request_size_bytes = Column(Integer, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)
    
    # コスト（API利用料金追跡用）
    estimated_cost = Column(JSON, nullable=True)  # {"amount": 0.01, "currency": "USD"}
    
    # エラー情報
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # メタデータ
    extra_metadata = Column("metadata", JSON, default=dict, nullable=False)
    
    # リレーション
    api_key = relationship("APIKey", back_populates="usage_logs")
    
    # インデックス
    __table_args__ = (
        Index("idx_usage_api_key_created", "api_key_id", "created_at"),
        Index("idx_usage_endpoint", "endpoint"),
    )