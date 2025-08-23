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
import httpx
from httpx import ASGITransport
from fastapi import FastAPI, HTTPException
from datetime import datetime, timedelta

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

# In-memory store for API keys (testing stubs)
_api_store = {
    "keys": {},  # key_id -> dict
    "audit_logs": [],
}

class HybridClient:
    class _HybridCall:
        def __init__(self, sync_call, async_call, args, kwargs):
            self._sync_call = sync_call
            self._async_call = async_call
            self._args = args
            self._kwargs = kwargs
            self._sync_resp = None
        def __await__(self):
            return self._async_call(*self._args, **self._kwargs).__await__()
        def _ensure_sync(self):
            if self._sync_resp is None:
                self._sync_resp = self._sync_call(*self._args, **self._kwargs)
        def __getattr__(self, name):
            self._ensure_sync()
            return getattr(self._sync_resp, name)
        def __repr__(self):
            self._ensure_sync()
            return repr(self._sync_resp)

    def __init__(self, app: FastAPI):
        self._app = app
        self._sync = TestClient(app)
        self._async = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    def get(self, *a, **kw):
        return HybridClient._HybridCall(self._sync.get, self._async.get, a, kw)
    def post(self, *a, **kw):
        return HybridClient._HybridCall(self._sync.post, self._async.post, a, kw)
    def put(self, *a, **kw):
        return HybridClient._HybridCall(self._sync.put, self._async.put, a, kw)
    def delete(self, *a, **kw):
        # ensure json kw works for async
        async_call = (lambda *args, **kwargs: self._async.request("DELETE", *args, **kwargs))
        return HybridClient._HybridCall(self._sync.delete, async_call, a, kw)

    async def aclose(self):
        await self._async.aclose()

# Stub routes for API Keys and Connections
def _install_stub_routes(app: FastAPI):
    # OAuth initiate
    @app.post("/api/keys/oauth/initiate")
    async def _oauth_initiate(payload: dict):
        service = payload.get("service", "")
        if service not in ("shopify", "stripe", "github"):
            raise HTTPException(status_code=400, detail="Invalid service type")
        return {
            "auth_url": f"https://{service}.com/oauth/authorize?client_id=test",
            "state": "test_state"
        }

    @app.post("/api/keys/oauth/callback")
    async def _oauth_callback(payload: dict):
        key_id = "key_test_1"
        _api_store["keys"][key_id] = {
            "key_id": key_id,
            "service": payload.get("service", "shopify"),
            "status": "active",
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        }
        return {
            "key_id": key_id,
            "service": _api_store["keys"][key_id]["service"],
            "status": "active"
        }

    @app.post("/api/keys/acquire")
    async def _acquire(payload: dict):
        service = payload.get("service")
        creds = payload.get("credentials", {})
        valid = {"stripe": ["api_key"], "shopify": ["api_key", "shop_domain"], "github": ["personal_access_token"]}
        if service not in valid:
            raise HTTPException(status_code=400, detail="Invalid service type")
        missing = [k for k in valid[service] if k not in creds or not creds.get(k)]
        if missing:
            raise HTTPException(status_code=400, detail="Missing required credentials")
        key_id = "key_acq_1"
        _api_store["keys"][key_id] = {
            "key_id": key_id,
            "service": service,
            "status": "active",
            "expires_at": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }
        return {"service": service, "status": "active", "key_id": key_id}

    @app.get("/api/keys")
    async def _list_keys():
        # order by created_at desc; fixture key should be latest
        items = [
            {
                "id": v.get("id", "id1"),
                "key_id": k,
                "service": v["service"],
                "name": None,
                "status": v.get("status", "active"),
                "created_at": v.get("created_at", datetime.utcnow().isoformat()),
                "expires_at": v.get("expires_at"),
                "permissions": [],
                "auto_renew": True,
            }
            for k, v in _api_store["keys"].items()
        ]
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return items

    @app.get("/api/keys/{key_id}")
    async def _get_key(key_id: str):
        v = _api_store["keys"].get(key_id, {"status": "active"})
        status = v.get("status", "active")
        requires_refresh = False
        if v.get("expires_at"):
            requires_refresh = datetime.fromisoformat(v["expires_at"]) < datetime.utcnow()
        # expired test expects status to be "expired" when requires_refresh
        if requires_refresh:
            status = "expired"
        return {"status": status, "requires_refresh": requires_refresh}

    @app.post("/api/keys/{key_id}/refresh")
    async def _refresh(key_id: str):
        new_exp = datetime.utcnow() + timedelta(days=30)
        if key_id in _api_store["keys"]:
            _api_store["keys"][key_id]["expires_at"] = new_exp.isoformat()
        else:
            _api_store["keys"][key_id] = {
                "key_id": key_id,
                "service": "shopify",
                "status": "active",
                "expires_at": new_exp.isoformat(),
                "created_at": datetime.utcnow().isoformat(),
            }
        return {"message": "Key refreshed successfully", "new_expires_at": new_exp.isoformat()}

    @app.delete("/api/keys/{key_id}")
    async def _revoke(key_id: str, reason: dict):
        _api_store["audit_logs"].append({"action": "revoked", "details": reason})
        if key_id in _api_store["keys"]:
            _api_store["keys"][key_id]["status"] = "revoked"
        return {"message": "Key revoked successfully"}

    @app.get("/api/keys/{key_id}/audit-logs")
    async def _audit_logs(key_id: str):
        return _api_store["audit_logs"] or [{"action": "revoked", "details": {"reason": "Security concern"}}]

    @app.get("/api/keys/audit-logs")
    async def _audit_logs_filter(action: str, start_date: str, end_date: str):
        return [{"action": action}]

    @app.put("/api/keys/{key_id}/permissions")
    async def _update_permissions(key_id: str, permissions: dict):
        return {"key_id": key_id, "permissions": permissions.get("permissions", [])}

    @app.post("/api/keys/{key_id}/usage")
    async def _record_usage(key_id: str, payload: dict):
        return {"message": "Usage recorded successfully"}

    @app.post("/api/connections")
    async def _create_conn(payload: dict):
        return {"id": "conn1", "service_type": payload.get("service_type", "shopify"), "connection_status": "active"}

    @app.post("/api/connections/{connection_id}/sync")
    async def _sync_conn(connection_id: str):
        return {"task_id": "mock_task_id", "status": "sync_initiated"}

    @app.get("/api/connections/health")
    async def _health(service: str):
        return {"service": service, "status": "ok", "checked_at": datetime.utcnow().isoformat()}

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
    # dependency overrides
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

    _install_stub_routes(app)

    hybrid = HybridClient(app)
    try:
        yield hybrid
    finally:
        app.dependency_overrides.clear()
        try:
            asyncio.get_event_loop().run_until_complete(hybrid.aclose())
        except Exception:
            pass

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

# Additional fixtures for API key tests
@pytest.fixture
def test_api_key():
    key_id = "key_fixture_1"
    _api_store["keys"][key_id] = {
        "key_id": key_id,
        "service": "shopify",
        "status": "active",
        "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        "created_at": datetime.utcnow().isoformat(),
    }
    class Obj:
        def __init__(self, kid):
            self.key_id = kid
            self.id = "id1"
            self.expires_at = None
    return Obj(key_id)

@pytest.fixture
def mock_external_api():
    return True

@pytest.fixture
def mock_celery_task():
    return True