"""
Correlation ID management
MUST: Track requests across all services
"""

import uuid
from typing import Optional
from fastapi import Request
from contextvars import ContextVar

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id",
    default=None
)

def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())

def get_correlation_id(request: Request = None) -> str:
    """
    Get correlation ID from request or context
    
    Priority:
    1. Request header (X-Correlation-ID)
    2. Request state
    3. Context variable
    4. Generate new
    """
    
    # Try request header
    if request:
        correlation_id = request.headers.get("X-Correlation-ID")
        if correlation_id:
            return correlation_id
        
        # Try request state
        if hasattr(request.state, "correlation_id"):
            return request.state.correlation_id
    
    # Try context variable
    correlation_id = correlation_id_var.get()
    if correlation_id:
        return correlation_id
    
    # Generate new
    return generate_correlation_id()

def set_correlation_id(request: Request, correlation_id: str = None) -> str:
    """
    Set correlation ID in request and context
    
    Returns:
        The correlation ID that was set
    """
    
    if not correlation_id:
        correlation_id = generate_correlation_id()
    
    # Set in request state
    if request:
        request.state.correlation_id = correlation_id
    
    # Set in context variable
    correlation_id_var.set(correlation_id)
    
    return correlation_id

class CorrelationIDMiddleware:
    """
    Middleware to manage correlation IDs
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract or generate correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode()
        
        if not correlation_id:
            correlation_id = generate_correlation_id()
        
        # Set in context
        correlation_id_var.set(correlation_id)
        
        async def send_with_correlation(message):
            if message["type"] == "http.response.start":
                # Add correlation ID to response headers
                headers = message.get("headers", [])
                headers.append((b"x-correlation-id", correlation_id.encode()))
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_with_correlation)