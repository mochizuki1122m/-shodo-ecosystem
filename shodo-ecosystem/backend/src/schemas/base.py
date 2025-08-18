"""
Base response schemas for API consistency
MUST: All responses follow BaseResponse pattern
"""

from typing import Generic, TypeVar, Optional, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

T = TypeVar('T')

class BaseResponse(BaseModel, Generic[T]):
    """
    Standard response wrapper for all API endpoints
    Ensures consistent response structure
    """
    success: bool = Field(default=True, description="Operation success status")
    message: Optional[str] = Field(default=None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Request correlation ID")
    data: Optional[T] = Field(default=None, description="Response payload")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ErrorDetail(BaseModel):
    """Error detail information"""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None

class ErrorResponse(BaseResponse[None]):
    """
    Standard error response
    """
    success: bool = Field(default=False)
    error: dict = Field(
        default={},
        description="Error details",
        example={
            "code": "VALIDATION_ERROR",
            "message": "Invalid input data",
            "details": []
        }
    )
    
    @classmethod
    def create(
        cls,
        code: str,
        message: str,
        details: Optional[List[ErrorDetail]] = None,
        correlation_id: Optional[str] = None
    ):
        """Factory method to create error response"""
        return cls(
            success=False,
            message=message,
            correlation_id=correlation_id or str(uuid.uuid4()),
            error={
                "code": code,
                "message": message,
                "details": [d.dict() for d in details] if details else []
            }
        )

class PaginatedResponse(BaseResponse[T]):
    """
    Paginated response wrapper
    """
    total: int = Field(description="Total number of items")
    page: int = Field(default=1, ge=1, description="Current page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    pages: int = Field(description="Total number of pages")
    
    @classmethod
    def create(
        cls,
        items: List[Any],
        total: int,
        page: int = 1,
        per_page: int = 20,
        message: Optional[str] = None
    ):
        """Factory method to create paginated response"""
        pages = (total + per_page - 1) // per_page
        return cls(
            success=True,
            message=message,
            data=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )

# Response helpers
def success_response(
    data: Any = None,
    message: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> BaseResponse:
    """Create a success response"""
    return BaseResponse(
        success=True,
        message=message,
        data=data,
        correlation_id=correlation_id or str(uuid.uuid4())
    )

def error_response(
    code: str,
    message: str,
    details: Optional[List[ErrorDetail]] = None,
    correlation_id: Optional[str] = None
) -> ErrorResponse:
    """Create an error response"""
    return ErrorResponse.create(
        code=code,
        message=message,
        details=details,
        correlation_id=correlation_id
    )