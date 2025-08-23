"""
Shopify API実装
"""

import httpx
from typing import Dict, List
from datetime import datetime
import os

from ...core.exceptions import ExternalAPIException

class ShopifyAPI:
    """Shopify API クライアント"""
    
    def __init__(self):
        self.shop_domain = os.getenv("SHOPIFY_SHOP_DOMAIN", "")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
        self.api_version = "2024-01"
        self.base_url = f"https://{self.shop_domain}/admin/api/{self.api_version}"
        
    async def get_products(self, limit: int = 50) -> List[Dict]:
        """商品一覧取得"""
        if not self.shop_domain or not self.access_token:
            # 開発環境用のモックデータ
            return self._get_mock_products()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/products.json",
                    headers={"X-Shopify-Access-Token": self.access_token},
                    params={"limit": limit}
                )
                response.raise_for_status()
                return response.json().get("products", [])
        except Exception as e:
            raise ExternalAPIException(f"Failed to fetch products: {str(e)}")
    
    async def get_orders(self, status: str = "any", limit: int = 50) -> List[Dict]:
        """注文一覧取得"""
        if not self.shop_domain or not self.access_token:
            return self._get_mock_orders()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/orders.json",
                    headers={"X-Shopify-Access-Token": self.access_token},
                    params={"status": status, "limit": limit}
                )
                response.raise_for_status()
                return response.json().get("orders", [])
        except Exception as e:
            raise ExternalAPIException(f"Failed to fetch orders: {str(e)}")
    
    async def get_customers(self, limit: int = 50) -> List[Dict]:
        """顧客一覧取得"""
        if not self.shop_domain or not self.access_token:
            return self._get_mock_customers()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/customers.json",
                    headers={"X-Shopify-Access-Token": self.access_token},
                    params={"limit": limit}
                )
                response.raise_for_status()
                return response.json().get("customers", [])
        except Exception as e:
            raise ExternalAPIException(f"Failed to fetch customers: {str(e)}")
    
    async def update_inventory(self, inventory_item_id: int, quantity: int) -> Dict:
        """在庫更新"""
        if not self.shop_domain or not self.access_token:
            return {"success": True, "quantity": quantity}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/inventory_levels/set.json",
                    headers={"X-Shopify-Access-Token": self.access_token},
                    json={
                        "location_id": os.getenv("SHOPIFY_LOCATION_ID"),
                        "inventory_item_id": inventory_item_id,
                        "available": quantity
                    }
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise ExternalAPIException(f"Failed to update inventory: {str(e)}")
    
    def _get_mock_products(self) -> List[Dict]:
        """モック商品データ"""
        return [
            {
                "id": 1,
                "title": "サンプル商品1",
                "vendor": "サンプルベンダー",
                "product_type": "アパレル",
                "created_at": datetime.utcnow().isoformat(),
                "variants": [
                    {
                        "id": 1,
                        "title": "S",
                        "price": "2980",
                        "inventory_quantity": 10
                    }
                ]
            },
            {
                "id": 2,
                "title": "サンプル商品2",
                "vendor": "サンプルベンダー",
                "product_type": "アクセサリー",
                "created_at": datetime.utcnow().isoformat(),
                "variants": [
                    {
                        "id": 2,
                        "title": "フリーサイズ",
                        "price": "1980",
                        "inventory_quantity": 20
                    }
                ]
            }
        ]
    
    def _get_mock_orders(self) -> List[Dict]:
        """モック注文データ"""
        return [
            {
                "id": 1,
                "order_number": 1001,
                "email": "customer1@example.com",
                "created_at": datetime.utcnow().isoformat(),
                "total_price": "4960",
                "financial_status": "paid",
                "fulfillment_status": None
            },
            {
                "id": 2,
                "order_number": 1002,
                "email": "customer2@example.com",
                "created_at": datetime.utcnow().isoformat(),
                "total_price": "1980",
                "financial_status": "pending",
                "fulfillment_status": None
            }
        ]
    
    def _get_mock_customers(self) -> List[Dict]:
        """モック顧客データ"""
        return [
            {
                "id": 1,
                "email": "customer1@example.com",
                "first_name": "太郎",
                "last_name": "山田",
                "orders_count": 5,
                "total_spent": "29800",
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": 2,
                "email": "customer2@example.com",
                "first_name": "花子",
                "last_name": "佐藤",
                "orders_count": 3,
                "total_spent": "15900",
                "created_at": datetime.utcnow().isoformat()
            }
        ]