"""
改善実装（Refresh/LPR/Preview）の軽量テスト
LIGHT_TESTS=1 を想定。外部依存はモック/パッチで回避。
"""

import asyncio
import json
import pytest
from types import SimpleNamespace


async def _maybe_await(result):
    if asyncio.iscoroutine(result):
        return await result
    return result


async def _post(client, url: str, **kwargs):
    return await _maybe_await(client.post(url, **kwargs))


async def _get(client, url: str, **kwargs):
    return await _maybe_await(client.get(url, **kwargs))


@pytest.mark.asyncio
async def test_auth_refresh_flow(client, monkeypatch):
    """/auth/login → /auth/refresh ローテーションの流れを検証（Refreshはモック）。"""
    # Patch RefreshTokenManager methods
    from src.api.v1 import auth as auth_module

    async def fake_generate(self, **kwargs):
        return "refresh_token_initial"

    async def fake_validate(self, token):
        if token == "refresh_token_initial":
            return {
                "user_id": "normal-user-id",
                "username": "user",
                "roles": ["user"],
                "device_id": "dev-1",
            }
        if token == "refresh_token_rotated":
            return {
                "user_id": "normal-user-id",
                "username": "user",
                "roles": ["user"],
                "device_id": "dev-1",
            }
        return None

    async def fake_rotate(self, token):
        assert token == "refresh_token_initial"
        return "refresh_token_rotated", {
            "user_id": "normal-user-id",
            "username": "user",
            "roles": ["user"],
            "device_id": "dev-1",
        }

    monkeypatch.setattr(auth_module.RefreshTokenManager, "generate", fake_generate, raising=False)
    monkeypatch.setattr(auth_module.RefreshTokenManager, "validate", fake_validate, raising=False)
    monkeypatch.setattr(auth_module.RefreshTokenManager, "rotate", fake_rotate, raising=False)

    # Login (開発用ダミー認証を使用)
    res = await _post(
        client,
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Cookieからrefresh_tokenを取得（LIGHT_TESTSではヘッダに格納される）
    # httpx.AsyncClientはレスポンスのcookies経由で参照可能
    refresh_cookie = res.cookies.get("refresh_token") or res.cookies.get(
        auth_module.settings.refresh_cookie_name
    )
    assert refresh_cookie == "refresh_token_initial"

    # Refresh（Cookie優先だがBodyも許容）
    res2 = await _post(
        client,
        "/api/v1/auth/refresh",
        json={"refresh_token": "refresh_token_initial"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is True
    assert "access_token" in data2["data"]


@pytest.mark.asyncio
async def test_lpr_fail_closed_in_production(client, monkeypatch):
    """本番環境ではLPRトークン無しで /api/v1/nlp/health にアクセスできないこと。"""
    # ENV を production に強制
    from src.core import config as cfg
    monkeypatch.setattr(cfg.settings, "environment", "production", raising=False)

    res = await _get(client, "/api/v1/nlp/health")
    # LPRミドルウェアが 401 を返す（トークン欠如）
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_preview_redis_cache_flow(client, monkeypatch):
    """プレビュー生成→Redis保存→取得（refine前に取り出し）をモックRedisで検証。"""
    # Patch get_current_user to bypass auth dependency
    from src.api.v1 import preview as preview_module

    async def fake_current_user():
        return SimpleNamespace(id="u-1", user_id="u-1")

    monkeypatch.setattr(preview_module, "get_current_user", lambda: fake_current_user(), raising=False)

    # Patch Redis client with simple in-memory dict
    store = {}

    class FakeRedis:
        async def setex(self, key, ttl, value):
            store[key] = value

        async def get(self, key):
            return store.get(key)

    from src.api.v1 import preview as pv
    monkeypatch.setattr(pv, "get_redis", lambda: FakeRedis(), raising=False)

    # generate
    body = {
        "service_id": "svc-1",
        "changes": [
            {
                "type": "content",
                "target": "#title",
                "property": "text",
                "old_value": "old",
                "new_value": "new",
            }
        ],
    }
    res = await _post(client, "/api/v1/preview/generate", json=body)
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    preview_id = payload["data"]["id"]

    # refine で Redis から取得されることを検証
    res2 = await _post(
        client,
        f"/api/v1/preview/{preview_id}/refine",
        json={"refinement": "もっと大きく"},
    )
    assert res2.status_code == 200
    payload2 = res2.json()
    assert payload2["success"] is True
    assert payload2["data"]["id"] != preview_id  # 新しいIDが払い出される

