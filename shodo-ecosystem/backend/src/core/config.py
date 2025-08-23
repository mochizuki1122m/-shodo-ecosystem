"""
統一設定モジュール
全ての設定をこのファイルに集約
"""

from typing import List, Optional, Dict
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import json

class Settings(BaseSettings):
    """アプリケーション設定"""
    
    # pydantic v2 設定
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # 基本設定
    app_name: str = Field(default="Shodo Ecosystem", env="APP_NAME")
    app_version: str = Field(default="5.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # サーバー設定
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    reload: bool = Field(default=False, env="RELOAD")
    workers: int = Field(default=1, env="WORKERS")
    
    # データベース設定
    database_url: str = Field(
        default="postgresql://shodo:shodo_pass@postgres:5432/shodo",
        env="DATABASE_URL"
    )
    database_pool_size: int = Field(default=10, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Redis設定
    redis_url: str = Field(default="redis://redis:6379", env="REDIS_URL")
    redis_pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")
    redis_decode_responses: bool = Field(default=True, env="REDIS_DECODE_RESPONSES")
    
    # AIサーバー設定（ベースURLのみ、パスなし）
    vllm_url: str = Field(default="http://vllm:8001", env="VLLM_URL")
    vllm_timeout: int = Field(default=30, env="VLLM_TIMEOUT")
    vllm_retry_count: int = Field(default=3, env="VLLM_RETRY_COUNT")
    model_name: str = Field(default="openai/gpt-oss-20b", env="MODEL_NAME")
    inference_engine: str = Field(default="vllm", env="INFERENCE_ENGINE")
    
    # セキュリティ設定
    secret_key: SecretStr = Field(
        default=SecretStr("change-this-in-production-to-a-secure-random-string"),
        env="SECRET_KEY"
    )
    jwt_secret_key: SecretStr = Field(
        default=SecretStr("change-this-in-production-to-a-secure-random-string"),
        env="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_public_key: Optional[str] = Field(default=None, env="JWT_PUBLIC_KEY")
    jwt_private_key: Optional[str] = Field(default=None, env="JWT_PRIVATE_KEY")
    jwt_audience: str = Field(default="shodo-ecosystem", env="JWT_AUDIENCE")
    jwt_issuer: str = Field(default="shodo-auth", env="JWT_ISSUER")
    jwt_expiration_hours: int = Field(default=1, env="JWT_EXPIRATION_HOURS")
    
    # 暗号化設定
    encryption_key: SecretStr = Field(
        default=SecretStr("change-this-in-production-to-a-secure-random-string"),
        env="ENCRYPTION_KEY"
    )
    
    # CORS設定
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost", "http://frontend:3000"],
        env="CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: List[str] = Field(default=["*"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default=["*"], env="CORS_ALLOW_HEADERS")
    
    # Trusted hosts
    trusted_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1", "shodo.local", "*.shodo.local"],
        env="TRUSTED_HOSTS"
    )
    
    # レート制限設定（統一）
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, env="RATE_LIMIT_PER_HOUR")
    rate_limit_burst: int = Field(default=10, env="RATE_LIMIT_BURST")
    rate_limit_endpoint_limits: Dict[str, Dict[str, int]] = Field(
        default={
            "/api/v1/auth/login": {"per_minute": 5, "per_hour": 20, "burst": 2},
            "/api/v1/auth/register": {"per_minute": 3, "per_hour": 10, "burst": 1},
            "/api/v1/lpr/issue": {"per_minute": 10, "per_hour": 100, "burst": 3},
            "/api/v1/nlp/analyze": {"per_minute": 30, "per_hour": 500, "burst": 5},
            "/api/v1/preview/generate": {"per_minute": 20, "per_hour": 300, "burst": 3},
            "/health": {"per_minute": 9999, "per_hour": 99999, "burst": 999},
            "/metrics": {"per_minute": 9999, "per_hour": 99999, "burst": 999},
        },
        env="RATE_LIMIT_ENDPOINT_LIMITS"
    )
    rate_limit_fail_open: bool = Field(default=False, env="RATE_LIMIT_FAIL_OPEN")
    rate_limit_degraded_mode_headers: bool = Field(default=True, env="RATE_LIMIT_DEGRADED_MODE_HEADERS")
    
    # CSRF 設定（Cookieベース認証用）
    csrf_enabled: bool = Field(default=True, env="CSRF_ENABLED")
    csrf_cookie_name: str = Field(default="csrf_token", env="CSRF_COOKIE_NAME")
    csrf_header_name: str = Field(default="X-CSRF-Token", env="CSRF_HEADER_NAME")
    csrf_cookie_secure: bool = Field(default=True, env="CSRF_COOKIE_SECURE")
    csrf_cookie_samesite: str = Field(default="Lax", env="CSRF_COOKIE_SAMESITE")
    
    # SLO 設定
    slo_availability_target: float = Field(default=99.9, env="SLO_AVAILABILITY_TARGET")
    slo_latency_p95_ms: int = Field(default=300, env="SLO_LATENCY_P95_MS")
    slo_error_rate_percent: float = Field(default=1.0, env="SLO_ERROR_RATE_PERCENT")
    
    # ログ設定
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # LPR設定
    lpr_ttl_hours: int = Field(default=1, env="LPR_TTL_HOURS")  # 短命化
    lpr_device_binding: bool = Field(default=True, env="LPR_DEVICE_BINDING")
    lpr_scope_minimization: bool = Field(default=True, env="LPR_SCOPE_MINIMIZATION")
    lpr_audit_logging: bool = Field(default=True, env="LPR_AUDIT_LOGGING")
    
    # 監査設定
    service_name: str = Field(default="shodo-ecosystem", env="SERVICE_NAME")
    audit_signing_key: str = Field(
        default="change-this-audit-key-in-production",
        env="AUDIT_SIGNING_KEY"
    )
    
    # キャッシュ設定
    cache_ttl_seconds: int = Field(default=300, env="CACHE_TTL_SECONDS")
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    
    # CSP 設定（connect-src を環境変数で調整可能に）
    csp_connect_src: List[str] = Field(default=["'self'", "https:"], env="CSP_CONNECT_SRC")
    
    # 外部サービス設定
    shopify_api_key: Optional[str] = Field(default=None, env="SHOPIFY_API_KEY")
    shopify_api_secret: Optional[str] = Field(default=None, env="SHOPIFY_API_SECRET")
    stripe_api_key: Optional[str] = Field(default=None, env="STRIPE_API_KEY")
    gmail_api_key: Optional[str] = Field(default=None, env="GMAIL_API_KEY")
    slack_api_key: Optional[str] = Field(default=None, env="SLACK_API_KEY")
    
    def is_production(self) -> bool:
        """本番環境かどうかを判定"""
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """開発環境かどうかを判定"""
        return self.environment.lower() == "development"
    
    def is_testing(self) -> bool:
        """テスト環境かどうかを判定"""
        return self.environment.lower() == "testing"

    def validate_security(self):
        """本番時のセキュリティ設定を検証（必須設定が無ければFail-fast）"""
        if self.is_production():
            # JWT はRS256既定
            if self.jwt_algorithm.upper() != "RS256":
                self.jwt_algorithm = "RS256"
            # 鍵が無ければ起動失敗
            if not self.jwt_private_key or not self.jwt_public_key:
                raise ValueError("JWT keys are required in production (JWT_PRIVATE_KEY, JWT_PUBLIC_KEY)")
            # 既定の脆弱なキーが残っていれば失敗
            weak = "change-this-in-production-to-a-secure-random-string"
            if self.secret_key.get_secret_value() == weak or self.jwt_secret_key.get_secret_value() == weak or self.encryption_key.get_secret_value() == weak:
                raise ValueError("Default secrets must be overridden in production")

    # 互換: 環境変数のリスト/JSON形式対応（v1のparse_env_varの代替）
    @staticmethod
    def _parse_env_list(raw_val: str) -> List[str]:
        try:
            data = json.loads(raw_val)
            if isinstance(data, list):
                return [str(x).strip() for x in data]
        except Exception:
            pass
        return [x.strip() for x in str(raw_val).split(",") if x.strip()]

@lru_cache()
def get_settings() -> Settings:
    """設定のシングルトンインスタンスを取得"""
    s = Settings()
    # 本番検証
    try:
        s.validate_security()
    except Exception:
        # 早期にわかるよう例外を再送出
        raise
    return s

# グローバル設定インスタンス
settings = get_settings()