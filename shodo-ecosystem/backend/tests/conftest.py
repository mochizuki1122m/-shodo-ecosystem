"""
pytest設定とフィクスチャ（軽量・自己完結）
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

# FastAPI アプリ
from src.main_unified import app
from src.middleware.auth import get_current_user, CurrentUser
from src.models.models import Base
from src.services.auth.lpr import LPRService
from src.services.audit.audit_logger import AuditLogger

# SQLite(メモリ) の非永続テストDB
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
TestSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
def client(db_session):
    # DB依存のオーバーライド
    async def override_get_db():
        yield db_session

    async def override_current_user():
        return CurrentUser(
            user_id="test-user-id",
            username="testuser",
            email="test@example.com",
            roles=["user"],
            is_active=True,
        )

    from src.services.database import get_db as _get_db
    app.dependency_overrides[_get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}

# ===== モックデータ =====

@pytest.fixture
def mock_shopify_product():
    return {
        "id": "123",
        "title": "Test Product",
        "variants": [{"id": "v1", "price": "1000.00"}],
    }

@pytest.fixture
def mock_stripe_customer():
    return {
        "id": "cus_test123",
        "name": "Test Customer",
        "email": "test@example.com",
        "metadata": {"source": "web"},
    }

@pytest_asyncio.fixture
async def lpr_service():
    service = LPRService()
    service.redis_client = AsyncMock()
    yield service

@pytest_asyncio.fixture
async def audit_logger():
    logger = AuditLogger()
    logger.redis_client = AsyncMock()
    yield logger