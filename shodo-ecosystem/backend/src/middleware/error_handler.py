"""
エラーハンドリングミドルウェア
"""

import traceback
import logging
from typing import Any
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import uuid

from ..core.exceptions import BaseAPIException
from ..services.audit.audit_logger import log_error

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """統一的なエラーハンドリングミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        """リクエスト処理とエラーハンドリング"""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            return response
            
        except BaseAPIException as e:
            # カスタム例外の処理
            await self._log_error(request, e, request_id)
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": {
                        "code": e.__class__.__name__,
                        "message": e.detail,
                        "request_id": request_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                headers=e.headers
            )
            
        except ValueError as e:
            # バリデーションエラー
            await self._log_error(request, e, request_id)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": {
                        "code": "ValidationError",
                        "message": str(e),
                        "request_id": request_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
        except Exception as e:
            # 予期しないエラー
            error_detail = self._get_error_detail(e)
            await self._log_error(request, e, request_id, is_critical=True)
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "code": "InternalServerError",
                        "message": "An unexpected error occurred",
                        "request_id": request_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "detail": error_detail if self._is_debug() else None
                    }
                }
            )
    
    async def _log_error(
        self,
        request: Request,
        error: Exception,
        request_id: str,
        is_critical: bool = False
    ):
        """エラーログ記録"""
        error_info = {
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc() if is_critical else None
        }
        
        if is_critical:
            logger.error(f"Critical error: {error_info}")
        else:
            logger.warning(f"Handled error: {error_info}")
        
        # 監査ログに記録
        try:
            await log_error(
                user_id=getattr(request.state, "user_id", None),
                action="error",
                resource=str(request.url.path),
                details=error_info,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent")
            )
        except Exception as log_error:
            logger.error(f"Failed to log error to audit: {log_error}")
    
    def _get_error_detail(self, error: Exception) -> dict:
        """エラー詳細情報取得"""
        return {
            "type": error.__class__.__name__,
            "message": str(error),
            "traceback": traceback.format_exc().split("\n")
        }
    
    def _is_debug(self) -> bool:
        """デバッグモード判定"""
        import os
        return os.getenv("DEBUG", "false").lower() == "true"