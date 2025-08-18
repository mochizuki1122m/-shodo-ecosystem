"""
NLP request/response schemas
MUST: OpenAPI compliant
"""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator

class NLPRequest(BaseModel):
    """NLP analysis request"""
    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text to analyze"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context for analysis"
    )
    mode: str = Field(
        default="dual_path",
        pattern="^(dual_path|rule_only|ai_only)$",
        description="Analysis mode"
    )
    
    @validator('text')
    def validate_text(cls, v):
        if not v or v.isspace():
            raise ValueError("Text cannot be empty or whitespace only")
        return v

class NLPAnalysisData(BaseModel):
    """NLP analysis result data"""
    intent: str = Field(description="Detected intent")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted entities"
    )
    service: Optional[str] = Field(
        default=None,
        description="Detected service"
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether confirmation is required"
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Clarification suggestions"
    )
    processing_path: str = Field(
        description="Processing path used (rule/ai/dual)"
    )
    processing_time_ms: float = Field(
        ge=0,
        description="Processing time in milliseconds"
    )

class NLPResponse(BaseModel):
    """Full NLP response (deprecated, use BaseResponse[NLPAnalysisData])"""
    pass