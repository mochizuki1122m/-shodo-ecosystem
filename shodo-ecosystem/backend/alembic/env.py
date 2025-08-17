"""
Alembic環境設定
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys
from pathlib import Path

# プロジェクトのルートパスを追加
sys.path.append(str(Path(__file__).parent.parent))

# モデルをインポート
from src.models.base import Base
from src.models.api_key import APIKey, APIKeyAuditLog, APIKeyUsage
from src.models.user import User, UserSession
from src.models.service_connection import ServiceConnection

# Alembic Config object
config = context.config

# Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# モデルのメタデータ
target_metadata = Base.metadata

# 環境変数からデータベースURLを取得
def get_url():
    return os.getenv(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url")
    ).replace("+asyncpg", "")  # 同期用URLに変換

def run_migrations_offline() -> None:
    """
    'offline'モードでマイグレーションを実行
    
    SQLAlchemyのURLを設定し、context.execute()でSQL文字列を
    出力するようにコンテキストを構成します。
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """
    'online'モードでマイグレーションを実行
    
    Engineを作成し、接続とトランザクションでコンテキストを構成します。
    """
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()