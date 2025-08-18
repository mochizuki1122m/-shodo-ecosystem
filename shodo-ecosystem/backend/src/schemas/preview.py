"""
プレビュー関連スキーマ
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ChangeType(str, Enum):
    """変更タイプ"""
    STYLE = "style"
    CONTENT = "content"
    STRUCTURE = "structure"
    DATA = "data"

class ApprovalStatus(str, Enum):
    """承認ステータス"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Change(BaseModel):
    """変更内容"""
    type: ChangeType = Field(..., description="変更タイプ")
    target: str = Field(..., description="変更対象")
    property: str = Field(..., description="プロパティ")
    old_value: Any = Field(..., description="変更前の値")
    new_value: Any = Field(..., description="変更後の値")
    metadata: Optional[Dict] = Field(default=None, description="メタデータ")

class PreviewRequest(BaseModel):
    """プレビューリクエスト"""
    source_type: str = Field(..., description="ソースタイプ")
    source_id: str = Field(..., description="ソースID")
    modifications: List[Dict[str, Any]] = Field(..., description="変更内容")
    session_id: Optional[str] = Field(default=None, description="セッションID")

class PreviewData(BaseModel):
    """プレビューデータ"""
    visual_url: str = Field(..., description="ビジュアルURL")
    diff_html: str = Field(..., description="差分HTML")
    changes: List[Change] = Field(..., description="変更リスト")
    confidence_score: float = Field(..., description="確信度スコア")

class PreviewResponse(BaseModel):
    """プレビューレスポンス"""
    preview_id: str = Field(..., description="プレビューID")
    session_id: str = Field(..., description="セッションID")
    preview_data: PreviewData = Field(..., description="プレビューデータ")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="作成日時")

class RefinementRequest(BaseModel):
    """改善リクエスト"""
    refinement: str = Field(..., description="改善内容")

class ApplyRequest(BaseModel):
    """適用リクエスト"""
    confirm: bool = Field(default=True, description="確認フラグ")

class ApplyResponse(BaseModel):
    """適用レスポンス"""
    success: bool = Field(..., description="成功フラグ")
    applied_changes: int = Field(..., description="適用された変更数")
    rollback_token: str = Field(..., description="ロールバックトークン")

class RollbackRequest(BaseModel):
    """ロールバックリクエスト"""
    rollback_token: str = Field(..., description="ロールバックトークン")

class RollbackResponse(BaseModel):
    """ロールバックレスポンス"""
    success: bool = Field(..., description="成功フラグ")
    reverted_changes: int = Field(..., description="元に戻した変更数")

class PreviewHistory(BaseModel):
    """プレビュー履歴"""
    history: List[PreviewResponse] = Field(default_factory=list, description="履歴リスト")

class PreviewSession(BaseModel):
    """プレビューセッション"""
    session_id: str = Field(..., description="セッションID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="作成日時")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新日時")
    preview_count: int = Field(default=0, description="プレビュー数")