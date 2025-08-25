def test_ai_health_uses_internal_token(monkeypatch, client):
    # 内部トークン設定時にヘルスチェックが403にならないようにヘッダが付与されることを確認
    monkeypatch.setenv("AI_INTERNAL_TOKEN", "test-token")
    resp = client.get("/health")
    assert resp.status_code in (200, 503)
"""
APIキー管理の統合テスト
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient

from src.models.api_key import ServiceType, APIKeyStatus
from src.models.user import User

class TestAPIKeyManagement:
    """APIキー管理の統合テスト"""
    
    @pytest.mark.asyncio
    async def test_oauth_flow_initiation(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """OAuth認証フローの開始テスト"""
        response = await client.post(
            "/api/keys/oauth/initiate",
            json={
                "service": "shopify",
                "redirect_uri": "http://localhost:3000/callback"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "state" in data
        assert "shopify.com" in data["auth_url"]
    
    @pytest.mark.asyncio
    async def test_oauth_callback_exchange(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_external_api
    ):
        """OAuthコールバックとトークン交換のテスト"""
        # まずOAuthフローを開始
        init_response = await client.post(
            "/api/keys/oauth/initiate",
            json={
                "service": "shopify",
                "redirect_uri": "http://localhost:3000/callback"
            },
            headers=auth_headers
        )
        state = init_response.json()["state"]
        
        # コールバックを処理
        response = await client.post(
            "/api/keys/oauth/callback",
            json={
                "service": "shopify",
                "code": "test_auth_code",
                "state": state
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "key_id" in data
        assert data["service"] == "shopify"
        assert data["status"] == "active"
    
    @pytest.mark.asyncio
    async def test_direct_api_key_acquisition(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_external_api
    ):
        """直接APIキー取得のテスト"""
        response = await client.post(
            "/api/keys/acquire",
            json={
                "service": "stripe",
                "credentials": {
                    "api_key": "sk_test_123456789"
                }
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "stripe"
        assert data["status"] == "active"
        assert "key_id" in data
    
    @pytest.mark.asyncio
    async def test_list_user_api_keys(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key
    ):
        """ユーザーのAPIキー一覧取得テスト"""
        response = await client.get(
            "/api/keys",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["key_id"] == test_api_key.key_id
    
    @pytest.mark.asyncio
    async def test_refresh_api_key(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key,
        mock_external_api
    ):
        """APIキーの更新テスト"""
        response = await client.post(
            f"/api/keys/{test_api_key.key_id}/refresh",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Key refreshed successfully"
        assert "new_expires_at" in data
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key
    ):
        """APIキーの無効化テスト"""
        response = await client.delete(
            f"/api/keys/{test_api_key.key_id}",
            json={"reason": "No longer needed"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Key revoked successfully"
    
    @pytest.mark.asyncio
    async def test_api_key_usage_tracking(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key
    ):
        """APIキー使用状況の追跡テスト"""
        # 使用状況を記録
        await client.post(
            f"/api/keys/{test_api_key.key_id}/usage",
            json={
                "endpoint": "/api/products",
                "method": "GET",
                "status_code": 200,
                "response_time_ms": 150
            },
            headers=auth_headers
        )
        
        # 統計を取得
        response = await client.get(
            f"/api/keys/{test_api_key.key_id}/statistics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_requests"] >= 1
        assert data["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_api_key_permissions(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key
    ):
        """APIキーの権限管理テスト"""
        # 権限を更新
        response = await client.put(
            f"/api/keys/{test_api_key.key_id}/permissions",
            json={
                "permissions": ["read:products", "write:orders"]
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "read:products" in data["permissions"]
        assert "write:orders" in data["permissions"]
    
    @pytest.mark.asyncio
    async def test_api_key_rotation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key,
        mock_celery_task
    ):
        """APIキーのローテーションテスト"""
        response = await client.post(
            f"/api/keys/{test_api_key.key_id}/rotate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "mock_task_id"
        assert data["status"] == "rotation_initiated"

class TestAPIKeyValidation:
    """APIキーのバリデーションテスト"""
    
    @pytest.mark.asyncio
    async def test_invalid_service_type(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """無効なサービスタイプのテスト"""
        response = await client.post(
            "/api/keys/acquire",
            json={
                "service": "invalid_service",
                "credentials": {"key": "test"}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Invalid service type" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_missing_credentials(
        self,
        client: AsyncClient,
        auth_headers: dict
    ):
        """認証情報不足のテスト"""
        response = await client.post(
            "/api/keys/acquire",
            json={
                "service": "stripe",
                "credentials": {}
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Missing required credentials" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_expired_key_access(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session,
        test_api_key
    ):
        """期限切れキーへのアクセステスト"""
        # キーを期限切れに設定
        test_api_key.expires_at = datetime.utcnow() - timedelta(days=1)
        test_api_key.status = APIKeyStatus.EXPIRED
        await db_session.commit()
        
        response = await client.get(
            f"/api/keys/{test_api_key.key_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "expired"
        assert data["requires_refresh"] == True

class TestAPIKeyAuditLog:
    """APIキーの監査ログテスト"""
    
    @pytest.mark.asyncio
    async def test_audit_log_creation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key
    ):
        """監査ログ作成のテスト"""
        # アクションを実行
        await client.delete(
            f"/api/keys/{test_api_key.key_id}",
            json={"reason": "Security concern"},
            headers=auth_headers
        )
        
        # 監査ログを確認
        response = await client.get(
            f"/api/keys/{test_api_key.key_id}/audit-logs",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) > 0
        assert logs[0]["action"] == "revoked"
        assert logs[0]["details"]["reason"] == "Security concern"
    
    @pytest.mark.asyncio
    async def test_audit_log_filtering(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key
    ):
        """監査ログのフィルタリングテスト"""
        response = await client.get(
            "/api/keys/audit-logs",
            params={
                "action": "created",
                "start_date": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "end_date": datetime.utcnow().isoformat()
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        logs = response.json()
        for log in logs:
            assert log["action"] == "created"

class TestServiceConnection:
    """サービス接続の統合テスト"""
    
    @pytest.mark.asyncio
    async def test_create_service_connection(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_api_key
    ):
        """サービス接続の作成テスト"""
        response = await client.post(
            "/api/connections",
            json={
                "service_type": "shopify",
                "api_key_id": test_api_key.id,
                "config": {
                    "shop_domain": "test-shop.myshopify.com",
                    "webhook_url": "https://example.com/webhook"
                }
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["service_type"] == "shopify"
        assert data["connection_status"] == "active"
    
    @pytest.mark.asyncio
    async def test_sync_service_data(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_external_api,
        mock_celery_task
    ):
        """サービスデータの同期テスト"""
        # まず接続を作成
        conn_response = await client.post(
            "/api/connections",
            json={
                "service_type": "shopify",
                "config": {"shop_domain": "test.myshopify.com"}
            },
            headers=auth_headers
        )
        connection_id = conn_response.json()["id"]
        
        # 同期を実行
        response = await client.post(
            f"/api/connections/{connection_id}/sync",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "mock_task_id"
        assert data["status"] == "sync_initiated"
    
    @pytest.mark.asyncio
    async def test_connection_health_check(
        self,
        client: AsyncClient,
        auth_headers: dict,
        mock_external_api
    ):
        """接続のヘルスチェックテスト"""
        response = await client.get(
            "/api/connections/health",
            params={"service": "shopify"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "shopify"
        assert "status" in data
        assert "checked_at" in data