"""
NLP関連スキーマ
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .common import StatusEnum

class AnalysisType(str, Enum):
    """解析タイプ"""
    RULE_BASED = "rule_based"
    AI_BASED = "ai_based"
    HYBRID = "hybrid"

class NLPRequest(BaseModel):
    """NLP解析リクエスト"""
    text: str = Field(..., min_length=1, max_length=10000, description="解析対象テキスト")
    context: Optional[Dict[str, Any]] = Field(default=None, description="コンテキスト情報")
    analysis_type: AnalysisType = Field(default=AnalysisType.HYBRID, description="解析タイプ")
    session_id: Optional[str] = Field(default=None, description="セッションID")

class NLPResponse(BaseModel):
    """NLP解析レスポンス"""
    session_id: str = Field(..., description="セッションID")
    analysis_id: str = Field(..., description="解析ID")
    status: StatusEnum = Field(..., description="ステータス")
    rule_matches: Optional[Dict] = Field(default=None, description="ルールベース解析結果")
    ai_analysis: Optional[Dict] = Field(default=None, description="AI解析結果")
    combined_score: float = Field(..., description="統合スコア")
    processing_time_ms: int = Field(..., description="処理時間（ミリ秒）")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="タイムスタンプ")

class NLPBatchRequest(BaseModel):
    """バッチ解析リクエスト"""
    texts: List[str] = Field(..., description="解析対象テキストリスト")
    analysis_type: AnalysisType = Field(default=AnalysisType.HYBRID, description="解析タイプ")

class NLPBatchResponse(BaseModel):
    """バッチ解析レスポンス"""
    batch_id: str = Field(..., description="バッチID")
    total: int = Field(..., description="総件数")
    completed: int = Field(..., description="完了件数")
    results: List[NLPResponse] = Field(default_factory=list, description="解析結果リスト")