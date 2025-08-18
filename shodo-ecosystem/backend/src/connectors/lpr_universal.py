"""
LPRベースのユニバーサルSaaSコネクタ
どのSaaSでも、ユーザーがログインするだけで完全な操作が可能
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from ..auth.lpr_system import LPRAuthenticator, LPRSession, LPR
from .base import (
    BaseSaaSConnector, ConnectorConfig, ConnectorCredentials,
    ConnectorType, AuthMethod, ResourceSnapshot, ChangeSet
)

class LPRUniversalConnector(BaseSaaSConnector):
    """
    LPRを使用した完全に安全なユニバーサルコネクタ
    
    特徴:
    - APIキー不要
    - ユーザーが手動でログイン
    - ユーザーの全権限で操作可能
    - 2時間で自動失効
    - すべての操作が監査される
    """
    
    def __init__(self, service_url: str, service_name: Optional[str] = None):
        # 基本設定（認証情報は不要）
        config = ConnectorConfig(
            name=service_name or "Unknown",
            type=ConnectorType.CUSTOM,
            auth_method=AuthMethod.CUSTOM,  # LPR認証
            base_url=service_url,
            rate_limit=100,
            timeout=30,
            retry_count=3,
            retry_delay=1
        )
        
        # 空の認証情報（LPRを使うので不要）
        credentials = ConnectorCredentials()
        
        super().__init__(config, credentials)
        
        self.service_url = service_url
        self.service_name = service_name
        self.lpr: Optional[LPR] = None
        self.session: Optional[LPRSession] = None
    
    async def initialize(self) -> bool:
        """
        初期化 - ユーザーにログインしてもらう
        """
        try:
            print("\n" + "="*60)
            print("🔐 LPR Universal Connector Initialization")
            print("="*60)
            
            # LPR認証を実行
            authenticator = LPRAuthenticator()
            self.lpr = await authenticator.authenticate(
                service_url=self.service_url,
                service_name=self.service_name,
                ttl_hours=2  # 2時間有効
            )
            
            # LPRセッションを作成
            self.session = LPRSession(self.lpr)
            
            print(f"\n✅ Successfully initialized with LPR: {self.lpr.lpr_id}")
            print(f"📍 Service: {self.lpr.service_name}")
            print(f"⏰ Valid until: {self.lpr.expires_at}")
            print("="*60 + "\n")
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            return False
    
    async def authenticate(self) -> bool:
        """
        認証 - LPRで既に認証済み
        """
        if self.lpr and self.lpr.is_valid():
            return True
        return False
    
    async def validate_connection(self) -> bool:
        """
        接続検証 - LPRが有効か確認
        """
        if not self.lpr:
            return False
        return self.lpr.is_valid()
    
    async def list_resources(
        self,
        resource_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        リソース一覧取得 - ユーザーの全権限で実行
        """
        if not self.session:
            raise Exception("Not initialized. Please call initialize() first.")
        
        # エンドポイントの推測
        endpoint = self._guess_endpoint(resource_type, 'list')
        url = f"{self.config.base_url}{endpoint}"
        
        # パラメータ設定
        params = {}
        if filters:
            params.update(filters)
        if limit:
            params['limit'] = limit
        if offset:
            params['offset'] = offset
        
        # LPRセッションでリクエスト実行
        response = await self.session.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            return self._extract_list_from_response(data, resource_type)
        else:
            print(f"Failed to list {resource_type}: {response.status_code}")
            return []
    
    async def get_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        単一リソース取得 - ユーザーの全権限で実行
        """
        if not self.session:
            raise Exception("Not initialized. Please call initialize() first.")
        
        endpoint = self._guess_endpoint(resource_type, 'get', resource_id)
        url = f"{self.config.base_url}{endpoint}"
        
        response = await self.session.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return self._extract_resource_from_response(data, resource_type)
        else:
            print(f"Failed to get {resource_type}/{resource_id}: {response.status_code}")
            return None
    
    async def create_resource(
        self,
        resource_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        リソース作成 - ユーザーの全権限で実行
        """
        if not self.session:
            raise Exception("Not initialized. Please call initialize() first.")
        
        endpoint = self._guess_endpoint(resource_type, 'create')
        url = f"{self.config.base_url}{endpoint}"
        
        response = await self.session.post(url, json=data)
        
        if response.status_code in [200, 201]:
            result = response.json()
            return self._extract_resource_from_response(result, resource_type)
        else:
            raise Exception(f"Failed to create {resource_type}: {response.status_code}")
    
    async def update_resource(
        self,
        resource_type: str,
        resource_id: str,
        data: Dict[str, Any],
        partial: bool = True
    ) -> Dict[str, Any]:
        """
        リソース更新 - ユーザーの全権限で実行
        """
        if not self.session:
            raise Exception("Not initialized. Please call initialize() first.")
        
        endpoint = self._guess_endpoint(resource_type, 'update', resource_id)
        url = f"{self.config.base_url}{endpoint}"
        
        if partial:
            response = await self.session.request('PATCH', url, json=data)
            if response.status_code == 405:  # Method not allowed
                response = await self.session.put(url, json=data)
        else:
            response = await self.session.put(url, json=data)
        
        if response.status_code in [200, 201]:
            result = response.json()
            return self._extract_resource_from_response(result, resource_type)
        else:
            raise Exception(f"Failed to update {resource_type}/{resource_id}: {response.status_code}")
    
    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
        soft_delete: bool = True
    ) -> bool:
        """
        リソース削除 - ユーザーの全権限で実行
        """
        if not self.session:
            raise Exception("Not initialized. Please call initialize() first.")
        
        if soft_delete:
            # ソフトデリート試行
            try:
                await self.update_resource(
                    resource_type,
                    resource_id,
                    {"deleted": True, "status": "deleted"}
                )
                return True
            except:
                pass
        
        # ハードデリート
        endpoint = self._guess_endpoint(resource_type, 'delete', resource_id)
        url = f"{self.config.base_url}{endpoint}"
        
        response = await self.session.delete(url)
        return response.status_code in [200, 204, 202]
    
    async def search_resources(
        self,
        resource_type: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        リソース検索 - ユーザーの全権限で実行
        """
        if not self.session:
            raise Exception("Not initialized. Please call initialize() first.")
        
        # 検索エンドポイントを試す
        search_endpoints = [
            f"/{resource_type}/search?q={query}",
            f"/search/{resource_type}?q={query}",
            f"/{resource_type}?search={query}",
            f"/{resource_type}?q={query}"
        ]
        
        for endpoint in search_endpoints:
            url = f"{self.config.base_url}{endpoint}"
            try:
                response = await self.session.get(url, params=filters)
                if response.status_code == 200:
                    data = response.json()
                    return self._extract_list_from_response(data, resource_type)
            except:
                continue
        
        # フォールバック: 全件取得してフィルタ
        all_items = await self.list_resources(resource_type)
        return [
            item for item in all_items
            if query.lower() in json.dumps(item).lower()
        ]
    
    async def create_snapshot(
        self,
        resource_type: str,
        resource_id: str
    ) -> ResourceSnapshot:
        """
        スナップショット作成
        """
        resource = await self.get_resource(resource_type, resource_id)
        if not resource:
            raise ValueError(f"Resource {resource_type}/{resource_id} not found")
        
        import hashlib
        data_str = json.dumps(resource, sort_keys=True)
        checksum = hashlib.sha256(data_str.encode()).hexdigest()
        
        return ResourceSnapshot(
            resource_id=resource_id,
            resource_type=resource_type,
            data=resource,
            metadata={
                'service': self.lpr.service_name if self.lpr else 'Unknown',
                'lpr_id': self.lpr.lpr_id if self.lpr else None,
                'captured_with_lpr': True
            },
            captured_at=datetime.utcnow(),
            checksum=checksum
        )
    
    async def generate_preview(
        self,
        snapshot: ResourceSnapshot,
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        プレビュー生成
        """
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
        
        return {
            "html": self._generate_preview_html(snapshot.resource_type, preview_data),
            "css": self._generate_preview_css(),
            "data": preview_data,
            "changes": self._calculate_changes(snapshot.data, preview_data),
            "confidence": 1.0,  # LPRは完全な権限なので確信度100%
            "lpr_id": self.lpr.lpr_id if self.lpr else None
        }
    
    async def validate_changes(
        self,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        変更の検証 - LPRではユーザーの権限内なら全て有効
        """
        errors = []
        
        # 基本的な検証のみ
        for key, value in changes.items():
            if value is None and key in ['id', 'name', 'title']:
                errors.append(f"Required field '{key}' cannot be null")
        
        return len(errors) == 0, errors
    
    async def apply_changes(
        self,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any],
        dry_run: bool = False
    ) -> ChangeSet:
        """
        変更の適用 - ユーザーの全権限で実行
        """
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
    
    async def rollback(self, change_set: ChangeSet) -> bool:
        """
        ロールバック - ユーザーの全権限で実行
        """
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
            print(f"Rollback failed: {e}")
            return False
    
    async def can_rollback(self, change_set: ChangeSet) -> bool:
        """
        ロールバック可能性チェック
        LPRが有効な間はロールバック可能
        """
        if not self.lpr or not self.lpr.is_valid():
            return False
        
        if change_set.applied_at:
            # LPRの有効期限内ならロールバック可能
            return datetime.utcnow() < self.lpr.expires_at
        
        return False
    
    def _guess_endpoint(
        self,
        resource_type: str,
        operation: str,
        resource_id: Optional[str] = None
    ) -> str:
        """
        エンドポイントを推測
        """
        # 複数形に変換（簡易版）
        if not resource_type.endswith('s'):
            resource_type_plural = resource_type + 's'
        else:
            resource_type_plural = resource_type
        
        # 一般的なRESTパターン
        patterns = {
            'list': [
                f"/{resource_type_plural}",
                f"/api/{resource_type_plural}",
                f"/api/v1/{resource_type_plural}",
                f"/v1/{resource_type_plural}"
            ],
            'get': [
                f"/{resource_type_plural}/{resource_id}",
                f"/api/{resource_type_plural}/{resource_id}",
                f"/api/v1/{resource_type_plural}/{resource_id}",
                f"/v1/{resource_type_plural}/{resource_id}"
            ],
            'create': [
                f"/{resource_type_plural}",
                f"/api/{resource_type_plural}",
                f"/api/v1/{resource_type_plural}",
                f"/v1/{resource_type_plural}"
            ],
            'update': [
                f"/{resource_type_plural}/{resource_id}",
                f"/api/{resource_type_plural}/{resource_id}",
                f"/api/v1/{resource_type_plural}/{resource_id}",
                f"/v1/{resource_type_plural}/{resource_id}"
            ],
            'delete': [
                f"/{resource_type_plural}/{resource_id}",
                f"/api/{resource_type_plural}/{resource_id}",
                f"/api/v1/{resource_type_plural}/{resource_id}",
                f"/v1/{resource_type_plural}/{resource_id}"
            ]
        }
        
        # 最初のパターンを返す（実際はエラーハンドリングで複数試行）
        return patterns.get(operation, [f"/{resource_type_plural}"])[0]
    
    def _extract_list_from_response(
        self,
        data: Any,
        resource_type: str
    ) -> List[Dict[str, Any]]:
        """
        レスポンスからリストを抽出
        """
        if isinstance(data, list):
            return data
        
        if isinstance(data, dict):
            # 一般的なパターンを試す
            for key in ['data', 'items', 'results', resource_type, f"{resource_type}s"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
        
        return []
    
    def _extract_resource_from_response(
        self,
        data: Any,
        resource_type: str
    ) -> Dict[str, Any]:
        """
        レスポンスからリソースを抽出
        """
        if isinstance(data, dict):
            # ネストされている場合
            for key in ['data', resource_type]:
                if key in data:
                    return data[key]
            # そのまま返す
            return data
        
        return {}
    
    def _generate_preview_html(
        self,
        resource_type: str,
        data: Dict[str, Any]
    ) -> str:
        """
        プレビューHTML生成
        """
        html = f"""
        <div class="lpr-preview">
            <div class="lpr-header">
                <span class="lpr-badge">🔐 LPR</span>
                <span class="service-name">{self.lpr.service_name if self.lpr else 'Unknown'}</span>
            </div>
            <h2>{resource_type.upper()}</h2>
            <div class="resource-data">
        """
        
        for key, value in data.items():
            html += f"""
                <div class="field">
                    <span class="key">{key}:</span>
                    <span class="value">{value}</span>
                </div>
            """
        
        html += """
            </div>
            <div class="lpr-footer">
                <span class="lpr-id">LPR ID: {}</span>
                <span class="expires">Expires: {}</span>
            </div>
        </div>
        """.format(
            self.lpr.lpr_id if self.lpr else 'N/A',
            self.lpr.expires_at if self.lpr else 'N/A'
        )
        
        return html
    
    def _generate_preview_css(self) -> str:
        """
        プレビューCSS生成
        """
        return """
        .lpr-preview {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .lpr-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #4caf50;
        }
        .lpr-badge {
            background: #4caf50;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }
        .service-name {
            font-size: 14px;
            color: #666;
        }
        .resource-data {
            margin: 20px 0;
        }
        .field {
            display: flex;
            padding: 10px;
            border-bottom: 1px solid #f0f0f0;
        }
        .field:hover {
            background: #f9f9f9;
        }
        .key {
            flex: 0 0 200px;
            font-weight: 500;
            color: #666;
        }
        .value {
            flex: 1;
            color: #333;
        }
        .lpr-footer {
            margin-top: 20px;
            padding-top: 10px;
            border-top: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #999;
        }
        """
    
    def _calculate_changes(self, original: Dict, modified: Dict) -> List[Dict[str, Any]]:
        """
        変更点の計算
        """
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
                    changes.append({
                        "type": "modify",
                        "path": current_path,
                        "old_value": orig[key],
                        "new_value": mod[key]
                    })
        
        compare_dicts(original, modified)
        return changes
    
    async def get_audit_log(self) -> List[Dict[str, Any]]:
        """
        監査ログを取得
        LPRのすべての操作履歴
        """
        if self.lpr:
            return self.lpr.operations_log
        return []
    
    async def close(self):
        """
        コネクタをクローズ
        """
        if self.session:
            await self.session.close()
        self._initialized = False

# 使用例
async def connect_with_lpr(service_url: str) -> LPRUniversalConnector:
    """
    LPRを使って任意のSaaSに接続
    
    Example:
        # Shopifyに接続
        connector = await connect_with_lpr("https://mystore.myshopify.com")
        
        # ユーザーの全権限で操作
        orders = await connector.list_resources("orders")
        
        # 監査ログ確認
        audit_log = await connector.get_audit_log()
        print(f"Operations performed: {len(audit_log)}")
    """
    connector = LPRUniversalConnector(service_url)
    await connector.initialize()  # ユーザーが手動でログイン
    return connector