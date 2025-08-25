"""
Shodo Ecosystem Production Backend Server
Enterprise-grade implementation with full monitoring and security
"""

import logging
from contextlib import asynccontextmanager


from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
import uvicorn
import structlog

# Core configuration
from .core.config import settings, validate_settings
from .core.security import SecurityHeaders

# Database
from .services.database import init_db, close_db

# LPR System
from .services.auth.lpr_service import get_lpr_service
from .services.audit.audit_logger import init_audit_logger
from .middleware.lpr_enforcer import LPREnforcerMiddleware

# Monitoring
from .utils.correlation import CorrelationIDMiddleware
from .monitoring.metrics import MetricsMiddleware, init_system_metrics, get_metrics
from .monitoring.tracing import init_tracing

# ===== Secrets (Vault) =====
from pydantic import SecretStr
from .services.secrets.vault_client import get_vault_client

# API routers
from .api import health
from .api.v1 import nlp, preview

# Structured logging configuration
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    
    logger.info("Starting Shodo Ecosystem Backend (Production)")
    
    # Validate settings
    try:
        validate_settings()
        logger.info("Settings validated successfully")
    except ValueError as e:
        logger.error("Settings validation failed", error=str(e))
        raise
    
    # Initialize Vault and load critical secrets in production
    try:
        if settings.is_production():
            vault = await get_vault_client()
            # JWT keys
            jwt_keys = await vault.get_jwt_keys()
            if not jwt_keys.get("private_key") or not jwt_keys.get("public_key"):
                raise ValueError("JWT keys missing from Vault")
            settings.jwt_private_key = jwt_keys.get("private_key")
            settings.jwt_public_key = jwt_keys.get("public_key")
            settings.jwt_algorithm = "RS256"
            # Encryption key
            enc_key = await vault.get_encryption_key()
            if not enc_key:
                raise ValueError("Encryption key missing from Vault")
            settings.encryption_key = SecretStr(enc_key.decode("utf-8") if isinstance(enc_key, (bytes, bytearray)) else str(enc_key))
            # Audit signing key (optional but recommended)
            try:
                audit_sign = await vault.get_secret("audit", "signing_key")
                if audit_sign:
                    settings.audit_signing_key = audit_sign
            except Exception as e:
                logger.warning("Audit signing key not found in Vault", error=str(e))
            # Re-validate security with loaded secrets
            settings.validate_security()
            logger.info("Vault secrets loaded and security validated")
    except Exception as e:
        logger.error("Failed to load secrets from Vault", error=str(e))
        raise
    
    # Initialize database
    try:
        db_success, redis_success = await init_db()
        logger.info(
            "Database initialization",
            postgres=db_success,
            redis=redis_success
        )
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise
    
    # Initialize LPR system
    try:
        await get_lpr_service()
        await init_audit_logger()
        logger.info("LPR system initialized successfully")
    except Exception as e:
        logger.error("LPR system initialization failed", error=str(e))
        raise
    
    # Initialize monitoring
    init_system_metrics(settings.app_version, settings.environment)
    init_tracing(app)
    logger.info("Monitoring systems initialized")
    
    # Application started
    logger.info(
        "Application started",
        host=settings.host,
        port=settings.port,
        environment=settings.environment,
        version=settings.app_version
    )
    
    yield
    
    # Cleanup
    logger.info("Shutting down application")
    
    try:
        await close_db()
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error("Cleanup failed", error=str(e))

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if not settings.is_production() else None,
    redoc_url="/api/redoc" if not settings.is_production() else None,
)

# ===== Middleware Configuration =====

# CORS (strict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
    expose_headers=["X-Correlation-ID", "X-Process-Time", "X-LPR-JTI"],
)

# Trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts
)

# Correlation ID tracking
app.add_middleware(CorrelationIDMiddleware)

# Metrics collection
app.add_middleware(MetricsMiddleware)

# LPR enforcement
app.add_middleware(LPREnforcerMiddleware)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    for header, value in SecurityHeaders.HEADERS.items():
        response.headers[header] = value
    
    return response

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with correlation ID"""
    correlation_id = request.state.correlation_id if hasattr(request.state, "correlation_id") else None
    
    logger.error(
        "Unhandled exception",
        path=str(request.url.path),
        method=request.method,
        error=str(exc),
        correlation_id=correlation_id,
        exc_info=True
    )
    
    # Don't expose internal errors in production
    if settings.is_production():
        message = "An internal error occurred"
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": message,
            "correlation_id": correlation_id
        }
    )

# ===== API Router Registration =====

# Health checks (no auth required)
app.include_router(health.router)

# NLP API
app.include_router(nlp.router)

# Preview API
app.include_router(preview.router)

# TODO: Add these routers when implemented
# app.include_router(auth.router)
# app.include_router(lpr.router)
# app.include_router(dashboard.router)
# app.include_router(mcp.router)

# ===== Metrics Endpoint =====

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    metrics_data = get_metrics()
    return Response(
        content=metrics_data,
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )

# ===== Root Endpoint =====

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "lpr_enabled": settings.feature_lpr_enabled,
        "docs": "/api/docs" if not settings.is_production() else None,
    }

# ===== Admin Endpoints (Production only) =====

if settings.is_production():
    @app.post("/api/admin/lpr/cleanup")
    async def cleanup_expired_tokens():
        """Clean up expired LPR tokens"""
        lpr_service = await get_lpr_service()
        count = await lpr_service.cleanup_expired_tokens()
        
        return {
            "message": "Cleanup completed",
            "cleaned": count,
        }
    
    @app.get("/api/admin/lpr/stats")
    async def get_lpr_statistics():
        """Get LPR system statistics"""
        # TODO: Implement statistics gathering
        return {
            "total_tokens": 0,
            "active_tokens": 0,
            "revoked_tokens": 0,
            "expired_tokens": 0,
            "audit_logs": 0,
            "device_fingerprints": 0,
        }

# ===== Debug Endpoints (Development only) =====

if not settings.is_production():
    @app.get("/debug/config")
    async def debug_config():
        """Configuration information (debug only)"""
        return {
            "app_name": settings.app_name,
            "app_version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug,
            "cors_origins": settings.cors_origins,
            "rate_limit_enabled": settings.rate_limit_enabled,
            "features": {
                "lpr": settings.feature_lpr_enabled,
                "nlp": settings.feature_nlp_enabled,
                "preview": settings.feature_preview_enabled,
                "mcp": settings.feature_mcp_enabled,
            }
        }
    
    @app.post("/debug/test-lpr")
    async def test_lpr_flow():
        """Test LPR flow"""
        return {
            "message": "Test endpoint for LPR flow",
            "steps": [
                "1. Call /api/v1/lpr/visible-login",
                "2. Call /api/v1/lpr/issue",
                "3. Use token for protected endpoints",
                "4. Call /api/v1/lpr/revoke",
            ]
        }

# ===== Main Execution =====

if __name__ == "__main__":
    # Validate settings before starting
    validate_settings()
    
    # Configure logging
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s" if settings.log_format == "text" else None,
    )
    
    # Start server
    uvicorn.run(
        "src.main_production:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
        workers=settings.workers if not settings.reload else 1,
        loop="uvloop",
        access_log=True,
        use_colors=not settings.is_production(),
        proxy_headers=True,
        forwarded_allow_ips="*"
    )