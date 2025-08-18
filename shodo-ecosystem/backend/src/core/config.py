"""
Enterprise Configuration Management
Production-ready settings with validation
"""

import os
from typing import List, Optional, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator, SecretStr
import secrets

class Settings(BaseSettings):
    """
    Application settings with strict validation
    MUST: All secrets from environment/Vault, never hardcoded
    """
    
    # Application
    app_name: str = "Shodo Ecosystem"
    app_version: str = "1.0.0"
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = Field(default=False)
    
    # MUST: Production debug=False
    @validator('debug')
    def validate_debug(cls, v, values):
        if values.get('environment') == 'production' and v:
            raise ValueError("DEBUG must be False in production")
        return v
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = Field(default=4, ge=1, le=16)
    reload: bool = False
    
    # Security - MUST: Strong secrets
    secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(64)),
        min_length=64
    )
    jwt_secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(64)),
        min_length=64
    )
    jwt_algorithm: str = "RS256"
    jwt_expire_minutes: int = Field(default=60, le=60)  # Max 1 hour
    encryption_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        min_length=32
    )
    
    # CORS - MUST: Strict in production
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
    )
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = ["*"]
    
    @validator('cors_origins')
    def validate_cors(cls, v, values):
        if values.get('environment') == 'production':
            # MUST: No wildcards in production
            if any(origin in ['*', 'null'] for origin in v):
                raise ValueError("Wildcard CORS origins not allowed in production")
        return v
    
    # Trusted Hosts - MUST: Explicit allowlist
    trusted_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"]
    )
    
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://shodo:shodo_pass@postgres:5432/shodo",
        pattern=r"^postgresql\+asyncpg://.*"
    )
    database_pool_size: int = Field(default=20, ge=5, le=100)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_pool_timeout: int = Field(default=30, ge=10, le=60)
    database_echo: bool = False
    
    # Redis
    redis_url: str = Field(
        default="redis://redis:6379/0",
        pattern=r"^redis://.*"
    )
    redis_pool_size: int = Field(default=10, ge=5, le=50)
    redis_decode_responses: bool = True
    
    # AI Server
    vllm_url: str = Field(
        default="http://vllm:8001",
        pattern=r"^https?://.*"
    )
    vllm_timeout: int = Field(default=30, ge=10, le=120)
    vllm_max_retries: int = Field(default=3, ge=1, le=5)
    inference_engine: str = Field(
        default="vllm",
        pattern="^(vllm|ollama)$"
    )
    
    # Monitoring
    metrics_enabled: bool = True
    tracing_enabled: bool = True
    otlp_endpoint: str = Field(
        default="http://otel-collector:4317",
        pattern=r"^https?://.*"
    )
    service_name: str = "shodo-backend"
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_default: int = Field(default=100, ge=10, le=1000)  # per minute
    rate_limit_burst: int = Field(default=150, ge=10, le=1500)
    
    # Logging
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    log_format: str = "json"  # json or text
    log_file: Optional[str] = None
    
    # File Upload
    max_upload_size: int = Field(default=10485760, le=104857600)  # 10MB default, 100MB max
    allowed_upload_extensions: List[str] = [".jpg", ".jpeg", ".png", ".pdf", ".csv", ".xlsx"]
    
    # Session
    session_lifetime_seconds: int = Field(default=3600, ge=300, le=86400)  # 5min to 24h
    session_cookie_secure: bool = True
    session_cookie_httponly: bool = True
    session_cookie_samesite: str = Field(
        default="lax",
        pattern="^(lax|strict|none)$"
    )
    
    # Feature Flags
    feature_lpr_enabled: bool = True
    feature_nlp_enabled: bool = True
    feature_preview_enabled: bool = True
    feature_mcp_enabled: bool = True
    
    # External Services (from Vault/KMS in production)
    shopify_api_key: Optional[SecretStr] = None
    shopify_api_secret: Optional[SecretStr] = None
    stripe_api_key: Optional[SecretStr] = None
    gmail_client_id: Optional[SecretStr] = None
    gmail_client_secret: Optional[SecretStr] = None
    
    # Vault/KMS Configuration
    vault_enabled: bool = Field(default=False)
    vault_url: Optional[str] = None
    vault_token: Optional[SecretStr] = None
    vault_mount_point: str = "secret"
    vault_path: str = "shodo"
    
    @validator('vault_enabled')
    def validate_vault(cls, v, values):
        if values.get('environment') == 'production' and not v:
            raise ValueError("Vault must be enabled in production")
        return v
    
    # Health Check
    health_check_enabled: bool = True
    health_check_path: str = "/health"
    
    # SLA/SLO Targets
    slo_availability_target: float = Field(default=99.95, ge=99.0, le=100.0)
    slo_latency_p95_ms: int = Field(default=300, ge=100, le=1000)
    slo_error_rate_percent: float = Field(default=0.1, ge=0.0, le=1.0)
    
    model_config = SettingsConfigDict(
        env_file=".env" if os.getenv("ENVIRONMENT") != "production" else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid"  # Reject unknown fields
    )
    
    def get_database_url(self, sync: bool = False) -> str:
        """Get database URL for sync or async operations"""
        if sync:
            return self.database_url.replace("+asyncpg", "")
        return self.database_url
    
    def get_redis_settings(self) -> Dict[str, Any]:
        """Get Redis connection settings"""
        return {
            "url": self.redis_url,
            "encoding": "utf-8",
            "decode_responses": self.redis_decode_responses,
            "max_connections": self.redis_pool_size,
        }
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development"

# Create settings instance
settings = Settings()

# Validate critical settings at startup
def validate_settings():
    """Validate settings meet requirements"""
    errors = []
    
    if settings.is_production():
        # MUST requirements for production
        if settings.debug:
            errors.append("DEBUG must be False in production")
        
        if not settings.vault_enabled:
            errors.append("Vault must be enabled in production")
        
        if "*" in settings.cors_origins:
            errors.append("Wildcard CORS not allowed in production")
        
        if not settings.session_cookie_secure:
            errors.append("Session cookies must be secure in production")
        
        if settings.jwt_expire_minutes > 60:
            errors.append("JWT expiry must be <= 60 minutes")
    
    if errors:
        raise ValueError(f"Settings validation failed: {'; '.join(errors)}")

# Export
__all__ = ['settings', 'Settings', 'validate_settings']