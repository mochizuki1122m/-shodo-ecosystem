"""
プレビュー関連のスキーマ定義
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator, HttpUrl
from enum import Enum

from .common import StatusEnum

class PreviewType(str, Enum):
    """プレビュータイプ"""
    HTML = "html"
    CSS = "css"
    JSON = "json"
    MARKDOWN = "markdown"
    COMPONENT = "component"

class ChangeType(str, Enum):
    """変更タイプ"""
    CONTENT = "content"
    STYLE = "style"
    STRUCTURE = "structure"
    ATTRIBUTE = "attribute"
    SCRIPT = "script"

class ApprovalStatus(str, Enum):
    """承認ステータス"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"

class PreviewRequest(BaseModel):
    """プレビュー生成リクエスト"""
    source_type: str = Field(..., description="ソースタイプ（SaaS名など）")
    source_id: str = Field(..., description="ソースID")
    target_element: Optional[str] = Field(None, description="対象要素セレクタ")
    modifications: Dict[str, Any] = Field(..., description="変更内容")
    preview_type: PreviewType = Field(PreviewType.HTML, description="プレビュータイプ")
    context: Optional[Dict[str, Any]] = Field(None, description="コンテキスト情報")
    session_id: Optional[str] = Field(None, description="セッションID")
    
    @validator('modifications')
    def validate_modifications(cls, v):
        """変更内容の検証"""
        if not v:
            raise ValueError("Modifications cannot be empty")
        return v

class Change(BaseModel):
    """変更内容"""
    change_id: str = Field(..., description="変更ID")
    type: ChangeType = Field(..., description="変更タイプ")
    target: str = Field(..., description="対象要素")
    property: str = Field(..., description="プロパティ")
    old_value: Any = Field(..., description="変更前の値")
    new_value: Any = Field(..., description="変更後の値")
    description: Optional[str] = Field(None, description="変更の説明")
    impact_level: str = Field("low", regex="^(low|medium|high|critical)$", description="影響度")

class PreviewData(BaseModel):
    """プレビューデータ"""
    preview_id: str = Field(..., description="プレビューID")
    version: int = Field(..., ge=1, description="バージョン")
    html: Optional[str] = Field(None, description="HTMLコンテンツ")
    css: Optional[str] = Field(None, description="CSSスタイル")
    javascript: Optional[str] = Field(None, description="JavaScriptコード")
    changes: List[Change] = Field(default_factory=list, description="変更リスト")
    confidence: float = Field(..., ge=0, le=1, description="確信度")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="メタデータ")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
class PreviewResponse(BaseModel):
    """プレビューレスポンス"""
    session_id: str = Field(..., description="セッションID")
    preview_id: str = Field(..., description="プレビューID")
    status: StatusEnum = Field(..., description="ステータス")
    preview_data: PreviewData = Field(..., description="プレビューデータ")
    preview_url: Optional[HttpUrl] = Field(None, description="プレビューURL")
    expires_at: datetime = Field(..., description="有効期限")
    can_apply: bool = Field(True, description="適用可能フラグ")
    warnings: List[str] = Field(default_factory=list, description="警告メッセージ")
    
class RefinementRequest(BaseModel):
    """修正リクエスト"""
    preview_id: str = Field(..., description="プレビューID")
    refinement_text: str = Field(..., min_length=1, max_length=1000, description="修正指示")
    keep_history: bool = Field(True, description="履歴保持フラグ")
    
class ApplyRequest(BaseModel):
    """適用リクエスト"""
    preview_id: str = Field(..., description="プレビューID")
    target_environment: str = Field("production", description="適用先環境")
    dry_run: bool = Field(False, description="ドライラン")
    backup: bool = Field(True, description="バックアップ作成")
    approval_token: Optional[str] = Field(None, description="承認トークン")
    
class ApplyResponse(BaseModel):
    """適用レスポンス"""
    apply_id: str = Field(..., description="適用ID")
    status: ApprovalStatus = Field(..., description="適用ステータス")
    applied_changes: List[Change] = Field(..., description="適用された変更")
    rollback_id: Optional[str] = Field(None, description="ロールバックID")
    backup_id: Optional[str] = Field(None, description="バックアップID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class PreviewHistory(BaseModel):
    """プレビュー履歴"""
    history_id: str = Field(..., description="履歴ID")
    preview_id: str = Field(..., description="プレビューID")
    version: int = Field(..., description="バージョン")
    changes: List[Change] = Field(..., description="変更リスト")
    created_by: str = Field(..., description="作成者")
    created_at: datetime = Field(..., description="作成日時")
    parent_version: Optional[int] = Field(None, description="親バージョン")
    
class RollbackRequest(BaseModel):
    """ロールバックリクエスト"""
    apply_id: str = Field(..., description="適用ID")
    rollback_to: Optional[str] = Field(None, description="ロールバック先ID")
    reason: str = Field(..., description="ロールバック理由")
    
class RollbackResponse(BaseModel):
    """ロールバックレスポンス"""
    rollback_id: str = Field(..., description="ロールバックID")
    status: StatusEnum = Field(..., description="ステータス")
    rolled_back_changes: List[Change] = Field(..., description="ロールバックされた変更")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PreviewSession(BaseModel):
    """プレビューセッション"""
    session_id: str = Field(..., description="セッションID")
    user_id: str = Field(..., description="ユーザーID")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")
    preview_count: int = Field(0, description="プレビュー生成数")
    apply_count: int = Field(0, description="適用回数")
    rollback_count: int = Field(0, description="ロールバック回数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="メタデータ")