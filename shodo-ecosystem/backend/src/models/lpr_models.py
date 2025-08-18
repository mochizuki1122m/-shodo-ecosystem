"""
LPRシステムのデータベースモデル

SQLAlchemyを使用したLPR関連のテーブル定義。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, UniqueConstraint, CheckConstraint,
    func, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import uuid

Base = declarative_base()

class LPRToken(Base):
    """LPRトークンテーブル"""
    __tablename__ = "lpr_tokens"
    
    # 主キー
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti = Column(String(255), unique=True, nullable=False, index=True)
    
    # バージョン管理
    version = Column(String(10), nullable=False, default="1.0.0")
    
    # 主体情報（仮名化）
    subject_pseudonym = Column(String(64), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # 時間情報
    issued_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # デバイス情報
    device_fingerprint_hash = Column(String(64), nullable=False)
    device_metadata = Column(JSONB, nullable=True)  # 追加のデバイス情報
    
    # 権限情報
    origin_allowlist = Column(ARRAY(String), nullable=False)
    scope_allowlist = Column(JSONB, nullable=False)  # LPRScopeのリスト
    
    # ポリシー
    policy = Column(JSONB, nullable=False)  # LPRPolicyの内容
    
    # 相関・追跡
    correlation_id = Column(String(64), nullable=False, index=True)
    parent_session_id = Column(String(255), nullable=True)
    
    # 失効情報
    revoked = Column(Boolean, default=False, nullable=False, index=True)
    revocation_time = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Text, nullable=True)
    revoked_by = Column(String(255), nullable=True)
    
    # 使用統計
    usage_count = Column(Integer, default=0, nullable=False)
    last_request_url = Column(Text, nullable=True)
    last_request_method = Column(String(10), nullable=True)
    
    # メタデータ
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # リレーション
    user = relationship("User", backref=backref("lpr_tokens", lazy="dynamic"))
    audit_logs = relationship("AuditLog", backref="lpr_token", lazy="dynamic")
    
    # インデックス
    __table_args__ = (
        Index("idx_lpr_active", "subject_pseudonym", "expires_at", "revoked"),
        Index("idx_lpr_correlation", "correlation_id"),
        Index("idx_lpr_device", "device_fingerprint_hash"),
        CheckConstraint("expires_at > issued_at", name="check_expiry_after_issue"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": str(self.id),
            "jti": self.jti,
            "version": self.version,
            "subject_pseudonym": self.subject_pseudonym,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "device_fingerprint_hash": self.device_fingerprint_hash,
            "origin_allowlist": self.origin_allowlist,
            "scope_allowlist": self.scope_allowlist,
            "policy": self.policy,
            "revoked": self.revoked,
            "usage_count": self.usage_count,
        }

class AuditLog(Base):
    """監査ログテーブル"""
    __tablename__ = "audit_logs"
    
    # 主キー
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_number = Column(Integer, nullable=False, unique=True, index=True)
    
    # 5W1H
    who = Column(String(255), nullable=False, index=True)  # 誰が
    when = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)  # いつ
    what = Column(Text, nullable=False)  # 何を
    where = Column(String(255), nullable=False)  # どこで
    why = Column(Text, nullable=False)  # なぜ
    how = Column(String(255), nullable=False)  # どのように
    
    # イベント情報
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    result = Column(String(20), nullable=False)
    
    # 相関・追跡
    correlation_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(255), nullable=True)
    request_id = Column(String(64), nullable=True)
    
    # LPR関連
    lpr_token_id = Column(UUID(as_uuid=True), ForeignKey("lpr_tokens.id"), nullable=True)
    
    # クライアント情報
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # 詳細データ
    details = Column(JSONB, nullable=True)
    
    # ハッシュチェーン
    previous_hash = Column(String(64), nullable=False)
    entry_hash = Column(String(64), nullable=False, unique=True)
    signature = Column(Text, nullable=True)
    
    # タイムスタンプ
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # インデックス
    __table_args__ = (
        Index("idx_audit_event", "event_type", "when"),
        Index("idx_audit_who_when", "who", "when"),
        Index("idx_audit_correlation", "correlation_id"),
        Index("idx_audit_severity", "severity", "when"),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": str(self.id),
            "sequence_number": self.sequence_number,
            "who": self.who,
            "when": self.when.isoformat(),
            "what": self.what,
            "where": self.where,
            "why": self.why,
            "how": self.how,
            "event_type": self.event_type,
            "severity": self.severity,
            "result": self.result,
            "correlation_id": self.correlation_id,
            "details": self.details,
            "entry_hash": self.entry_hash,
        }

class DeviceFingerprint(Base):
    """デバイス指紋テーブル"""
    __tablename__ = "device_fingerprints"
    
    # 主キー
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fingerprint_hash = Column(String(64), unique=True, nullable=False, index=True)
    
    # デバイス情報
    user_agent = Column(Text, nullable=False)
    accept_language = Column(String(255), nullable=False)
    screen_resolution = Column(String(20), nullable=True)
    timezone = Column(String(50), nullable=True)
    platform = Column(String(50), nullable=True)
    
    # ハードウェア情報
    hardware_concurrency = Column(Integer, nullable=True)
    device_memory = Column(Integer, nullable=True)
    
    # フィンガープリント
    canvas_fingerprint = Column(Text, nullable=True)
    webgl_fingerprint = Column(Text, nullable=True)
    audio_fingerprint = Column(Text, nullable=True)
    
    # 信頼性スコア
    trust_score = Column(Float, default=0.5, nullable=False)
    
    # 統計
    first_seen = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=False, default=func.now())
    usage_count = Column(Integer, default=1, nullable=False)
    
    # ユーザー関連
    user_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # 関連するユーザーID
    
    # メタデータ
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # インデックス
    __table_args__ = (
        Index("idx_device_trust", "trust_score", "last_seen"),
        Index("idx_device_usage", "usage_count", "last_seen"),
    )

class RateLimitBucket(Base):
    """レート制限バケットテーブル"""
    __tablename__ = "rate_limit_buckets"
    
    # 主キー
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # バケット識別子
    bucket_key = Column(String(255), unique=True, nullable=False, index=True)
    bucket_type = Column(String(50), nullable=False)  # "lpr", "user", "ip", etc.
    
    # トークンバケット
    tokens = Column(Float, nullable=False, default=0.0)
    max_tokens = Column(Float, nullable=False)
    refill_rate = Column(Float, nullable=False)  # トークン/秒
    
    # 時間情報
    last_refill = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # 統計
    total_requests = Column(Integer, default=0, nullable=False)
    rejected_requests = Column(Integer, default=0, nullable=False)
    
    # メタデータ
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # インデックス
    __table_args__ = (
        Index("idx_ratelimit_key", "bucket_key", "bucket_type"),
        Index("idx_ratelimit_refill", "last_refill"),
    )

class LPRUsageLog(Base):
    """LPR使用ログテーブル（詳細な使用履歴）"""
    __tablename__ = "lpr_usage_logs"
    
    # 主キー
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # LPRトークン参照
    lpr_token_id = Column(UUID(as_uuid=True), ForeignKey("lpr_tokens.id"), nullable=False)
    jti = Column(String(255), nullable=False, index=True)
    
    # リクエスト情報
    request_time = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    request_method = Column(String(10), nullable=False)
    request_url = Column(Text, nullable=False)
    request_origin = Column(String(255), nullable=True)
    request_size = Column(Integer, nullable=True)
    
    # レスポンス情報
    response_status = Column(Integer, nullable=True)
    response_size = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # 検証結果
    validation_result = Column(String(20), nullable=False)  # "success", "failure"
    validation_error = Column(Text, nullable=True)
    
    # デバイス情報
    device_fingerprint_match = Column(Boolean, nullable=True)
    client_ip = Column(String(45), nullable=True)
    
    # 相関ID
    correlation_id = Column(String(64), nullable=False, index=True)
    
    # メタデータ
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # リレーション
    lpr_token = relationship("LPRToken", backref=backref("usage_logs", lazy="dynamic"))
    
    # インデックス
    __table_args__ = (
        Index("idx_usage_token_time", "lpr_token_id", "request_time"),
        Index("idx_usage_correlation", "correlation_id"),
        Index("idx_usage_result", "validation_result", "request_time"),
    )

class LPRRevocationList(Base):
    """LPR失効リストテーブル（高速参照用）"""
    __tablename__ = "lpr_revocation_list"
    
    # 主キー
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # トークン識別子
    jti = Column(String(255), unique=True, nullable=False, index=True)
    
    # 失効情報
    revoked_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), index=True)
    reason = Column(Text, nullable=False)
    revoked_by = Column(String(255), nullable=False)
    
    # 元のトークン情報（参照用）
    original_expires_at = Column(DateTime(timezone=True), nullable=False)
    subject_pseudonym = Column(String(64), nullable=False)
    
    # 通知状態
    notification_sent = Column(Boolean, default=False, nullable=False)
    
    # メタデータ
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # インデックス
    __table_args__ = (
        Index("idx_revocation_jti", "jti"),
        Index("idx_revocation_time", "revoked_at"),
        Index("idx_revocation_expires", "original_expires_at"),
    )

# イベントリスナー：監査ログのシーケンス番号自動採番
@event.listens_for(AuditLog, "before_insert")
def receive_before_insert(mapper, connection, target):
    """監査ログ挿入前にシーケンス番号を採番"""
    # 最大のシーケンス番号を取得
    result = connection.execute(
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM audit_logs"
    )
    target.sequence_number = result.scalar()

# ユーザーテーブル（既存または新規）
class User(Base):
    """ユーザーテーブル（LPR関連カラムを追加）"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    
    # LPR関連
    lpr_enabled = Column(Boolean, default=True, nullable=False)
    max_lpr_tokens = Column(Integer, default=10, nullable=False)
    lpr_default_ttl = Column(Integer, default=3600, nullable=False)
    
    # その他のカラムは既存のシステムに依存
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())