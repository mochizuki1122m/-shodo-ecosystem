"""
テスト設定とフィクスチャ
"""

import pytest
import asyncio
from typing import Generator, AsyncGenerator
from datetime import datetime
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# テスト用の環境変数設定
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["ENCRYPTION_KEY"] = "test-encryption-key"

from src.main import app
from src.core.security import JWTManager, TokenData
from src.services.database import Base, get_db

# テスト用データベースエンジン
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """イベントループフィクスチャ"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def async_engine():
    """非同期データベースエンジン"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()

@pytest.fixture(scope="function")
async def async_session(async_engine):
    """非同期データベースセッション"""
    async_session_maker = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session

@pytest.fixture(scope="function")
def sync_engine():
    """同期データベースエンジン"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    engine.dispose()

@pytest.fixture(scope="function")
def sync_session(sync_engine):
    """同期データベースセッション"""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
    session = SessionLocal()
    
    yield session
    
    session.close()

@pytest.fixture(scope="function")
def test_app(sync_session):
    """テスト用FastAPIアプリケーション"""
    # データベース依存性をオーバーライド
    def override_get_db():
        try:
            yield sync_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield app
    
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def client(test_app):
    """同期テストクライアント"""
    with TestClient(test_app) as c:
        yield c

@pytest.fixture(scope="function")
async def async_client(test_app):
    """非同期テストクライアント"""
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="function")
def auth_headers():
    """認証ヘッダー"""
    token_data = TokenData(
        user_id="test-user-id",
        username="testuser",
        email="test@example.com",
        roles=["user"],
        exp=datetime.utcnow()
    )
    
    token = JWTManager.create_access_token(token_data.dict())
    
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def admin_headers():
    """管理者認証ヘッダー"""
    token_data = TokenData(
        user_id="admin-user-id",
        username="admin",
        email="admin@example.com",
        roles=["admin", "user"],
        exp=datetime.utcnow()
    )
    
    token = JWTManager.create_access_token(token_data.dict())
    
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="function")
def sample_nlp_request():
    """サンプルNLPリクエスト"""
    return {
        "text": "これはテスト用のテキストです。",
        "text_type": "plain",
        "analysis_type": "hybrid",
        "options": {},
        "context": {}
    }

@pytest.fixture(scope="function")
def sample_preview_request():
    """サンプルプレビューリクエスト"""
    return {
        "source_type": "shopify",
        "source_id": "product_123",
        "modifications": {
            "title": "新しいタイトル",
            "price": 1000
        },
        "preview_type": "html"
    }

@pytest.fixture(scope="function")
def sample_user():
    """サンプルユーザー"""
    return {
        "user_id": "test-user-id",
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "roles": ["user"],
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

@pytest.fixture(scope="function")
def mock_vllm_response():
    """モックvLLMレスポンス"""
    return {
        "choices": [{
            "text": "これはAIによる解析結果です。",
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }

@pytest.fixture(scope="function")
def mock_shopify_product():
    """モックShopify商品"""
    return {
        "id": 123456789,
        "title": "テスト商品",
        "body_html": "<p>商品の説明</p>",
        "vendor": "テストベンダー",
        "product_type": "テストタイプ",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "tags": "テスト,サンプル",
        "variants": [{
            "id": 987654321,
            "product_id": 123456789,
            "title": "Default Title",
            "price": "1000.00",
            "sku": "TEST-001",
            "inventory_quantity": 100
        }],
        "images": [{
            "id": 111111111,
            "product_id": 123456789,
            "src": "https://example.com/image.jpg",
            "alt": "テスト画像"
        }]
    }

@pytest.fixture(scope="function")
def mock_stripe_customer():
    """モックStripe顧客"""
    return {
        "id": "cus_test123",
        "object": "customer",
        "created": 1640995200,
        "email": "test@example.com",
        "name": "Test Customer",
        "phone": "+81-90-1234-5678",
        "balance": 0,
        "currency": "jpy",
        "delinquent": False,
        "metadata": {}
    }

# マーカー定義
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.slow = pytest.mark.slow
pytest.mark.skip_ci = pytest.mark.skip_ci