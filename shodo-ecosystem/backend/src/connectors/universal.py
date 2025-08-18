"""
ユニバーサルSaaSコネクタ
任意のSaaSに動的に接続可能な汎用コネクタ
"""

import httpx
import json
import yaml
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import asyncio
from urllib.parse import urlparse
import re

from .base import (
    BaseSaaSConnector, ConnectorConfig, ConnectorCredentials,
    ConnectorType, AuthMethod, ResourceSnapshot, ChangeSet
)

class APISpecification:
    """API仕様の自動解析"""
    
    @staticmethod
    async def discover_from_url(base_url: str) -> Dict[str, Any]:
        """URLからAPI仕様を自動検出"""
        spec = {}
        
        # OpenAPI/Swagger仕様の検出
        openapi_paths = [
            '/openapi.json',
            '/swagger.json',
            '/api-docs',
            '/v1/openapi.json',
            '/api/v1/openapi.json',
            '/.well-known/openapi.json'
        ]
        
        async with httpx.AsyncClient() as client:
            for path in openapi_paths:
                try:
                    response = await client.get(f"{base_url}{path}")
                    if response.status_code == 200:
                        spec['openapi'] = response.json()
                        spec['type'] = 'openapi'
                        return spec
                except:
                    continue
            
            # GraphQL仕様の検出
            try:
                response = await client.post(
                    f"{base_url}/graphql",
                    json={"query": "{__schema{types{name}}}"}
                )
                if response.status_code == 200:
                    spec['graphql'] = response.json()
                    spec['type'] = 'graphql'
                    return spec
            except:
                pass
            
            # REST APIの推測
            spec['type'] = 'rest'
            spec['discovered_endpoints'] = await APISpecification._probe_endpoints(base_url)
            
        return spec
    
    @staticmethod
    async def _probe_endpoints(base_url: str) -> List[str]:
        """一般的なエンドポイントを探索"""
        common_endpoints = [
            '/api', '/v1', '/v2', '/api/v1', '/api/v2',
            '/users', '/products', '/orders', '/customers',
            '/items', '/accounts', '/projects', '/tasks',
            '/invoices', '/payments', '/subscriptions'
        ]
        
        discovered = []
        async with httpx.AsyncClient() as client:
            for endpoint in common_endpoints:
                try:
                    response = await client.head(f"{base_url}{endpoint}")
                    if response.status_code < 400:
                        discovered.append(endpoint)
                except:
                    continue
        
        return discovered

class AuthenticationDetector:
    """認証方式の自動検出"""
    
    @staticmethod
    async def detect_auth_method(base_url: str) -> Dict[str, Any]:
        """認証方式を自動検出"""
        auth_info = {
            'method': None,
            'details': {}
        }
        
        async with httpx.AsyncClient() as client:
            # OAuth2の検出
            oauth_endpoints = [
                '/.well-known/oauth-authorization-server',
                '/.well-known/openid-configuration',
                '/oauth/authorize',
                '/auth/authorize'
            ]
            
            for endpoint in oauth_endpoints:
                try:
                    response = await client.get(f"{base_url}{endpoint}")
                    if response.status_code == 200:
                        auth_info['method'] = 'oauth2'
                        auth_info['details'] = response.json()
                        return auth_info
                except:
                    continue
            
            # APIキー認証の検出（ヘッダーを確認）
            try:
                response = await client.get(base_url)
                headers = response.headers
                
                if 'x-api-key' in headers or 'api-key' in headers:
                    auth_info['method'] = 'api_key'
                    auth_info['details']['header_name'] = 'x-api-key' if 'x-api-key' in headers else 'api-key'
                elif 'authorization' in headers:
                    auth_value = headers['authorization'].lower()
                    if auth_value.startswith('bearer'):
                        auth_info['method'] = 'bearer'
                    elif auth_value.startswith('basic'):
                        auth_info['method'] = 'basic'
            except:
                pass
        
        # デフォルトはAPIキー
        if not auth_info['method']:
            auth_info['method'] = 'api_key'
            auth_info['details']['header_name'] = 'x-api-key'
        
        return auth_info

class UniversalSaaSConnector(BaseSaaSConnector):
    """
    任意のSaaSに接続可能なユニバーサルコネクタ
    """
    
    def __init__(
        self,
        service_name: str,
        base_url: str,
        credentials: ConnectorCredentials,
        api_spec: Optional[Dict[str, Any]] = None
    ):
        # 基本設定
        config = ConnectorConfig(
            name=service_name,
            type=ConnectorType.CUSTOM,
            auth_method=AuthMethod.CUSTOM,
            base_url=base_url,
            rate_limit=100,
            timeout=30,
            retry_count=3,
            retry_delay=1
        )
        super().__init__(config, credentials)
        
        self.service_name = service_name
        self.api_spec = api_spec or {}
        self.discovered_resources = {}
        self.auth_info = {}
        
    async def initialize(self) -> bool:
        """初期化と自動検出"""
        try:
            # API仕様の自動検出
            if not self.api_spec:
                self.api_spec = await APISpecification.discover_from_url(self.config.base_url)
            
            # 認証方式の自動検出
            self.auth_info = await AuthenticationDetector.detect_auth_method(self.config.base_url)
            
            # HTTPクライアントの初期化
            self._session = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=self._build_headers(),
                timeout=self.config.timeout
            )
            
            # リソースの自動検出
            await self._discover_resources()
            
            self._initialized = await self.validate_connection()
            return self._initialized
            
        except Exception as e:
            print(f"Failed to initialize connector: {e}")
            return False
    
    def _build_headers(self) -> Dict[str, str]:
        """認証ヘッダーの自動構築"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.auth_info.get('method') == 'api_key':
            header_name = self.auth_info.get('details', {}).get('header_name', 'x-api-key')
            if self.credentials.api_key:
                headers[header_name] = self.credentials.api_key
        
        elif self.auth_info.get('method') == 'bearer':
            if self.credentials.access_token:
                headers['Authorization'] = f"Bearer {self.credentials.access_token}"
        
        elif self.auth_info.get('method') == 'basic':
            if self.credentials.username and self.credentials.password:
                import base64
                auth_str = f"{self.credentials.username}:{self.credentials.password}"
                encoded = base64.b64encode(auth_str.encode()).decode()
                headers['Authorization'] = f"Basic {encoded}"
        
        if self.credentials.custom_headers:
            headers.update(self.credentials.custom_headers)
        
        return headers
    
    async def _discover_resources(self):
        """リソースタイプの自動検出"""
        if self.api_spec.get('type') == 'openapi':
            # OpenAPI仕様からリソースを抽出
            paths = self.api_spec.get('openapi', {}).get('paths', {})
            for path, methods in paths.items():
                # パスからリソース名を推測
                parts = path.strip('/').split('/')
                if parts and parts[0] not in ['api', 'v1', 'v2']:
                    resource_name = parts[0]
                    if resource_name not in self.discovered_resources:
                        self.discovered_resources[resource_name] = {
                            'path': path,
                            'methods': list(methods.keys())
                        }
        
        elif self.api_spec.get('type') == 'graphql':
            # GraphQLスキーマからタイプを抽出
            schema = self.api_spec.get('graphql', {}).get('data', {}).get('__schema', {})
            types = schema.get('types', [])
            for type_def in types:
                if not type_def['name'].startswith('__'):
                    self.discovered_resources[type_def['name'].lower()] = {
                        'type': 'graphql',
                        'name': type_def['name']
                    }
        
        else:
            # REST APIの場合、エンドポイントから推測
            for endpoint in self.api_spec.get('discovered_endpoints', []):
                resource_name = endpoint.strip('/').split('/')[-1]
                if resource_name:
                    self.discovered_resources[resource_name] = {
                        'path': endpoint,
                        'methods': ['GET', 'POST', 'PUT', 'DELETE']  # 推測
                    }
    
    async def authenticate(self) -> bool:
        """認証処理"""
        if self.auth_info.get('method') == 'oauth2':
            # OAuth2フローの実行
            return await self._oauth2_authenticate()
        else:
            # その他の認証はヘッダーで処理済み
            return True
    
    async def _oauth2_authenticate(self) -> bool:
        """OAuth2認証フロー"""
        details = self.auth_info.get('details', {})
        
        if 'token_endpoint' in details:
            # Client Credentials Grant
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    details['token_endpoint'],
                    data={
                        'grant_type': 'client_credentials',
                        'client_id': self.credentials.client_id,
                        'client_secret': self.credentials.client_secret
                    }
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.credentials.access_token = token_data.get('access_token')
                    return True
        
        return False
    
    async def validate_connection(self) -> bool:
        """接続検証"""
        try:
            # 最も基本的なエンドポイントでテスト
            test_endpoints = ['/', '/api', '/health', '/status', '/ping']
            
            for endpoint in test_endpoints:
                response = await self._session.get(endpoint)
                if response.status_code < 400:
                    return True
            
            # リソースエンドポイントでテスト
            for resource_name, resource_info in self.discovered_resources.items():
                if 'path' in resource_info:
                    response = await self._session.get(resource_info['path'])
                    if response.status_code < 400:
                        return True
            
            return False
            
        except Exception:
            return False
    
    async def list_resources(
        self,
        resource_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """リソース一覧の取得"""
        # リソースタイプから適切なエンドポイントを決定
        resource_info = self.discovered_resources.get(resource_type)
        
        if not resource_info:
            # 推測でエンドポイントを構築
            endpoint = f"/{resource_type}"
        else:
            endpoint = resource_info.get('path', f"/{resource_type}")
        
        params = {}
        if filters:
            params.update(filters)
        if limit:
            # 一般的なパラメータ名を試す
            params['limit'] = limit
            params['per_page'] = limit  # 別名
            params['page_size'] = limit  # 別名
        if offset:
            params['offset'] = offset
            params['skip'] = offset  # 別名
        
        try:
            response = await self._session.get(endpoint, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # レスポンス形式の自動判定
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 一般的なレスポンス構造を試す
                for key in ['data', 'items', 'results', resource_type, f"{resource_type}s"]:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                
                # 単一オブジェクトの場合
                return [data]
            
            return []
            
        except Exception as e:
            print(f"Error listing resources: {e}")
            return []
    
    async def get_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """単一リソースの取得"""
        resource_info = self.discovered_resources.get(resource_type)
        
        if resource_info and resource_info.get('type') == 'graphql':
            # GraphQLクエリ
            return await self._graphql_get_resource(resource_type, resource_id)
        
        # RESTエンドポイント
        endpoint = f"/{resource_type}/{resource_id}"
        
        try:
            response = await self._session.get(endpoint)
            response.raise_for_status()
            
            data = response.json()
            
            # レスポンス形式の自動判定
            if isinstance(data, dict):
                # ネストされたデータの場合
                for key in ['data', resource_type]:
                    if key in data:
                        return data[key]
                return data
            
            return None
            
        except Exception as e:
            print(f"Error getting resource: {e}")
            return None
    
    async def _graphql_get_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """GraphQLでリソース取得"""
        query = f"""
        query Get{resource_type.capitalize()} {{
            {resource_type}(id: "{resource_id}") {{
                id
                __typename
            }}
        }}
        """
        
        try:
            response = await self._session.post(
                "/graphql",
                json={"query": query}
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get('data', {}).get(resource_type)
            
        except Exception as e:
            print(f"GraphQL error: {e}")
            return None
    
    async def search_resources(
        self,
        resource_type: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """リソースの検索"""
        # 検索エンドポイントのパターンを試す
        search_patterns = [
            f"/{resource_type}/search",
            f"/{resource_type}?q={query}",
            f"/search/{resource_type}",
            f"/api/search?type={resource_type}&q={query}"
        ]
        
        for pattern in search_patterns:
            try:
                response = await self._session.get(pattern, params=filters)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        for key in ['data', 'items', 'results']:
                            if key in data and isinstance(data[key], list):
                                return data[key]
            except:
                continue
        
        # フォールバック：全件取得してフィルタリング
        all_resources = await self.list_resources(resource_type)
        return [
            r for r in all_resources
            if query.lower() in str(r).lower()
        ]
    
    async def create_snapshot(
        self,
        resource_type: str,
        resource_id: str
    ) -> ResourceSnapshot:
        """スナップショット作成"""
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
                'service': self.service_name,
                'api_type': self.api_spec.get('type', 'unknown')
            },
            captured_at=datetime.utcnow(),
            checksum=checksum
        )
    
    async def generate_preview(
        self,
        snapshot: ResourceSnapshot,
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """汎用プレビュー生成"""
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
        
        # 汎用的なHTMLプレビュー生成
        html = self._generate_generic_preview_html(
            snapshot.resource_type,
            preview_data,
            changes
        )
        
        css = self._generate_generic_preview_css()
        
        return {
            "html": html,
            "css": css,
            "data": preview_data,
            "changes": self._calculate_changes(snapshot.data, preview_data),
            "confidence": 0.75  # 汎用的なので確信度は低め
        }
    
    def _generate_generic_preview_html(
        self,
        resource_type: str,
        data: Dict[str, Any],
        changes: Dict[str, Any]
    ) -> str:
        """汎用的なプレビューHTML生成"""
        html_parts = [
            f'<div class="universal-preview">',
            f'<h2 class="resource-type">{resource_type.upper()}</h2>',
            f'<div class="resource-id">ID: {data.get("id", "N/A")}</div>',
            '<div class="resource-details">'
        ]
        
        # 変更されたフィールドをハイライト
        for key, value in data.items():
            is_changed = key in changes
            css_class = "field changed" if is_changed else "field"
            
            if isinstance(value, dict):
                html_parts.append(f'<div class="{css_class}">')
                html_parts.append(f'<span class="key">{key}:</span>')
                html_parts.append('<div class="nested">')
                for k, v in value.items():
                    html_parts.append(f'<div class="field"><span class="key">{k}:</span> <span class="value">{v}</span></div>')
                html_parts.append('</div></div>')
            elif isinstance(value, list):
                html_parts.append(f'<div class="{css_class}">')
                html_parts.append(f'<span class="key">{key}:</span>')
                html_parts.append(f'<span class="value">[{len(value)} items]</span>')
                html_parts.append('</div>')
            else:
                html_parts.append(f'<div class="{css_class}">')
                html_parts.append(f'<span class="key">{key}:</span>')
                html_parts.append(f'<span class="value">{value}</span>')
                html_parts.append('</div>')
        
        html_parts.append('</div>')
        
        # 変更サマリー
        if changes:
            html_parts.append('<div class="changes-summary">')
            html_parts.append(f'<h3>変更内容 ({len(changes)}件)</h3>')
            html_parts.append('<ul>')
            for key, value in changes.items():
                html_parts.append(f'<li><strong>{key}</strong>: {value}</li>')
            html_parts.append('</ul>')
            html_parts.append('</div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    def _generate_generic_preview_css(self) -> str:
        """汎用的なプレビューCSS生成"""
        return """
        .universal-preview {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .resource-type {
            color: #333;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }
        .resource-id {
            font-family: monospace;
            font-size: 12px;
            color: #666;
            margin-bottom: 20px;
        }
        .resource-details {
            margin: 20px 0;
        }
        .field {
            display: flex;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .field.changed {
            background: #fff3cd;
            padding: 8px;
            margin: 4px 0;
            border-left: 3px solid #ffc107;
        }
        .field .key {
            flex: 0 0 200px;
            font-weight: 500;
            color: #666;
        }
        .field .value {
            flex: 1;
            color: #333;
        }
        .nested {
            margin-left: 20px;
            padding-left: 20px;
            border-left: 2px solid #e0e0e0;
        }
        .changes-summary {
            margin-top: 30px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
        }
        .changes-summary h3 {
            margin: 0 0 10px;
            color: #495057;
        }
        .changes-summary ul {
            margin: 0;
            padding-left: 20px;
        }
        .changes-summary li {
            margin: 5px 0;
            color: #495057;
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
        """変更の検証（汎用）"""
        errors = []
        
        # 基本的な検証のみ
        for key, value in changes.items():
            # NULL値のチェック
            if value is None:
                errors.append(f"Field '{key}' cannot be null")
            
            # 空文字列のチェック（IDや名前フィールドの場合）
            if key in ['id', 'name', 'title', 'email'] and value == "":
                errors.append(f"Field '{key}' cannot be empty")
        
        return len(errors) == 0, errors
    
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
        endpoint = f"/{resource_type}"
        
        try:
            response = await self._session.post(endpoint, json=data)
            response.raise_for_status()
            
            result = response.json()
            
            # レスポンス形式の自動判定
            if isinstance(result, dict):
                for key in ['data', resource_type]:
                    if key in result:
                        return result[key]
            
            return result
            
        except Exception as e:
            print(f"Error creating resource: {e}")
            raise
    
    async def update_resource(
        self,
        resource_type: str,
        resource_id: str,
        data: Dict[str, Any],
        partial: bool = True
    ) -> Dict[str, Any]:
        """リソース更新"""
        endpoint = f"/{resource_type}/{resource_id}"
        
        try:
            if partial:
                # PATCH（部分更新）を試す
                response = await self._session.patch(endpoint, json=data)
                if response.status_code == 405:  # Method Not Allowed
                    # PUTにフォールバック
                    response = await self._session.put(endpoint, json=data)
            else:
                response = await self._session.put(endpoint, json=data)
            
            response.raise_for_status()
            
            result = response.json()
            
            # レスポンス形式の自動判定
            if isinstance(result, dict):
                for key in ['data', resource_type]:
                    if key in result:
                        return result[key]
            
            return result
            
        except Exception as e:
            print(f"Error updating resource: {e}")
            raise
    
    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
        soft_delete: bool = True
    ) -> bool:
        """リソース削除"""
        if soft_delete:
            # ソフトデリートを試す（ステータス更新）
            try:
                result = await self.update_resource(
                    resource_type,
                    resource_id,
                    {"status": "deleted", "deleted": True, "active": False}
                )
                return result is not None
            except:
                pass
        
        # ハードデリート
        endpoint = f"/{resource_type}/{resource_id}"
        
        try:
            response = await self._session.delete(endpoint)
            return response.status_code in [200, 204, 202]
        except Exception as e:
            print(f"Error deleting resource: {e}")
            return False
    
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
        # 24時間以内の変更のみロールバック可能
        if change_set.applied_at:
            elapsed = datetime.utcnow() - change_set.applied_at
            return elapsed.total_seconds() < 86400
        return False