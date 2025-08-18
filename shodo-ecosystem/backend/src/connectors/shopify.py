"""
Shopifyコネクタ実装
Eコマースプラットフォーム連携
"""

import httpx
import hashlib
import hmac
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from .base import (
    BaseSaaSConnector, ConnectorConfig, ConnectorCredentials,
    ConnectorType, AuthMethod, ResourceSnapshot, ChangeSet
)

class ShopifyConnector(BaseSaaSConnector):
    """Shopify API連携コネクタ"""
    
    RESOURCE_TYPES = {
        "product": "products",
        "order": "orders",
        "customer": "customers",
        "collection": "collections",
        "inventory": "inventory_items",
        "variant": "variants",
        "page": "pages",
        "blog": "blogs",
        "article": "articles",
        "theme": "themes"
    }
    
    def __init__(self, store_domain: str, credentials: ConnectorCredentials):
        config = ConnectorConfig(
            name="Shopify",
            type=ConnectorType.ECOMMERCE,
            auth_method=AuthMethod.BEARER,
            base_url=f"https://{store_domain}/admin/api/2024-01",
            api_version="2024-01",
            rate_limit=40,  # Shopify Plus rate limit
            timeout=30,
            retry_count=3,
            retry_delay=1
        )
        super().__init__(config, credentials)
        self.store_domain = store_domain
        
    async def initialize(self) -> bool:
        """初期化"""
        self._session = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=self._get_headers(),
            timeout=self.config.timeout
        )
        self._initialized = await self.validate_connection()
        return self._initialized
    
    async def authenticate(self) -> bool:
        """認証"""
        try:
            response = await self._session.get("/shop.json")
            return response.status_code == 200
        except Exception:
            return False
    
    async def validate_connection(self) -> bool:
        """接続検証"""
        try:
            response = await self._session.get("/shop.json")
            return response.status_code == 200
        except Exception:
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """ヘッダー生成"""
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": self.credentials.access_token or ""
        }
        if self.credentials.custom_headers:
            headers.update(self.credentials.custom_headers)
        return headers
    
    # === 読み取り操作 ===
    
    async def list_resources(
        self,
        resource_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = 50,
        offset: Optional[int] = 0
    ) -> List[Dict[str, Any]]:
        """リソース一覧取得"""
        endpoint = self.RESOURCE_TYPES.get(resource_type, resource_type)
        params = {
            "limit": min(limit or 50, 250),  # Shopify max is 250
            "page": (offset // (limit or 50)) + 1 if offset else 1
        }
        
        if filters:
            params.update(filters)
        
        try:
            response = await self._session.get(f"/{endpoint}.json", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get(endpoint, [])
        except Exception as e:
            print(f"Error listing {resource_type}: {e}")
            return []
    
    async def get_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """単一リソース取得"""
        endpoint = self.RESOURCE_TYPES.get(resource_type, resource_type)
        singular = endpoint.rstrip('s')  # Simple singularization
        
        try:
            response = await self._session.get(f"/{endpoint}/{resource_id}.json")
            response.raise_for_status()
            data = response.json()
            return data.get(singular, data)
        except Exception as e:
            print(f"Error getting {resource_type} {resource_id}: {e}")
            return None
    
    async def search_resources(
        self,
        resource_type: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """リソース検索"""
        # Shopify search API
        if resource_type == "product":
            endpoint = "/products/search.json"
        elif resource_type == "customer":
            endpoint = "/customers/search.json"
        elif resource_type == "order":
            endpoint = "/orders.json"
            filters = filters or {}
            filters["status"] = "any"
            filters["name"] = query
            return await self.list_resources("order", filters)
        else:
            return await self.list_resources(resource_type, {"query": query})
        
        try:
            response = await self._session.get(endpoint, params={"query": query})
            response.raise_for_status()
            data = response.json()
            return data.get(self.RESOURCE_TYPES.get(resource_type, resource_type), [])
        except Exception as e:
            print(f"Error searching {resource_type}: {e}")
            return []
    
    # === スナップショット・プレビュー ===
    
    async def create_snapshot(
        self,
        resource_type: str,
        resource_id: str
    ) -> ResourceSnapshot:
        """スナップショット作成"""
        resource = await self.get_resource(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource {resource_type}/{resource_id} not found")
        
        # チェックサム計算
        data_str = json.dumps(resource, sort_keys=True)
        checksum = hashlib.sha256(data_str.encode()).hexdigest()
        
        return ResourceSnapshot(
            resource_id=resource_id,
            resource_type=resource_type,
            data=resource,
            metadata={
                "store": self.store_domain,
                "api_version": self.config.api_version
            },
            captured_at=datetime.utcnow(),
            checksum=checksum
        )
    
    async def generate_preview(
        self,
        snapshot: ResourceSnapshot,
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """プレビュー生成"""
        # スナップショットデータのコピー
        preview_data = snapshot.data.copy()
        
        # 変更を適用（実際のAPIコールはしない）
        for key, value in changes.items():
            if "." in key:  # ネストされたキー
                keys = key.split(".")
                target = preview_data
                for k in keys[:-1]:
                    target = target.setdefault(k, {})
                target[keys[-1]] = value
            else:
                preview_data[key] = value
        
        # プレビューHTML生成（商品の場合）
        if snapshot.resource_type == "product":
            html = self._generate_product_preview_html(preview_data)
            css = self._generate_product_preview_css()
        else:
            html = f"<pre>{json.dumps(preview_data, indent=2)}</pre>"
            css = "pre { font-family: monospace; background: #f5f5f5; padding: 10px; }"
        
        return {
            "html": html,
            "css": css,
            "data": preview_data,
            "changes": self._calculate_changes(snapshot.data, preview_data),
            "confidence": 0.95
        }
    
    def _generate_product_preview_html(self, product: Dict[str, Any]) -> str:
        """商品プレビューHTML生成"""
        return f"""
        <div class="shopify-product-preview">
            <div class="product-image">
                <img src="{product.get('image', {}).get('src', '/placeholder.jpg')}" alt="{product.get('title', '')}">
            </div>
            <div class="product-details">
                <h1 class="product-title">{product.get('title', 'Untitled Product')}</h1>
                <div class="product-vendor">{product.get('vendor', '')}</div>
                <div class="product-price">
                    {product.get('variants', [{}])[0].get('price', '0.00')} {product.get('variants', [{}])[0].get('currency', 'JPY')}
                </div>
                <div class="product-description">
                    {product.get('body_html', '')}
                </div>
                <div class="product-tags">
                    {', '.join(product.get('tags', '').split(','))}
                </div>
            </div>
        </div>
        """
    
    def _generate_product_preview_css(self) -> str:
        """商品プレビューCSS生成"""
        return """
        .shopify-product-preview {
            display: flex;
            gap: 20px;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .product-image {
            flex: 0 0 300px;
        }
        .product-image img {
            width: 100%;
            height: auto;
            border-radius: 8px;
        }
        .product-details {
            flex: 1;
        }
        .product-title {
            font-size: 28px;
            margin: 0 0 10px;
            color: #333;
        }
        .product-vendor {
            color: #666;
            margin-bottom: 10px;
        }
        .product-price {
            font-size: 24px;
            font-weight: bold;
            color: #e74c3c;
            margin: 15px 0;
        }
        .product-description {
            line-height: 1.6;
            color: #444;
            margin: 20px 0;
        }
        .product-tags {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 20px;
        }
        """
    
    def _calculate_changes(self, original: Dict, modified: Dict) -> List[Dict[str, Any]]:
        """変更点の計算"""
        changes = []
        
        def compare_dicts(orig, mod, path=""):
            for key in set(list(orig.keys()) + list(mod.keys())):
                current_path = f"{path}.{key}" if path else key
                
                if key not in orig:
                    changes.append({
                        "type": "add",
                        "path": current_path,
                        "value": mod[key]
                    })
                elif key not in mod:
                    changes.append({
                        "type": "remove",
                        "path": current_path,
                        "old_value": orig[key]
                    })
                elif orig[key] != mod[key]:
                    if isinstance(orig[key], dict) and isinstance(mod[key], dict):
                        compare_dicts(orig[key], mod[key], current_path)
                    else:
                        changes.append({
                            "type": "modify",
                            "path": current_path,
                            "old_value": orig[key],
                            "new_value": mod[key]
                        })
        
        compare_dicts(original, modified)
        return changes
    
    async def validate_changes(
        self,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """変更の検証"""
        errors = []
        
        # 商品の検証
        if resource_type == "product":
            if "title" in changes and not changes["title"]:
                errors.append("Product title cannot be empty")
            if "variants" in changes:
                for variant in changes.get("variants", []):
                    if "price" in variant:
                        try:
                            float(variant["price"])
                        except ValueError:
                            errors.append(f"Invalid price: {variant['price']}")
        
        # 注文の検証
        elif resource_type == "order":
            if "financial_status" in changes:
                valid_statuses = ["pending", "authorized", "paid", "partially_paid", "refunded", "voided"]
                if changes["financial_status"] not in valid_statuses:
                    errors.append(f"Invalid financial status: {changes['financial_status']}")
        
        return len(errors) == 0, errors
    
    # === 変更操作 ===
    
    async def apply_changes(
        self,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any],
        dry_run: bool = False
    ) -> ChangeSet:
        """変更の適用"""
        # スナップショット作成
        snapshot = await self.create_snapshot(resource_type, resource_id)
        
        # 変更の検証
        valid, errors = await self.validate_changes(resource_type, resource_id, changes)
        if not valid:
            raise ValueError(f"Invalid changes: {', '.join(errors)}")
        
        change_set = ChangeSet(
            change_id=f"cs_{datetime.utcnow().timestamp()}",
            resource_id=resource_id,
            resource_type=resource_type,
            changes=self._calculate_changes(snapshot.data, changes),
            created_at=datetime.utcnow()
        )
        
        if not dry_run:
            # 実際の更新
            result = await self.update_resource(resource_type, resource_id, changes)
            if result:
                change_set.applied_at = datetime.utcnow()
        
        return change_set
    
    async def create_resource(
        self,
        resource_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """リソース作成"""
        endpoint = self.RESOURCE_TYPES.get(resource_type, resource_type)
        singular = endpoint.rstrip('s')
        
        try:
            response = await self._session.post(
                f"/{endpoint}.json",
                json={singular: data}
            )
            response.raise_for_status()
            result = response.json()
            return result.get(singular, result)
        except Exception as e:
            print(f"Error creating {resource_type}: {e}")
            raise
    
    async def update_resource(
        self,
        resource_type: str,
        resource_id: str,
        data: Dict[str, Any],
        partial: bool = True
    ) -> Dict[str, Any]:
        """リソース更新"""
        endpoint = self.RESOURCE_TYPES.get(resource_type, resource_type)
        singular = endpoint.rstrip('s')
        
        try:
            if partial:
                method = self._session.patch
            else:
                method = self._session.put
            
            response = await method(
                f"/{endpoint}/{resource_id}.json",
                json={singular: data}
            )
            response.raise_for_status()
            result = response.json()
            return result.get(singular, result)
        except Exception as e:
            print(f"Error updating {resource_type} {resource_id}: {e}")
            raise
    
    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
        soft_delete: bool = True
    ) -> bool:
        """リソース削除"""
        endpoint = self.RESOURCE_TYPES.get(resource_type, resource_type)
        
        try:
            if soft_delete and resource_type in ["product", "collection"]:
                # Shopifyでは商品を非公開にすることで論理削除
                return await self.update_resource(
                    resource_type,
                    resource_id,
                    {"status": "draft"}
                ) is not None
            else:
                response = await self._session.delete(f"/{endpoint}/{resource_id}.json")
                return response.status_code in [200, 204]
        except Exception as e:
            print(f"Error deleting {resource_type} {resource_id}: {e}")
            return False
    
    # === ロールバック ===
    
    async def rollback(self, change_set: ChangeSet) -> bool:
        """ロールバック"""
        if change_set.rolled_back_at:
            return False  # Already rolled back
        
        try:
            # 変更を逆適用
            for change in reversed(change_set.changes):
                if change["type"] == "modify":
                    await self.update_resource(
                        change_set.resource_type,
                        change_set.resource_id,
                        {change["path"]: change["old_value"]}
                    )
            
            change_set.rolled_back_at = datetime.utcnow()
            return True
        except Exception as e:
            print(f"Error rolling back: {e}")
            return False
    
    async def can_rollback(self, change_set: ChangeSet) -> bool:
        """ロールバック可能性チェック"""
        # 24時間以内の変更のみロールバック可能
        if change_set.applied_at:
            elapsed = datetime.utcnow() - change_set.applied_at
            return elapsed.total_seconds() < 86400
        return False
    
    # === Webhook ===
    
    async def register_webhook(
        self,
        event_types: List[str],
        callback_url: str
    ) -> str:
        """Webhook登録"""
        webhook_data = {
            "webhook": {
                "topic": event_types[0] if event_types else "orders/create",
                "address": callback_url,
                "format": "json"
            }
        }
        
        try:
            response = await self._session.post("/webhooks.json", json=webhook_data)
            response.raise_for_status()
            result = response.json()
            return str(result.get("webhook", {}).get("id", ""))
        except Exception as e:
            print(f"Error registering webhook: {e}")
            return ""
    
    async def verify_webhook(self, data: bytes, hmac_header: str) -> bool:
        """Webhook署名検証"""
        if not self.credentials.api_secret:
            return False
        
        calculated_hmac = hmac.new(
            self.credentials.api_secret.encode('utf-8'),
            data,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(calculated_hmac, hmac_header)