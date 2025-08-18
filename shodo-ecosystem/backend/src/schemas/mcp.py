"""
MCP（Model Context Protocol）関連スキーマ
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ToolInfo(BaseModel):
    """ツール情報"""
    id: str = Field(..., description="ツールID")
    name: str = Field(..., description="ツール名")
    description: str = Field(..., description="ツールの説明")
    service: str = Field(..., description="所属サービス")
    parameters: List[Dict[str, Any]] = Field(default_factory=list, description="パラメータ定義")
    required_permissions: List[str] = Field(default_factory=list, description="必要な権限")

class ToolInvocationRequest(BaseModel):
    """ツール実行リクエスト"""
    tool_id: str = Field(..., description="ツールID")
    parameters: Dict[str, Any] = Field(..., description="実行パラメータ")
    context: Optional[Dict[str, Any]] = Field(default=None, description="コンテキスト")

class ToolInvocationResponse(BaseModel):
    """ツール実行レスポンス"""
    invocation_id: str = Field(..., description="実行ID")
    tool_id: str = Field(..., description="ツールID")
    status: str = Field(..., description="実行ステータス")
    result: Optional[Any] = Field(default=None, description="実行結果")
    error: Optional[str] = Field(default=None, description="エラーメッセージ")
    execution_time_ms: int = Field(..., description="実行時間（ミリ秒）")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="タイムスタンプ")