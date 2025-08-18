"""
SaaSコネクタのテスト
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime

from src.connectors.base import ConnectorConfig, ConnectorCredentials, ResourceSnapshot
from src.connectors.shopify import ShopifyConnector
from src.connectors.stripe import StripeConnector
from src.connectors.manager import ConnectorManager

@pytest.mark.unit
class TestShopifyConnector:
    """Shopifyコネクタのテスト"""
    
    @pytest.fixture
    def shopify_connector(self):
        """Shopifyコネクタのフィクスチャ"""
        credentials = ConnectorCredentials(
            access_token="test-token"
        )
        return ShopifyConnector("test-store.myshopify.com", credentials)
    
    @pytest.mark.asyncio
    async def test_initialize(self, shopify_connector):
        """初期化テスト"""
        with patch.object(shopify_connector, 'validate_connection', return_value=True):
            result = await shopify_connector.initialize()
            assert result is True
            assert shopify_connector._session is not None
    
    @pytest.mark.asyncio
    async def test_list_resources(self, shopify_connector, mock_shopify_product):
        """リソース一覧取得テスト"""
        shopify_connector._session = AsyncMock()
        shopify_connector._session.get.return_value = AsyncMock(
            status_code=200,
            json=AsyncMock(return_value={"products": [mock_shopify_product]})
        )
        
        products = await shopify_connector.list_resources("product")
        
        assert len(products) == 1
        assert products[0]["id"] == mock_shopify_product["id"]
    
    @pytest.mark.asyncio
    async def test_get_resource(self, shopify_connector, mock_shopify_product):
        """単一リソース取得テスト"""
        shopify_connector._session = AsyncMock()
        shopify_connector._session.get.return_value = AsyncMock(
            status_code=200,
            json=AsyncMock(return_value={"product": mock_shopify_product})
        )
        
        product = await shopify_connector.get_resource("product", "123456789")
        
        assert product["id"] == mock_shopify_product["id"]
        assert product["title"] == mock_shopify_product["title"]
    
    @pytest.mark.asyncio
    async def test_create_snapshot(self, shopify_connector, mock_shopify_product):
        """スナップショット作成テスト"""
        with patch.object(shopify_connector, 'get_resource', return_value=mock_shopify_product):
            snapshot = await shopify_connector.create_snapshot("product", "123456789")
            
            assert isinstance(snapshot, ResourceSnapshot)
            assert snapshot.resource_id == "123456789"
            assert snapshot.resource_type == "product"
            assert snapshot.data == mock_shopify_product
    
    @pytest.mark.asyncio
    async def test_generate_preview(self, shopify_connector, mock_shopify_product):
        """プレビュー生成テスト"""
        snapshot = ResourceSnapshot(
            resource_id="123456789",
            resource_type="product",
            data=mock_shopify_product,
            metadata={},
            captured_at=datetime.utcnow(),
            checksum="test-checksum"
        )
        
        changes = {"title": "新しいタイトル", "variants.0.price": "2000.00"}
        
        preview = await shopify_connector.generate_preview(snapshot, changes)
        
        assert "html" in preview
        assert "css" in preview
        assert preview["data"]["title"] == "新しいタイトル"
    
    @pytest.mark.asyncio
    async def test_validate_changes(self, shopify_connector):
        """変更検証テスト"""
        # 有効な変更
        valid, errors = await shopify_connector.validate_changes(
            "product", "123", {"title": "New Title"}
        )
        assert valid is True
        assert len(errors) == 0
        
        # 無効な変更
        invalid, errors = await shopify_connector.validate_changes(
            "product", "123", {"title": ""}
        )
        assert invalid is False
        assert len(errors) > 0

@pytest.mark.unit
class TestStripeConnector:
    """Stripeコネクタのテスト"""
    
    @pytest.fixture
    def stripe_connector(self):
        """Stripeコネクタのフィクスチャ"""
        credentials = ConnectorCredentials(
            api_key="sk_test_123"
        )
        return StripeConnector(credentials, test_mode=True)
    
    @pytest.mark.asyncio
    async def test_initialize(self, stripe_connector):
        """初期化テスト"""
        with patch.object(stripe_connector, 'validate_connection', return_value=True):
            result = await stripe_connector.initialize()
            assert result is True
            assert stripe_connector._session is not None
    
    @pytest.mark.asyncio
    async def test_list_resources(self, stripe_connector, mock_stripe_customer):
        """リソース一覧取得テスト"""
        stripe_connector._session = AsyncMock()
        stripe_connector._session.get.return_value = AsyncMock(
            status_code=200,
            json=AsyncMock(return_value={"data": [mock_stripe_customer]})
        )
        
        customers = await stripe_connector.list_resources("customer")
        
        assert len(customers) == 1
        assert customers[0]["id"] == mock_stripe_customer["id"]
    
    @pytest.mark.asyncio
    async def test_format_params(self, stripe_connector):
        """パラメータフォーマットテスト"""
        params = {
            "email": "test@example.com",
            "metadata": {
                "order_id": "123",
                "source": "web"
            }
        }
        
        formatted = stripe_connector._format_params(params)
        
        assert "email=test@example.com" in formatted
        assert "metadata[order_id]=123" in formatted
        assert "metadata[source]=web" in formatted
    
    @pytest.mark.asyncio
    async def test_generate_preview(self, stripe_connector, mock_stripe_customer):
        """プレビュー生成テスト"""
        snapshot = ResourceSnapshot(
            resource_id="cus_test123",
            resource_type="customer",
            data=mock_stripe_customer,
            metadata={},
            captured_at=datetime.utcnow(),
            checksum="test-checksum"
        )
        
        changes = {"name": "Updated Customer", "email": "updated@example.com"}
        
        preview = await stripe_connector.generate_preview(snapshot, changes)
        
        assert "html" in preview
        assert "css" in preview
        assert preview["data"]["name"] == "Updated Customer"
        assert preview["data"]["email"] == "updated@example.com"

@pytest.mark.unit
class TestConnectorManager:
    """コネクタマネージャーのテスト"""
    
    @pytest.fixture
    def connector_manager(self):
        """コネクタマネージャーのフィクスチャ"""
        return ConnectorManager()
    
    @pytest.mark.asyncio
    async def test_register_connector(self, connector_manager):
        """コネクタ登録テスト"""
        credentials = ConnectorCredentials(access_token="test-token")
        
        with patch('src.connectors.shopify.ShopifyConnector.initialize', return_value=True):
            result = await connector_manager.register_connector(
                "test-shopify",
                "shopify",
                credentials,
                store_domain="test-store.myshopify.com"
            )
            
            assert result is True
            assert "test-shopify" in connector_manager.connectors
    
    def test_get_connector(self, connector_manager):
        """コネクタ取得テスト"""
        mock_connector = Mock()
        connector_manager.connectors["test"] = mock_connector
        
        connector = connector_manager.get_connector("test")
        assert connector == mock_connector
        
        none_connector = connector_manager.get_connector("nonexistent")
        assert none_connector is None
    
    def test_list_connectors(self, connector_manager):
        """コネクタ一覧取得テスト"""
        mock_connector = Mock()
        mock_connector.config = ConnectorConfig(
            name="Test",
            type="ecommerce",
            auth_method="api_key",
            base_url="https://test.com"
        )
        mock_connector._initialized = True
        
        connector_manager.connectors["test"] = mock_connector
        
        connectors = connector_manager.list_connectors()
        
        assert len(connectors) == 1
        assert connectors[0]["name"] == "test"
        assert connectors[0]["type"] == "ecommerce"
    
    @pytest.mark.asyncio
    async def test_execute_cross_platform(self, connector_manager):
        """クロスプラットフォーム実行テスト"""
        mock_connector1 = Mock()
        mock_connector1.list_resources = AsyncMock(return_value=[{"id": 1}])
        
        mock_connector2 = Mock()
        mock_connector2.list_resources = AsyncMock(return_value=[{"id": 2}])
        
        connector_manager.connectors["conn1"] = mock_connector1
        connector_manager.connectors["conn2"] = mock_connector2
        
        results = await connector_manager.execute_cross_platform(
            "list_resources",
            ["conn1", "conn2"],
            {"resource_type": "product"}
        )
        
        assert "conn1" in results
        assert "conn2" in results
        assert results["conn1"] == [{"id": 1}]
        assert results["conn2"] == [{"id": 2}]
    
    def test_apply_mapping(self, connector_manager):
        """フィールドマッピングテスト"""
        resource = {
            "title": "Product Title",
            "price": 1000,
            "details": {
                "sku": "TEST-001",
                "weight": 500
            }
        }
        
        mapping = {
            "title": "name",
            "price": "amount",
            "details.sku": "product_code",
            "details.weight": "shipping.weight"
        }
        
        mapped = connector_manager._apply_mapping(resource, mapping)
        
        assert mapped["name"] == "Product Title"
        assert mapped["amount"] == 1000
        assert mapped["product_code"] == "TEST-001"
        assert mapped["shipping"]["weight"] == 500