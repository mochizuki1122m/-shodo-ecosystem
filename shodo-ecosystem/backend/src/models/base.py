"""
データベース基本設定とベースモデル
"""

import os
from typing import AsyncGenerator
from datetime import datetime
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import Column, DateTime, String
import uuid

# データベースURL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://shodo:shodo_pass@localhost:5432/shodo"
)

# 同期用URL（マイグレーション用）
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

LIGHT = os.getenv("LIGHT_TESTS") == "1"

# エンジンの作成（軽量テスト時はスキップ）
if not LIGHT:
    async_engine = create_async_engine(
        DATABASE_URL,
        echo=os.getenv("DEBUG", "false").lower() == "true",
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
    )
    sync_engine = create_engine(
        SYNC_DATABASE_URL,
        echo=os.getenv("DEBUG", "false").lower() == "true",
    )
else:
    async_engine = None
    sync_engine = None

# セッションファクトリ（軽量テスト時はダミー）
AsyncSessionLocal = async_sessionmaker(
    async_engine,  # type: ignore[arg-type]
    class_=AsyncSession,
    expire_on_commit=False,
) if not LIGHT else None

SessionLocal = sessionmaker(
    sync_engine,
    autocommit=False,
    autoflush=False,
) if not LIGHT else None

# メタデータ
metadata = MetaData()

# ベースクラス
Base = declarative_base(metadata=metadata)

class BaseModel(Base):
    """
    すべてのモデルの基底クラス
    """
    __abstract__ = True
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """モデルを辞書に変換"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
    
    def update_from_dict(self, data: dict):
        """辞書からモデルを更新"""
        for key, value in data.items():
            if hasattr(self, key) and key not in ['id', 'created_at']:
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()

# データベース接続の取得
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    非同期データベースセッションを取得
    """
    if LIGHT:
        # ダミーの非同期ジェネレーター
        async def _dummy():
            yield None  # type: ignore[misc]
        async for _ in _dummy():
            return
    async with AsyncSessionLocal() as session:  # type: ignore[func-returns-value]
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_sync_db() -> Session:
    """
    同期データベースセッションを取得（マイグレーション用）
    """
    if LIGHT:
        raise RuntimeError("Sync DB not available in LIGHT_TESTS mode")
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

async def init_db():
    """
    データベースの初期化
    """
    if LIGHT:
        return
    async with async_engine.begin() as conn:  # type: ignore[union-attr]
        # テーブルの作成
        await conn.run_sync(Base.metadata.create_all)
    
    print("Database initialized successfully")

async def drop_db():
    """
    データベースの削除（開発用）
    """
    if LIGHT:
        return
    async with async_engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.drop_all)
    
    print("Database dropped successfully")