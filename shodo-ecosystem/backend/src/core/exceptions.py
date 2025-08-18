"""
統一的な例外処理システム
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status

class BaseAPIException(HTTPException):
    """API基底例外クラス"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Internal server error"
    headers = None

    def __init__(
        self,
        detail: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        if detail:
            self.detail = detail
        if headers:
            self.headers = headers
        super().__init__(
            status_code=self.status_code,
            detail=self.detail,
            headers=self.headers
        )

class AuthenticationException(BaseAPIException):
    """認証例外"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication failed"
    headers = {"WWW-Authenticate": "Bearer"}

class AuthorizationException(BaseAPIException):
    """認可例外"""
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Permission denied"

class NotFoundException(BaseAPIException):
    """リソース未検出例外"""
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"

class ValidationException(BaseAPIException):
    """バリデーション例外"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation failed"

class RateLimitException(BaseAPIException):
    """レート制限例外"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Rate limit exceeded"

class ConflictException(BaseAPIException):
    """競合例外"""
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"

class BadRequestException(BaseAPIException):
    """不正リクエスト例外"""
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad request"

class ServiceUnavailableException(BaseAPIException):
    """サービス利用不可例外"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service temporarily unavailable"

class DatabaseException(BaseAPIException):
    """データベース例外"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Database error occurred"

class ExternalAPIException(BaseAPIException):
    """外部API例外"""
    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "External API error"