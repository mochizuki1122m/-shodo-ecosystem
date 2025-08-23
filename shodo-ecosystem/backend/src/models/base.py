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

LIGHT_TESTS = os.getenv("LIGHT_TESTS") == "1"

# データベースURL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://shodo:shodo_pass@localhost:5432/shodo"
)

# 同期用URL（マイグレーション用）
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "")

if not LIGHT_TESTS:
    # エンジンの作成
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
    
    # セッションファクトリ
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    SessionLocal = sessionmaker(
        sync_engine,
        autocommit=False,
        autoflush=False,
    )
else:
    # 軽量テスト時はダミーを用意
    async_engine = None
    sync_engine = None
    
    class _DummyAsyncSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def commit(self):
            pass
        async def rollback(self):
            pass
        async def close(self):
            pass
    
    def AsyncSessionLocal():  # type: ignore
        return _DummyAsyncSession()
    
    def SessionLocal():  # type: ignore
        return None

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
    if LIGHT_TESTS:
        # ダミーセッションを返す
        async with AsyncSessionLocal() as session:  # type: ignore
            yield session
            return
    
    async with AsyncSessionLocal() as session:  # type: ignore
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
    db = SessionLocal()  # type: ignore
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
    if LIGHT_TESTS:
        return
    async with async_engine.begin():  # type: ignore
        # テーブルの作成
        await async_engine.run_sync(Base.metadata.create_all)  # type: ignore
    
    print("Database initialized successfully")

async def drop_db():
    """
    データベースの削除（開発用）
    """
    if LIGHT_TESTS:
        return
    async with async_engine.begin():  # type: ignore
        await async_engine.run_sync(Base.metadata.drop_all)  # type: ignore
    
    print("Database dropped successfully")