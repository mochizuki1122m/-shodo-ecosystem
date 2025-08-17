"""
テスト用フィクスチャとベース設定
"""

import asyncio
import os
import sys
from typing import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.models.base import Base, get_db
from src.models.user import User
from src.models.api_key import APIKey, ServiceType
from src.main import app

# テスト用データベースURL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://shodo:shodo_pass@localhost:5432/shodo_test"
)

# テスト用エンジンとセッション
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """イベントループのフィクスチャ"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """データベースセッションのフィクスチャ"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTPクライアントのフィクスチャ"""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """テスト用ユーザーのフィクスチャ"""
    from src.services.auth.auth_service import hash_password
    
    user = User(
        email="test@example.com",
        username="testuser",
        password_hash=hash_password("Test123!@#"),
        is_active=True,
        is_verified=True,
        role="user"
    )
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    return user

@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """管理者ユーザーのフィクスチャ"""
    from src.services.auth.auth_service import hash_password
    
    admin = User(
        email="admin@example.com",
        username="admin",
        password_hash=hash_password("Admin123!@#"),
        is_active=True,
        is_verified=True,
        role="admin"
    )
    
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    
    return admin

@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    """認証ヘッダーのフィクスチャ"""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "Test123!@#"
        }
    )
    
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture
async def test_api_key(db_session: AsyncSession, test_user: User) -> APIKey:
    """テスト用APIキーのフィクスチャ"""
    from src.services.auth.api_key_manager import APIKeyManager
    
    manager = APIKeyManager()
    encrypted_key = manager._encrypt_key("test_api_key_12345")
    
    api_key = APIKey(
        key_id="test_key_001",
        service=ServiceType.SHOPIFY,
        encrypted_key=encrypted_key,
        user_id=test_user.id,
        name="Test Shopify Key",
        status="active"
    )
    
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    
    return api_key

@pytest.fixture
def mock_external_api(monkeypatch):
    """外部APIのモック"""
    import httpx
    
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.json_data = json_data
            self.status_code = status_code
        
        def json(self):
            return self.json_data
        
        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    message=f"Error {self.status_code}",
                    request=None,
                    response=self
                )
    
    async def mock_get(*args, **kwargs):
        url = args[0] if args else kwargs.get('url', '')
        
        if 'shopify' in url:
            return MockResponse({
                'shop': {'name': 'Test Shop', 'email': 'shop@test.com'}
            })
        elif 'stripe' in url:
            return MockResponse({
                'id': 'acct_test123',
                'email': 'stripe@test.com'
            })
        
        return MockResponse({}, 404)
    
    async def mock_post(*args, **kwargs):
        url = args[0] if args else kwargs.get('url', '')
        
        if 'oauth/token' in url:
            return MockResponse({
                'access_token': 'mock_access_token',
                'refresh_token': 'mock_refresh_token',
                'expires_in': 3600
            })
        
        return MockResponse({}, 404)
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)

@pytest.fixture
def mock_celery_task(monkeypatch):
    """Celeryタスクのモック"""
    
    class MockTask:
        def delay(self, *args, **kwargs):
            return MockAsyncResult()
        
        def apply_async(self, *args, **kwargs):
            return MockAsyncResult()
    
    class MockAsyncResult:
        def __init__(self):
            self.id = "mock_task_id"
            self.state = "SUCCESS"
        
        def get(self, timeout=None):
            return {"status": "completed"}
        
        @property
        def ready(self):
            return True
        
        @property
        def successful(self):
            return True
    
    monkeypatch.setattr(
        "src.tasks.api_key_tasks.refresh_expiring_keys",
        MockTask()
    )
    monkeypatch.setattr(
        "src.tasks.api_key_tasks.cleanup_expired_sessions",
        MockTask()
    )

# テスト用環境変数
@pytest.fixture(autouse=True)
def set_test_env_vars(monkeypatch):
    """テスト用環境変数を設定"""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_12345")
    monkeypatch.setenv("ENCRYPTION_KEY", "test_encryption_key")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")