"""
Stripeコネクタ実装
決済プラットフォーム連携
"""

import httpx
import hashlib
import hmac
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
from decimal import Decimal

from .base import (
    BaseSaaSConnector, ConnectorConfig, ConnectorCredentials,
    ConnectorType, AuthMethod, ResourceSnapshot, ChangeSet
)

class StripeConnector(BaseSaaSConnector):
    """Stripe API連携コネクタ"""
    
    RESOURCE_TYPES = {
        "customer": "customers",
        "payment_intent": "payment_intents",
        "payment_method": "payment_methods",
        "subscription": "subscriptions",
        "invoice": "invoices",
        "product": "products",
        "price": "prices",
        "charge": "charges",
        "refund": "refunds",
        "payout": "payouts",
        "balance": "balance",
        "dispute": "disputes"
    }
    
    def __init__(self, credentials: ConnectorCredentials, test_mode: bool = False):
        config = ConnectorConfig(
            name="Stripe",
            type=ConnectorType.PAYMENT,
            auth_method=AuthMethod.BEARER,
            base_url="https://api.stripe.com/v1",
            api_version="2023-10-16",
            rate_limit=100,  # Stripe default rate limit
            timeout=30,
            retry_count=3,
            retry_delay=1
        )
        super().__init__(config, credentials)
        self.test_mode = test_mode
        
    async def initialize(self) -> bool:
        """初期化"""
        self._session = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=self._get_headers(),
            timeout=self.config.timeout,
            auth=(self.credentials.api_key, "")  # Stripe uses basic auth with API key
        )
        self._initialized = await self.validate_connection()
        return self._initialized
    
    async def authenticate(self) -> bool:
        """認証"""
        try:
            response = await self._session.get("/balance")
            return response.status_code == 200
        except Exception:
            return False
    
    async def validate_connection(self) -> bool:
        """接続検証"""
        try:
            response = await self._session.get("/balance")
            return response.status_code == 200
        except Exception:
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """ヘッダー生成"""
        headers = {
            "Stripe-Version": self.config.api_version,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        if self.credentials.custom_headers:
            headers.update(self.credentials.custom_headers)
        return headers
    
    def _format_params(self, params: Dict[str, Any]) -> str:
        """Stripe形式のパラメータフォーマット"""
        def flatten(obj, parent_key=''):
            items = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{parent_key}[{k}]" if parent_key else k
                    items.extend(flatten(v, new_key))
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    new_key = f"{parent_key}[{i}]"
                    items.extend(flatten(v, new_key))
            else:
                items.append((parent_key, str(obj)))
            return items
        
        return "&".join([f"{k}={v}" for k, v in flatten(params)])
    
    # === 読み取り操作 ===
    
    async def list_resources(
        self,
        resource_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = 10,
        offset: Optional[int] = 0
    ) -> List[Dict[str, Any]]:
        """リソース一覧取得"""
        endpoint = self.RESOURCE_TYPES.get(resource_type, resource_type)
        params = {
            "limit": min(limit or 10, 100),  # Stripe max is 100
        }
        
        if offset:
            # Stripeはcursor-based pagination
            params["starting_after"] = offset
        
        if filters:
            params.update(filters)
        
        try:
            response = await self._session.get(f"/{endpoint}", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
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
        
        try:
            response = await self._session.get(f"/{endpoint}/{resource_id}")
            response.raise_for_status()
            return response.json()
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
        # Stripeは一部のリソースでのみ検索をサポート
        search_endpoints = {
            "customer": "/customers/search",
            "charge": "/charges/search",
            "payment_intent": "/payment_intents/search",
            "subscription": "/subscriptions/search",
            "invoice": "/invoices/search"
        }
        
        if resource_type not in search_endpoints:
            # 検索非対応の場合はリスト取得で代替
            return await self.list_resources(resource_type, {"email": query})
        
        try:
            response = await self._session.get(
                search_endpoints[resource_type],
                params={"query": query, "limit": 100}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
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
                "test_mode": self.test_mode,
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
        preview_data = snapshot.data.copy()
        
        # 変更を適用
        for key, value in changes.items():
            if "." in key:
                keys = key.split(".")
                target = preview_data
                for k in keys[:-1]:
                    target = target.setdefault(k, {})
                target[keys[-1]] = value
            else:
                preview_data[key] = value
        
        # プレビューHTML生成
        if snapshot.resource_type == "customer":
            html = self._generate_customer_preview_html(preview_data)
            css = self._generate_customer_preview_css()
        elif snapshot.resource_type == "subscription":
            html = self._generate_subscription_preview_html(preview_data)
            css = self._generate_subscription_preview_css()
        elif snapshot.resource_type == "invoice":
            html = self._generate_invoice_preview_html(preview_data)
            css = self._generate_invoice_preview_css()
        else:
            html = f"<pre>{json.dumps(preview_data, indent=2)}</pre>"
            css = "pre { font-family: monospace; background: #f5f5f5; padding: 10px; }"
        
        return {
            "html": html,
            "css": css,
            "data": preview_data,
            "changes": self._calculate_changes(snapshot.data, preview_data),
            "confidence": 0.98
        }
    
    def _generate_customer_preview_html(self, customer: Dict[str, Any]) -> str:
        """顧客プレビューHTML生成"""
        return f"""
        <div class="stripe-customer-preview">
            <div class="customer-header">
                <h2>顧客情報</h2>
                <span class="customer-id">{customer.get('id', '')}</span>
            </div>
            <div class="customer-details">
                <div class="detail-row">
                    <span class="label">名前:</span>
                    <span class="value">{customer.get('name', 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="label">メール:</span>
                    <span class="value">{customer.get('email', 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="label">電話:</span>
                    <span class="value">{customer.get('phone', 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="label">残高:</span>
                    <span class="value">{customer.get('balance', 0) / 100:.2f} {customer.get('currency', 'JPY').upper()}</span>
                </div>
                <div class="detail-row">
                    <span class="label">作成日:</span>
                    <span class="value">{datetime.fromtimestamp(customer.get('created', 0)).strftime('%Y-%m-%d %H:%M')}</span>
                </div>
            </div>
        </div>
        """
    
    def _generate_customer_preview_css(self) -> str:
        """顧客プレビューCSS生成"""
        return """
        .stripe-customer-preview {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .customer-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #6772e5;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .customer-header h2 {
            margin: 0;
            color: #32325d;
        }
        .customer-id {
            font-family: monospace;
            font-size: 12px;
            color: #8898aa;
        }
        .detail-row {
            display: flex;
            padding: 10px 0;
            border-bottom: 1px solid #e6ebf1;
        }
        .detail-row .label {
            flex: 0 0 120px;
            color: #8898aa;
            font-weight: 500;
        }
        .detail-row .value {
            flex: 1;
            color: #32325d;
        }
        """
    
    def _generate_subscription_preview_html(self, subscription: Dict[str, Any]) -> str:
        """サブスクリプションプレビューHTML生成"""
        items = subscription.get('items', {}).get('data', [])
        return f"""
        <div class="stripe-subscription-preview">
            <div class="subscription-header">
                <h2>サブスクリプション</h2>
                <span class="status status-{subscription.get('status', 'unknown')}">{subscription.get('status', 'unknown').upper()}</span>
            </div>
            <div class="subscription-items">
                {"".join([self._generate_subscription_item_html(item) for item in items])}
            </div>
            <div class="subscription-summary">
                <div class="summary-row">
                    <span>現在の期間:</span>
                    <span>{datetime.fromtimestamp(subscription.get('current_period_start', 0)).strftime('%Y-%m-%d')} - 
                          {datetime.fromtimestamp(subscription.get('current_period_end', 0)).strftime('%Y-%m-%d')}</span>
                </div>
                <div class="summary-row total">
                    <span>合計:</span>
                    <span>{self._format_amount(subscription)}</span>
                </div>
            </div>
        </div>
        """
    
    def _generate_subscription_item_html(self, item: Dict[str, Any]) -> str:
        """サブスクリプションアイテムHTML生成"""
        price = item.get('price', {})
        return f"""
        <div class="subscription-item">
            <div class="item-name">{price.get('nickname', price.get('id', ''))}</div>
            <div class="item-price">{price.get('unit_amount', 0) / 100:.2f} {price.get('currency', 'JPY').upper()}</div>
        </div>
        """
    
    def _generate_subscription_preview_css(self) -> str:
        """サブスクリプションプレビューCSS生成"""
        return """
        .stripe-subscription-preview {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .subscription-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .status {
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-active { background: #d4f4dd; color: #1a7f37; }
        .status-trialing { background: #fef3c7; color: #92400e; }
        .status-canceled { background: #fee; color: #c00; }
        .subscription-item {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #e6ebf1;
        }
        .subscription-summary {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 2px solid #e6ebf1;
        }
        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
        }
        .summary-row.total {
            font-weight: 600;
            font-size: 18px;
            color: #32325d;
        }
        """
    
    def _generate_invoice_preview_html(self, invoice: Dict[str, Any]) -> str:
        """請求書プレビューHTML生成"""
        lines = invoice.get('lines', {}).get('data', [])
        return f"""
        <div class="stripe-invoice-preview">
            <div class="invoice-header">
                <h2>請求書 #{invoice.get('number', 'DRAFT')}</h2>
                <div class="invoice-status status-{invoice.get('status', 'draft')}">{invoice.get('status', 'draft').upper()}</div>
            </div>
            <div class="invoice-meta">
                <div>請求日: {datetime.fromtimestamp(invoice.get('created', 0)).strftime('%Y-%m-%d')}</div>
                <div>支払期限: {datetime.fromtimestamp(invoice.get('due_date', 0)).strftime('%Y-%m-%d') if invoice.get('due_date') else 'N/A'}</div>
            </div>
            <table class="invoice-lines">
                <thead>
                    <tr>
                        <th>項目</th>
                        <th>数量</th>
                        <th>単価</th>
                        <th>金額</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join([self._generate_invoice_line_html(line) for line in lines])}
                </tbody>
                <tfoot>
                    <tr class="total">
                        <td colspan="3">合計</td>
                        <td>{invoice.get('total', 0) / 100:.2f} {invoice.get('currency', 'JPY').upper()}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        """
    
    def _generate_invoice_line_html(self, line: Dict[str, Any]) -> str:
        """請求書明細HTML生成"""
        return f"""
        <tr>
            <td>{line.get('description', 'N/A')}</td>
            <td>{line.get('quantity', 1)}</td>
            <td>{line.get('unit_amount', 0) / 100:.2f}</td>
            <td>{line.get('amount', 0) / 100:.2f}</td>
        </tr>
        """
    
    def _generate_invoice_preview_css(self) -> str:
        """請求書プレビューCSS生成"""
        return """
        .stripe-invoice-preview {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .invoice-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #6772e5;
        }
        .invoice-status {
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-draft { background: #f0f0f0; color: #666; }
        .status-open { background: #d4f4dd; color: #1a7f37; }
        .status-paid { background: #d4f4dd; color: #1a7f37; }
        .status-void { background: #fee; color: #c00; }
        .invoice-meta {
            display: flex;
            gap: 30px;
            margin-bottom: 30px;
            color: #8898aa;
        }
        .invoice-lines {
            width: 100%;
            border-collapse: collapse;
        }
        .invoice-lines th {
            text-align: left;
            padding: 10px;
            border-bottom: 2px solid #e6ebf1;
            color: #8898aa;
            font-weight: 500;
        }
        .invoice-lines td {
            padding: 10px;
            border-bottom: 1px solid #e6ebf1;
            color: #32325d;
        }
        .invoice-lines tfoot tr.total td {
            font-weight: 600;
            font-size: 16px;
            border-top: 2px solid #e6ebf1;
            border-bottom: none;
            padding-top: 15px;
        }
        """
    
    def _format_amount(self, obj: Dict[str, Any]) -> str:
        """金額フォーマット"""
        amount = obj.get('amount', 0) or obj.get('amount_total', 0) or 0
        currency = obj.get('currency', 'jpy')
        return f"{amount / 100:.2f} {currency.upper()}"
    
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
        
        # 顧客の検証
        if resource_type == "customer":
            if "email" in changes:
                # メールフォーマットの簡易チェック
                if "@" not in changes["email"]:
                    errors.append("Invalid email format")
        
        # サブスクリプションの検証
        elif resource_type == "subscription":
            if "cancel_at_period_end" in changes:
                if not isinstance(changes["cancel_at_period_end"], bool):
                    errors.append("cancel_at_period_end must be boolean")
        
        # 請求書の検証
        elif resource_type == "invoice":
            if "status" in changes:
                valid_statuses = ["draft", "open", "paid", "uncollectible", "void"]
                if changes["status"] not in valid_statuses:
                    errors.append(f"Invalid status: {changes['status']}")
        
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
        snapshot = await self.create_snapshot(resource_type, resource_id)
        
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
        
        try:
            response = await self._session.post(
                f"/{endpoint}",
                content=self._format_params(data),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()
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
        
        try:
            response = await self._session.post(
                f"/{endpoint}/{resource_id}",
                content=self._format_params(data),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()
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
            # Stripeでは多くのリソースが削除不可、代わりにキャンセルや無効化
            if resource_type == "subscription" and soft_delete:
                result = await self.update_resource(
                    resource_type,
                    resource_id,
                    {"cancel_at_period_end": True}
                )
                return result is not None
            elif resource_type in ["customer", "product"]:
                response = await self._session.delete(f"/{endpoint}/{resource_id}")
                return response.status_code in [200, 204]
            else:
                # 削除非対応
                return False
        except Exception as e:
            print(f"Error deleting {resource_type} {resource_id}: {e}")
            return False
    
    # === ロールバック ===
    
    async def rollback(self, change_set: ChangeSet) -> bool:
        """ロールバック"""
        if change_set.rolled_back_at:
            return False
        
        try:
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
        # 決済関連は慎重に（24時間以内かつ特定のリソースタイプのみ）
        if change_set.resource_type in ["charge", "payment_intent", "invoice"]:
            return False  # 決済関連はロールバック不可
        
        if change_set.applied_at:
            elapsed = datetime.utcnow() - change_set.applied_at
            return elapsed.total_seconds() < 86400
        return False
    
    # === Webhook ===
    
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Webhook署名検証"""
        if not self.credentials.api_secret:
            return False
        
        # Stripe署名検証ロジック
        elements = signature.split(',')
        timestamp = None
        signatures = []
        
        for element in elements:
            key, value = element.split('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signatures.append(value)
        
        if not timestamp or not signatures:
            return False
        
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_signature = hmac.new(
            self.credentials.api_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return any(hmac.compare_digest(expected_signature, sig) for sig in signatures)