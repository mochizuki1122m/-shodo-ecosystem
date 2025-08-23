"""
Preview request/response schemas
MUST: Match OpenAPI specification and engine data structures
"""

from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator

class ChangeRequest(BaseModel):
    """Change to apply in preview"""
    type: str = Field(
        ...,
        pattern="^(style|content|structure|data)$",
        description="Type of change"
    )
    target: str = Field(
        ...,
        description="Target element selector or ID"
    )
    property: str = Field(
        ...,
        description="Property to change"
    )
    old_value: Optional[Any] = Field(
        default=None,
        description="Previous value"
    )
    new_value: Any = Field(
        ...,
        description="New value to apply"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )

class PreviewRequest(BaseModel):
    """Preview generation request"""
    changes: List[ChangeRequest] = Field(
        ...,
        min_items=1,
        description="Changes to apply"
    )
    service_id: str = Field(
        ...,
        description="Target service identifier"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context"
    )

class RefineRequest(BaseModel):
    """Preview refinement request"""
    refinement: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language refinement instruction"
    )
    
    @validator('refinement')
    def validate_refinement(cls, v):
        if not v or v.isspace():
            raise ValueError("Refinement cannot be empty")
        return v

class ApplyRequest(BaseModel):
    """Production apply request"""
    confirmed: bool = Field(
        default=False,
        description="Confirmation flag for production deployment"
    )
    dry_run: bool = Field(
        default=False,
        description="Perform dry run without actual changes"
    )

class VisualData(BaseModel):
    """Visual preview data"""
    html: str = Field(description="HTML content")
    css: str = Field(description="CSS styles")
    javascript: Optional[str] = Field(
        default="",
        description="JavaScript code"
    )
    screenshot: Optional[str] = Field(
        default=None,
        description="Screenshot URL or base64"
    )

class PreviewData(BaseModel):
    """Preview response data"""
    id: str = Field(description="Preview ID")
    version_id: str = Field(description="Version ID")
    service: str = Field(description="Service identifier")
    visual: VisualData = Field(description="Visual preview data")
    diff: Dict[str, Any] = Field(description="Diff information")
    changes: List[Dict[str, Any]] = Field(description="Applied changes")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    revert_token: str = Field(description="Token for reverting changes")

class PreviewResponse(BaseModel):
    """Full preview response (deprecated, use BaseResponse[PreviewData])"""
