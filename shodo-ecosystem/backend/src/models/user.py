"""
ユーザー関連のデータベースモデル
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship
from .base import BaseModel

class User(BaseModel):
    """
    ユーザーモデル
    """
    __tablename__ = "users"
    
    # 基本情報
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    
    # 認証情報
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # 権限
    role = Column(String(50), default="user", nullable=False)  # user, admin, superadmin
    permissions = Column(JSON, default=list, nullable=False)
    
    # プロファイル
    avatar_url = Column(String(500), nullable=True)
    preferences = Column(JSON, default=dict, nullable=False)
    
    # セキュリティ
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    
    # 2FA
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(255), nullable=True)
    
    # リレーション
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    service_connections = relationship("ServiceConnection", back_populates="user", cascade="all, delete-orphan")
    
    # インデックス
    __table_args__ = (
        Index("idx_users_email_active", "email", "is_active"),
    )
    
    def is_locked(self) -> bool:
        """アカウントがロックされているかチェック"""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until
    
    def increment_failed_login(self):
        """ログイン失敗回数をインクリメント"""
        self.failed_login_attempts += 1
        
        # 5回失敗したら30分ロック
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow().replace(minute=datetime.utcnow().minute + 30)
    
    def reset_failed_login(self):
        """ログイン失敗回数をリセット"""
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def update_last_login(self, ip_address: str):
        """最終ログイン情報を更新"""
        self.last_login_at = datetime.utcnow()
        self.last_login_ip = ip_address
        self.reset_failed_login()

class UserSession(BaseModel):
    """
    ユーザーセッションモデル
    """
    __tablename__ = "user_sessions"
    
    # 関連
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # セッション情報
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=True, index=True)
    
    # デバイス情報
    device_id = Column(String(100), nullable=True)
    device_name = Column(String(255), nullable=True)
    device_type = Column(String(50), nullable=True)  # web, mobile, desktop
    
    # ネットワーク情報
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # 有効期限
    expires_at = Column(DateTime, nullable=False, index=True)
    refresh_expires_at = Column(DateTime, nullable=True)
    
    # アクティビティ
    last_activity_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # リレーション
    user = relationship("User", back_populates="sessions")
    
    # インデックス
    __table_args__ = (
        Index("idx_sessions_user_active", "user_id", "is_active"),
        Index("idx_sessions_expires", "expires_at"),
    )
    
    def is_expired(self) -> bool:
        """セッションが期限切れかチェック"""
        return datetime.utcnow() > self.expires_at
    
    def is_refresh_expired(self) -> bool:
        """リフレッシュトークンが期限切れかチェック"""
        if not self.refresh_expires_at:
            return True
        return datetime.utcnow() > self.refresh_expires_at
    
    def update_activity(self):
        """アクティビティを更新"""
        self.last_activity_at = datetime.utcnow()