"""
NLP関連のスキーマ定義
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

from .common import StatusEnum

class AnalysisType(str, Enum):
    """解析タイプ"""
    RULE_BASED = "rule_based"
    AI_BASED = "ai_based"
    HYBRID = "hybrid"

class TextType(str, Enum):
    """テキストタイプ"""
    PLAIN = "plain"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"

class NLPRequest(BaseModel):
    """NLP解析リクエスト"""
    text: str = Field(..., min_length=1, max_length=10000, description="解析対象テキスト")
    text_type: TextType = Field(TextType.PLAIN, description="テキストタイプ")
    analysis_type: AnalysisType = Field(AnalysisType.HYBRID, description="解析タイプ")
    options: Dict[str, Any] = Field(default_factory=dict, description="オプション設定")
    context: Optional[Dict[str, Any]] = Field(None, description="コンテキスト情報")
    session_id: Optional[str] = Field(None, description="セッションID")
    
    @validator('text')
    def validate_text(cls, v):
        """テキストの検証"""
        if not v or v.isspace():
            raise ValueError("Text cannot be empty or whitespace only")
        return v.strip()

class RuleMatch(BaseModel):
    """ルールマッチ結果"""
    rule_id: str = Field(..., description="ルールID")
    rule_name: str = Field(..., description="ルール名")
    category: str = Field(..., description="カテゴリ")
    matched_text: str = Field(..., description="マッチしたテキスト")
    position: Dict[str, int] = Field(..., description="位置情報")
    confidence: float = Field(..., ge=0, le=1, description="確信度")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="メタデータ")

class AIAnalysis(BaseModel):
    """AI解析結果"""
    intent: str = Field(..., description="検出された意図")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="エンティティ")
    sentiment: Dict[str, float] = Field(..., description="感情分析")
    keywords: List[str] = Field(default_factory=list, description="キーワード")
    summary: Optional[str] = Field(None, description="要約")
    confidence: float = Field(..., ge=0, le=1, description="全体の確信度")
    model_version: str = Field(..., description="使用モデルバージョン")

class NLPResponse(BaseModel):
    """NLP解析レスポンス"""
    session_id: str = Field(..., description="セッションID")
    analysis_id: str = Field(..., description="解析ID")
    status: StatusEnum = Field(..., description="処理ステータス")
    rule_matches: List[RuleMatch] = Field(default_factory=list, description="ルールマッチ結果")
    ai_analysis: Optional[AIAnalysis] = Field(None, description="AI解析結果")
    combined_score: float = Field(..., ge=0, le=1, description="統合スコア")
    processing_time_ms: int = Field(..., description="処理時間（ミリ秒）")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class NLPSession(BaseModel):
    """NLPセッション"""
    session_id: str = Field(..., description="セッションID")
    user_id: str = Field(..., description="ユーザーID")
    created_at: datetime = Field(..., description="作成日時")
    updated_at: datetime = Field(..., description="更新日時")
    analysis_count: int = Field(0, description="解析回数")
    total_tokens: int = Field(0, description="総トークン数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="メタデータ")

class RuleDefinition(BaseModel):
    """ルール定義"""
    rule_id: str = Field(..., description="ルールID")
    name: str = Field(..., description="ルール名")
    category: str = Field(..., description="カテゴリ")
    pattern: str = Field(..., description="パターン（正規表現）")
    description: str = Field(..., description="説明")
    priority: int = Field(0, ge=0, le=100, description="優先度")
    is_active: bool = Field(True, description="有効/無効")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class NLPBatchRequest(BaseModel):
    """バッチ解析リクエスト"""
    items: List[NLPRequest] = Field(..., min_items=1, max_items=100, description="解析リクエストリスト")
    parallel: bool = Field(True, description="並列処理の有無")
    priority: int = Field(0, ge=0, le=10, description="優先度")

class NLPBatchResponse(BaseModel):
    """バッチ解析レスポンス"""
    batch_id: str = Field(..., description="バッチID")
    total: int = Field(..., description="総件数")
    completed: int = Field(..., description="完了件数")
    failed: int = Field(..., description="失敗件数")
    results: List[NLPResponse] = Field(default_factory=list, description="結果リスト")
    processing_time_ms: int = Field(..., description="総処理時間")
    timestamp: datetime = Field(default_factory=datetime.utcnow)