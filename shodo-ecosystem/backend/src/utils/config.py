"""
アプリケーション設定
"""

import os
from typing import Optional
from pydantic import BaseSettings

class Settings(BaseSettings):
    """アプリケーション設定"""
    
    # 基本設定
    app_name: str = "Shodo Ecosystem"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # サーバー設定
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = os.getenv("RELOAD", "True").lower() == "true"
    
    # データベース設定
    database_url: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://shodo:shodo_pass@localhost:5432/shodo"
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # AI サーバー設定
    vllm_url: str = os.getenv("VLLM_URL", "http://localhost:8001")
    ai_model: str = os.getenv("AI_MODEL", "openai/gpt-oss-20b")
    
    # セキュリティ設定
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY", 
        "your-secret-key-here-change-in-production"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS設定
    cors_origins: list = [
        "http://localhost:3000",
        "http://frontend:3000",
        "http://localhost:8000"
    ]
    
    # レート制限設定
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    
    # ログ設定
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # キャッシュ設定
    cache_ttl: int = 300  # 5分
    cache_max_size: int = 1000
    
    # サービス設定
    shopify_api_key: Optional[str] = os.getenv("SHOPIFY_API_KEY")
    shopify_api_secret: Optional[str] = os.getenv("SHOPIFY_API_SECRET")
    
    gmail_client_id: Optional[str] = os.getenv("GMAIL_CLIENT_ID")
    gmail_client_secret: Optional[str] = os.getenv("GMAIL_CLIENT_SECRET")
    
    stripe_api_key: Optional[str] = os.getenv("STRIPE_API_KEY")
    stripe_webhook_secret: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    
    slack_bot_token: Optional[str] = os.getenv("SLACK_BOT_TOKEN")
    slack_app_token: Optional[str] = os.getenv("SLACK_APP_TOKEN")
    
    notion_api_key: Optional[str] = os.getenv("NOTION_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# シングルトンインスタンス
settings = Settings()

def get_settings() -> Settings:
    """設定を取得"""
    return settings

def is_production() -> bool:
    """本番環境かチェック"""
    return os.getenv("ENVIRONMENT", "development").lower() == "production"

def is_development() -> bool:
    """開発環境かチェック"""
    return not is_production()