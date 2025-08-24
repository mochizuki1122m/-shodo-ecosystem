"""
LPR Enforcer Middleware
MUST: Enforce LPR policies on all protected endpoints
"""

import time
import json
import random
from typing import Optional, Callable
from datetime import datetime, timezone

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from ..services.auth.lpr_service import (
    LPRService, LPRScope, DeviceFingerprint, get_lpr_service
)
from ..core.config import settings
from ..core.security import PIIMasking
from ..utils.correlation import set_correlation_id

logger = structlog.get_logger()

class LPREnforcerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce LPR policies
    
    MUST requirements:
    - Verify token signature and expiration
    - Check revocation status
    - Verify device fingerprint
    - Enforce rate limits
    - Add human speed jitter
    - Mask sensitive response data
    - Audit all operations
    """
    
    # Endpoints that don't require LPR
    EXEMPT_PATHS = [
        "/health",
        "/metrics",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/docs",
        "/api/redoc",
        "/openapi.json"
    ]
    
    # Endpoints that require LPR
    LPR_REQUIRED_PATHS = [
        "/api/v1/mcp/",
        "/api/v1/external/",
        "/api/v1/nlp/",
        "/api/v1/preview/"
    ]
    
    def __init__(self, app):
        super().__init__(app)
        self.lpr_service: Optional[LPRService] = None
        self.rate_limits = {}  # In-memory rate limiting
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through LPR enforcement"""
        
        # Set correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", "")
        if not correlation_id:
            correlation_id = set_correlation_id(request)
        
        # Check if path is exempt
        if self._is_exempt_path(request.url.path):
            return await call_next(request)
        
        # Check if LPR is required
        if not self._requires_lpr(request.url.path):
            # Regular authentication is sufficient
            return await call_next(request)
        
        # Initialize LPR service if needed
        if self.lpr_service is None:
            self.lpr_service = await get_lpr_service()
        
        # Extract LPR token
        lpr_token = self._extract_lpr_token(request)
        if not lpr_token:
            logger.warning(
                "LPR token missing for protected endpoint",
                path=request.url.path,
                correlation_id=correlation_id
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "LPR_TOKEN_REQUIRED",
                    "message": "LPR token is required for this operation",
                    "correlation_id": correlation_id
                }
            )
        
        # Extract device fingerprint
        device_fingerprint = self._extract_device_fingerprint(request)
        
        # Create required scope
        required_scope = LPRScope(
            method=request.method,
            url_pattern=request.url.path
        )
        
        # Verify token
        verification = await self.lpr_service.verify_token(
            lpr_token,
            device_fingerprint,
            required_scope
        )
        
        if not verification.get("valid"):
            logger.warning(
                "LPR token verification failed",
                path=request.url.path,
                error=verification.get("error"),
                correlation_id=correlation_id
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "LPR_VERIFICATION_FAILED",
                    "message": verification.get("error", "Token verification failed"),
                    "correlation_id": correlation_id
                }
            )
        
        # Extract token info
        jti = verification.get("jti")
        user_id = verification.get("user_id")
        service = verification.get("service")
        
        # Store LPR context in request state for downstream middlewares (e.g., RateLimit)
        request.state.lpr_jti = jti
        request.state.lpr_user_id = user_id
        request.state.lpr_service = service
        request.state.correlation_id = correlation_id
        
        # Add human speed jitter (if enabled)
        if await self._should_add_jitter(jti):
            jitter_ms = random.randint(50, 200)
            await self._async_sleep(jitter_ms / 1000)
        
        # Log the operation start
        start_time = time.time()
        logger.info(
            "LPR operation started",
            jti=jti,
            user_id=user_id,
            service=service,
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id
        )
        
        # Process the request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log operation failure
            logger.error(
                "LPR operation failed",
                jti=jti,
                user_id=user_id,
                service=service,
                error=str(e),
                correlation_id=correlation_id,
                exc_info=True
            )
            raise
        
        # Calculate operation time
        operation_time = time.time() - start_time
        
        # Mask sensitive response data
        if response.status_code == 200:
            response = await self._mask_response(response)
        
        # Add LPR headers
        response.headers["X-LPR-JTI"] = jti
        response.headers["X-LPR-Service"] = service
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Operation-Time"] = f"{operation_time:.3f}"
        
        # Audit log the operation
        await self._audit_log(
            jti=jti,
            user_id=user_id,
            service=service,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            operation_time=operation_time,
            correlation_id=correlation_id
        )
        
        return response
    
    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from LPR"""
        for exempt in self.EXEMPT_PATHS:
            if path.startswith(exempt):
                return True
        return False
    
    def _requires_lpr(self, path: str) -> bool:
        """Check if path requires LPR token"""
        for required in self.LPR_REQUIRED_PATHS:
            if path.startswith(required):
                return True
        return False
    
    def _extract_lpr_token(self, request: Request) -> Optional[str]:
        """Extract LPR token from request"""
        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer LPR-"):
            return auth_header[11:]  # Remove "Bearer LPR-" prefix
        
        # Check X-LPR-Token header
        lpr_header = request.headers.get("X-LPR-Token")
        if lpr_header:
            return lpr_header
        
        # Check query parameter (not recommended for production)
        if not settings.is_production():
            return request.query_params.get("lpr_token")
        
        return None
    
    def _extract_device_fingerprint(self, request: Request) -> DeviceFingerprint:
        """Extract device fingerprint from request"""
        return DeviceFingerprint(
            user_agent=request.headers.get("User-Agent", ""),
            accept_language=request.headers.get("Accept-Language", ""),
            screen_resolution=request.headers.get("X-Screen-Resolution"),
            timezone=request.headers.get("X-Timezone"),
            canvas_hash=request.headers.get("X-Canvas-Hash")
        )
    
    async def _check_rate_limit(self, jti: str, request: Request) -> bool:
        """Check rate limits for the token"""
        now = time.time()
        key = f"{jti}:{request.url.path}"
        
        if key not in self.rate_limits:
            self.rate_limits[key] = {
                "requests": [],
                "window_start": now
            }
        
        limits = self.rate_limits[key]
        
        # Clean old requests (outside 60 second window)
        limits["requests"] = [
            req_time for req_time in limits["requests"]
            if now - req_time < 60
        ]
        
        # Check limit (100 requests per minute)
        if len(limits["requests"]) >= 100:
            return False
        
        # Check burst limit (10 requests per second)
        recent_requests = [
            req_time for req_time in limits["requests"]
            if now - req_time < 1
        ]
        if len(recent_requests) >= 10:
            return False
        
        # Add current request
        limits["requests"].append(now)
        
        return True
    
    async def _should_add_jitter(self, jti: str) -> bool:
        """Determine if human speed jitter should be added"""
        # Add jitter to 30% of requests in production
        if settings.is_production():
            return random.random() < 0.3
        return False
    
    async def _async_sleep(self, seconds: float):
        """Async sleep for jitter"""
        import asyncio
        await asyncio.sleep(seconds)
    
    async def _mask_response(self, response: Response) -> Response:
        """Mask sensitive data in response"""
        # Only mask JSON responses
        if "application/json" not in response.headers.get("content-type", ""):
            return response
        
        # Read response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        try:
            # Parse JSON
            data = json.loads(body)
            
            # Mask PII
            masked_data = PIIMasking.mask_dict(data)
            
            # Create new response with masked data
            return JSONResponse(
                content=masked_data,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except:
            # If parsing fails, return original
            return response
    
    async def _audit_log(
        self,
        jti: str,
        user_id: str,
        service: str,
        method: str,
        path: str,
        status_code: int,
        operation_time: float,
        correlation_id: str
    ):
        """Create audit log entry"""
        
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "lpr_operation",
            "jti": jti,
            "user_id": user_id,
            "service": service,
            "method": method,
            "path": path,
            "status_code": status_code,
            "operation_time_ms": operation_time * 1000,
            "correlation_id": correlation_id,
            "success": 200 <= status_code < 400
        }
        
        # Log to structured logger
        logger.info("LPR audit", **audit_entry)
        
        # Store in audit database/SIEM
        # await store_audit_log(audit_entry)