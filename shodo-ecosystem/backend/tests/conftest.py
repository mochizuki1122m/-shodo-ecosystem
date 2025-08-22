"""
pytest設定とフィクスチャ
"""

import os

# 軽量テストモード（DBや外部依存を読み込まない）
if os.getenv("LIGHT_TESTS") == "1":
    # 軽量モードでは重い依存関係を読み込まずにスキップ
    # 必要な軽量フィクスチャをここに定義可能
    pass
else:
    import pytest
    import asyncio
    from typing import AsyncGenerator
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient

    # テスト用環境変数設定
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_shodo"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["DEBUG"] = "true"

    from src.main_unified import app
    from src.models.models import Base
    from src.services.database import get_db
    from sqlalchemy import text

    # テスト用データベースエンジン
    test_engine = create_async_engine(
        os.environ["DATABASE_URL"],
        echo=False,
    )

    TestSessionLocal = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    @pytest.fixture(scope="session")
    def event_loop():
        """イベントループフィクスチャ"""
        loop = asyncio.get_event_loop_policy().new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="function")
    async def db_session() -> AsyncGenerator[AsyncSession, None]:
        """データベースセッションフィクスチャ"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with TestSessionLocal() as session:
            yield session
            await session.rollback()
        
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @pytest.fixture(scope="function")
    def client(db_session):
        """テストクライアントフィクスチャ"""
        
        async def override_get_db():
            yield db_session
        
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as test_client:
            yield test_client
        
        app.dependency_overrides.clear()

    @pytest.fixture
    def auth_headers():
        """認証ヘッダーフィクスチャ（簡易化）"""
        return {"Authorization": f"Bearer test-token"}

    @pytest.fixture
    def admin_headers():
        """管理者認証ヘッダーフィクスチャ（簡易化）"""
        return {"Authorization": f"Bearer admin-token"}