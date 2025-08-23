"""
SaaSコネクタマネージャー
複数のコネクタを統合管理
"""

from typing import Dict, Any, List, Optional, Type
import asyncio
from datetime import datetime

from .base import BaseSaaSConnector, ConnectorCredentials
from .shopify import ShopifyConnector
from .stripe import StripeConnector

class ConnectorManager:
    """
    複数のSaaSコネクタを管理するマネージャークラス
    """
    
    # 利用可能なコネクタ
    AVAILABLE_CONNECTORS: Dict[str, Type[BaseSaaSConnector]] = {
        "shopify": ShopifyConnector,
        "stripe": StripeConnector,
    }
    
    def __init__(self):
        self.connectors: Dict[str, BaseSaaSConnector] = {}
        self.credentials_store: Dict[str, ConnectorCredentials] = {}
        
    async def register_connector(
        self,
        name: str,
        connector_type: str,
        credentials: ConnectorCredentials,
        **kwargs
    ) -> bool:
        """
        コネクタの登録
        
        Args:
            name: コネクタの識別名
            connector_type: コネクタタイプ（shopify, stripe等）
            credentials: 認証情報
            **kwargs: コネクタ固有のパラメータ
        
        Returns:
            bool: 登録成功/失敗
        """
        if connector_type not in self.AVAILABLE_CONNECTORS:
            raise ValueError(f"Unknown connector type: {connector_type}")
        
        connector_class = self.AVAILABLE_CONNECTORS[connector_type]
        
        # コネクタインスタンスの作成
        if connector_type == "shopify":
            connector = connector_class(
                store_domain=kwargs.get("store_domain", ""),
                credentials=credentials
            )
        elif connector_type == "stripe":
            connector = connector_class(
                credentials=credentials,
                test_mode=kwargs.get("test_mode", False)
            )
        else:
            connector = connector_class(
                config=kwargs.get("config"),
                credentials=credentials
            )
        
        # 初期化と接続検証
        initialized = await connector.initialize()
        if not initialized:
            return False
        
        # 登録
        self.connectors[name] = connector
        self.credentials_store[name] = credentials
        
        return True
    
    async def unregister_connector(self, name: str) -> bool:
        """
        コネクタの登録解除
        
        Args:
            name: コネクタの識別名
        
        Returns:
            bool: 解除成功/失敗
        """
        if name not in self.connectors:
            return False
        
        connector = self.connectors[name]
        await connector.close()
        
        del self.connectors[name]
        del self.credentials_store[name]
        
        return True
    
    def get_connector(self, name: str) -> Optional[BaseSaaSConnector]:
        """
        コネクタの取得
        
        Args:
            name: コネクタの識別名
        
        Returns:
            BaseSaaSConnector: コネクタインスタンス
        """
        return self.connectors.get(name)
    
    def list_connectors(self) -> List[Dict[str, Any]]:
        """
        登録済みコネクタ一覧
        
        Returns:
            List[Dict]: コネクタ情報のリスト
        """
        result = []
        for name, connector in self.connectors.items():
            result.append({
                "name": name,
                "type": connector.config.type,
                "auth_method": connector.config.auth_method,
                "base_url": connector.config.base_url,
                "initialized": connector._initialized
            })
        return result
    
    async def execute_cross_platform(
        self,
        operation: str,
        connectors: List[str],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        複数プラットフォームでの同時実行
        
        Args:
            operation: 実行する操作（list_resources, search_resources等）
            connectors: 対象コネクタ名のリスト
            params: 操作パラメータ
        
        Returns:
            Dict: 各コネクタの実行結果
        """
        tasks = []
        connector_names = []
        
        for name in connectors:
            connector = self.get_connector(name)
            if connector:
                method = getattr(connector, operation, None)
                if method:
                    tasks.append(method(**params))
                    connector_names.append(name)
        
        if not tasks:
            return {}
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            name: result if not isinstance(result, Exception) else {"error": str(result)}
            for name, result in zip(connector_names, results)
        }
    
    async def sync_resources(
        self,
        source_connector: str,
        target_connector: str,
        resource_type: str,
        mapping: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        リソースの同期
        
        Args:
            source_connector: ソースコネクタ名
            target_connector: ターゲットコネクタ名
            resource_type: リソースタイプ
            mapping: フィールドマッピング
        
        Returns:
            Dict: 同期結果
        """
        source = self.get_connector(source_connector)
        target = self.get_connector(target_connector)
        
        if not source or not target:
            raise ValueError("Invalid connector names")
        
        # ソースからリソース取得
        source_resources = await source.list_resources(resource_type)
        
        sync_results = {
            "total": len(source_resources),
            "synced": 0,
            "failed": 0,
            "errors": []
        }
        
        for resource in source_resources:
            try:
                # フィールドマッピング適用
                if mapping:
                    mapped_resource = self._apply_mapping(resource, mapping)
                else:
                    mapped_resource = resource
                
                # ターゲットに作成または更新
                existing = await target.search_resources(
                    resource_type,
                    query=resource.get("id", "")
                )
                
                if existing:
                    await target.update_resource(
                        resource_type,
                        existing[0]["id"],
                        mapped_resource
                    )
                else:
                    await target.create_resource(
                        resource_type,
                        mapped_resource
                    )
                
                sync_results["synced"] += 1
                
            except Exception as e:
                sync_results["failed"] += 1
                sync_results["errors"].append({
                    "resource_id": resource.get("id"),
                    "error": str(e)
                })
        
        return sync_results
    
    def _apply_mapping(self, resource: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        フィールドマッピングの適用
        
        Args:
            resource: 元のリソース
            mapping: マッピング定義
        
        Returns:
            Dict: マッピング適用後のリソース
        """
        mapped = {}
        
        for source_field, target_field in mapping.items():
            # ネストされたフィールドのサポート
            if "." in source_field:
                value = resource
                for key in source_field.split("."):
                    value = value.get(key, {})
                    if not isinstance(value, dict):
                        break
            else:
                value = resource.get(source_field)
            
            if "." in target_field:
                keys = target_field.split(".")
                target = mapped
                for key in keys[:-1]:
                    target = target.setdefault(key, {})
                target[keys[-1]] = value
            else:
                mapped[target_field] = value
        
        return mapped
    
    async def create_unified_preview(
        self,
        connectors: List[str],
        changes: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        統合プレビューの生成
        
        Args:
            connectors: 対象コネクタ名のリスト
            changes: 各コネクタへの変更内容
        
        Returns:
            Dict: 統合プレビュー結果
        """
        previews = {}
        
        for name in connectors:
            if name not in changes:
                continue
            
            connector = self.get_connector(name)
            if not connector:
                continue
            
            # 各コネクタでプレビュー生成
            resource_changes = changes[name]
            snapshot = await connector.create_snapshot(
                resource_changes["resource_type"],
                resource_changes["resource_id"]
            )
            
            preview = await connector.generate_preview(
                snapshot,
                resource_changes["changes"]
            )
            
            previews[name] = preview
        
        # 統合HTMLの生成
        combined_html = self._generate_combined_preview_html(previews)
        combined_css = self._generate_combined_preview_css(previews)
        
        return {
            "html": combined_html,
            "css": combined_css,
            "previews": previews,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _generate_combined_preview_html(self, previews: Dict[str, Dict[str, Any]]) -> str:
        """統合プレビューHTML生成"""
        sections = []
        
        for name, preview in previews.items():
            sections.append(f"""
            <div class="connector-preview" data-connector="{name}">
                <h3 class="connector-title">{name.upper()}</h3>
                <div class="connector-content">
                    {preview.get('html', '')}
                </div>
            </div>
            """)
        
        return f"""
        <div class="unified-preview">
            <h2 class="preview-title">統合プレビュー</h2>
            <div class="preview-sections">
                {"".join(sections)}
            </div>
        </div>
        """
    
    def _generate_combined_preview_css(self, previews: Dict[str, Dict[str, Any]]) -> str:
        """統合プレビューCSS生成"""
        base_css = """
        .unified-preview {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 20px;
        }
        .preview-title {
            font-size: 24px;
            margin-bottom: 30px;
            color: #333;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
        }
        .preview-sections {
            display: grid;
            gap: 30px;
        }
        .connector-preview {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            background: #fff;
        }
        .connector-title {
            font-size: 18px;
            margin-bottom: 20px;
            color: #666;
        }
        .connector-content {
            position: relative;
        }
        """
        
        # 各コネクタのCSSを結合
        connector_css = []
        for name, preview in previews.items():
            css = preview.get('css', '')
            # スコープを追加
            scoped_css = f".connector-preview[data-connector='{name}'] {{\n{css}\n}}"
            connector_css.append(scoped_css)
        
        return base_css + "\n" + "\n".join(connector_css)
    
    async def health_check(self) -> Dict[str, Any]:
        """
        全コネクタのヘルスチェック
        
        Returns:
            Dict: ヘルスチェック結果
        """
        results = {}
        
        for name, connector in self.connectors.items():
            try:
                # 接続検証
                is_connected = await connector.validate_connection()
                
                # API状態取得
                api_status = await connector.get_api_status()
                
                # レート制限状態
                rate_limit = await connector.get_rate_limit_status()
                
                results[name] = {
                    "status": "healthy" if is_connected else "unhealthy",
                    "connected": is_connected,
                    "api_status": api_status,
                    "rate_limit": rate_limit,
                    "timestamp": datetime.utcnow().isoformat()
                }
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return results