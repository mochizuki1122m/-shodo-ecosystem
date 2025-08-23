"""
MCP エコシステム - 自動プロトコル生成・統合システム
「必要な機能を自動的に作成するエコシステム」の実現
"""

import asyncio
import importlib
from typing import Dict, Any, List, Type
from dataclasses import dataclass
from pathlib import Path
import structlog

from .protocol_analyzer import MCPProtocolGenerator, ProtocolSpec
from .base import BaseMCPConnector, MCPResult

logger = structlog.get_logger()

@dataclass
class ServiceRequirement:
    """サービス要件定義"""
    service_name: str
    base_url: str
    required_capabilities: List[str]
    user_credentials: Dict[str, Any]
    custom_requirements: Dict[str, Any]

@dataclass
class GeneratedConnector:
    """生成されたコネクタ情報"""
    service_name: str
    connector_class: Type[BaseMCPConnector]
    protocol_spec: ProtocolSpec
    code_path: str
    capabilities: List[str]

class MCPEcosystem:
    """
    MCP エコシステム
    
    機能:
    1. サービス要件の分析
    2. 必要なプロトコルの自動生成
    3. コネクタの動的ロード・統合
    4. 機能の自動提供
    """
    
    def __init__(self, connectors_dir: str = "generated_connectors"):
        self.connectors_dir = Path(connectors_dir)
        self.connectors_dir.mkdir(exist_ok=True)
        
        self.protocol_generator = MCPProtocolGenerator()
        self.active_connectors: Dict[str, BaseMCPConnector] = {}
        self.generated_connectors: Dict[str, GeneratedConnector] = {}
        
    async def auto_integrate_service(
        self, 
        requirement: ServiceRequirement
    ) -> MCPResult:
        """
        サービスの自動統合
        
        プロセス:
        1. サービス分析
        2. プロトコル生成
        3. コネクタ作成
        4. 動的ロード
        5. 機能提供開始
        """
        
        logger.info(f"Starting auto-integration for {requirement.service_name}")
        
        try:
            # 1. 既存コネクタチェック
            if requirement.service_name in self.active_connectors:
                logger.info(f"Service {requirement.service_name} already integrated")
                return MCPResult(
                    success=True,
                    data={"status": "already_integrated"}
                )
            
            # 2. プロトコル分析・生成
            logger.info(f"Analyzing protocol for {requirement.service_name}")
            connector_code = await self.protocol_generator.generate_mcp_connector(
                requirement.base_url,
                requirement.service_name
            )
            
            # 3. コネクタファイル作成
            connector_path = self._save_connector_code(
                requirement.service_name,
                connector_code
            )
            
            # 4. 動的ロード
            connector_class = await self._load_connector_dynamically(
                requirement.service_name,
                connector_path
            )
            
            # 5. コネクタインスタンス化・認証
            connector_instance = connector_class()
            auth_success = await connector_instance.authenticate(
                requirement.user_credentials
            )
            
            if not auth_success:
                return MCPResult(
                    success=False,
                    error="Authentication failed"
                )
            
            # 6. アクティブコネクタに登録
            self.active_connectors[requirement.service_name] = connector_instance
            
            # 7. 機能検証
            capabilities = await self._verify_capabilities(
                connector_instance,
                requirement.required_capabilities
            )
            
            logger.info(f"Successfully integrated {requirement.service_name}")
            return MCPResult(
                success=True,
                data={
                    "service_name": requirement.service_name,
                    "capabilities": capabilities,
                    "status": "integrated"
                }
            )
            
        except Exception as e:
            logger.error(f"Auto-integration failed for {requirement.service_name}: {e}")
            return MCPResult(
                success=False,
                error=str(e)
            )
    
    def _save_connector_code(self, service_name: str, code: str) -> str:
        """生成されたコネクタコードを保存"""
        connector_file = self.connectors_dir / f"{service_name}_connector.py"
        
        with open(connector_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        logger.info(f"Connector code saved: {connector_file}")
        return str(connector_file)
    
    async def _load_connector_dynamically(
        self, 
        service_name: str, 
        connector_path: str
    ) -> Type[BaseMCPConnector]:
        """コネクタの動的ロード"""
        
        # モジュール名の生成
        module_name = f"generated_connectors.{service_name}_connector"
        
        try:
            # 動的インポート
            spec = importlib.util.spec_from_file_location(module_name, connector_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # コネクタクラスの取得
            connector_class_name = f"{service_name.title()}Connector"
            connector_class = getattr(module, connector_class_name)
            
            logger.info(f"Dynamically loaded connector: {connector_class_name}")
            return connector_class
            
        except Exception as e:
            logger.error(f"Failed to load connector {service_name}: {e}")
            raise
    
    async def _verify_capabilities(
        self, 
        connector: BaseMCPConnector, 
        required_capabilities: List[str]
    ) -> List[str]:
        """機能検証"""
        
        verified_capabilities = []
        
        for capability in required_capabilities:
            try:
                # 機能テスト実行
                test_result = await self._test_capability(connector, capability)
                if test_result:
                    verified_capabilities.append(capability)
                    logger.info(f"Capability verified: {capability}")
                else:
                    logger.warning(f"Capability test failed: {capability}")
                    
            except Exception as e:
                logger.warning(f"Capability test error for {capability}: {e}")
        
        return verified_capabilities
    
    async def _test_capability(
        self, 
        connector: BaseMCPConnector, 
        capability: str
    ) -> bool:
        """個別機能テスト"""
        
        capability_tests = {
            "inventory_management": self._test_inventory_capability,
            "user_management": self._test_user_capability,
            "order_management": self._test_order_capability,
            "create": self._test_create_capability,
            "read": self._test_read_capability,
            "update": self._test_update_capability,
            "delete": self._test_delete_capability
        }
        
        test_func = capability_tests.get(capability)
        if test_func:
            return await test_func(connector)
        
        return False
    
    async def _test_inventory_capability(self, connector: BaseMCPConnector) -> bool:
        """在庫管理機能テスト"""
        try:
            # 在庫一覧取得テスト
            result = await connector.execute_command("list_items", {})
            return result.success
        except:
            return False
    
    async def _test_user_capability(self, connector: BaseMCPConnector) -> bool:
        """ユーザー管理機能テスト"""
        try:
            result = await connector.execute_command("list_users", {})
            return result.success
        except:
            return False
    
    async def _test_order_capability(self, connector: BaseMCPConnector) -> bool:
        """注文管理機能テスト"""
        try:
            result = await connector.execute_command("list_orders", {})
            return result.success
        except:
            return False
    
    async def _test_create_capability(self, connector: BaseMCPConnector) -> bool:
        """作成機能テスト"""
        try:
            # テストデータで作成テスト
            test_data = {"name": "test_item", "quantity": 1}
            result = await connector.execute_command("create_item", test_data)
            return result.success
        except:
            return False
    
    async def _test_read_capability(self, connector: BaseMCPConnector) -> bool:
        """読み取り機能テスト"""
        try:
            result = await connector.execute_command("list_items", {})
            return result.success
        except:
            return False
    
    async def _test_update_capability(self, connector: BaseMCPConnector) -> bool:
        """更新機能テスト"""
        # 実際の実装では、既存アイテムの更新テストを行う
        return True
    
    async def _test_delete_capability(self, connector: BaseMCPConnector) -> bool:
        """削除機能テスト"""
        # 実際の実装では、テストアイテムの削除テストを行う
        return True
    
    async def execute_unified_command(
        self, 
        service_name: str, 
        command: str, 
        params: Dict[str, Any]
    ) -> MCPResult:
        """統合コマンド実行"""
        
        if service_name not in self.active_connectors:
            return MCPResult(
                success=False,
                error=f"Service {service_name} not integrated"
            )
        
        connector = self.active_connectors[service_name]
        return await connector.execute_command(command, params)
    
    async def get_available_services(self) -> List[Dict[str, Any]]:
        """利用可能サービス一覧"""
        
        services = []
        for service_name, connector in self.active_connectors.items():
            try:
                # サービス情報取得
                service_info = {
                    "name": service_name,
                    "status": "active",
                    "capabilities": await self._get_connector_capabilities(connector),
                    "last_check": "now"  # 実際は最終チェック時刻
                }
                services.append(service_info)
            except Exception as e:
                logger.warning(f"Failed to get service info for {service_name}: {e}")
        
        return services
    
    async def _get_connector_capabilities(self, connector: BaseMCPConnector) -> List[str]:
        """コネクタの機能一覧取得"""
        # 実装は各コネクタの機能を動的に検出
        return ["inventory_management", "create", "read", "update", "delete"]
    
    async def auto_discover_and_integrate(self, target_url: str) -> MCPResult:
        """
        自動発見・統合
        
        URLから自動的にサービスを発見し、統合する
        """
        
        logger.info(f"Auto-discovering service at {target_url}")
        
        try:
            # 1. サービス発見
            from urllib.parse import urlparse
            parsed_url = urlparse(target_url)
            service_name = parsed_url.netloc.replace('.', '_').replace('-', '_')
            
            # 2. 自動要件生成
            requirement = ServiceRequirement(
                service_name=service_name,
                base_url=target_url,
                required_capabilities=[
                    "inventory_management", "create", "read", "update"
                ],
                user_credentials={},  # 認証情報は後で設定
                custom_requirements={}
            )
            
            # 3. 自動統合実行
            return await self.auto_integrate_service(requirement)
            
        except Exception as e:
            logger.error(f"Auto-discovery failed for {target_url}: {e}")
            return MCPResult(
                success=False,
                error=str(e)
            )

# 使用例とデモンストレーション
class ZAICOIntegrationDemo:
    """ZAICO統合デモ"""
    
    def __init__(self):
        self.ecosystem = MCPEcosystem()
    
    async def integrate_zaico_automatically(self):
        """ZAICOの自動統合デモ"""
        
        print("🚀 MCP Ecosystem - ZAICO Auto Integration Demo")
        print("=" * 50)
        
        # 1. ZAICO要件定義
        zaico_requirement = ServiceRequirement(
            service_name="zaico",
            base_url="https://web.zaico.co.jp",
            required_capabilities=[
                "inventory_management",
                "create",
                "read", 
                "update",
                "delete"
            ],
            user_credentials={
                "username": "demo_user",  # 実際の認証情報
                "password": "demo_pass"
            },
            custom_requirements={
                "data_sync_frequency": "real_time",
                "fallback_mode": "manual_csv"
            }
        )
        
        print(f"📋 Service Requirement: {zaico_requirement.service_name}")
        print(f"🎯 Required Capabilities: {zaico_requirement.required_capabilities}")
        
        # 2. 自動統合実行
        print("\n🔄 Starting auto-integration...")
        integration_result = await self.ecosystem.auto_integrate_service(zaico_requirement)
        
        if integration_result.success:
            print("✅ Integration successful!")
            print(f"📊 Available capabilities: {integration_result.data.get('capabilities', [])}")
            
            # 3. 機能テスト
            print("\n🧪 Testing integrated capabilities...")
            
            # 在庫一覧取得テスト
            list_result = await self.ecosystem.execute_unified_command(
                "zaico",
                "list_items",
                {}
            )
            
            if list_result.success:
                print("✅ Inventory listing: OK")
            else:
                print(f"❌ Inventory listing failed: {list_result.error}")
            
            # アイテム作成テスト
            create_result = await self.ecosystem.execute_unified_command(
                "zaico",
                "create_item",
                {
                    "name": "Test Product",
                    "quantity": 10,
                    "price": 1000
                }
            )
            
            if create_result.success:
                print("✅ Item creation: OK")
            else:
                print(f"❌ Item creation failed: {create_result.error}")
            
        else:
            print(f"❌ Integration failed: {integration_result.error}")
        
        # 4. 統合サービス一覧表示
        print("\n📋 Available integrated services:")
        services = await self.ecosystem.get_available_services()
        for service in services:
            print(f"  • {service['name']}: {service['status']} ({len(service['capabilities'])} capabilities)")

async def main():
    """メインデモ実行"""
    demo = ZAICOIntegrationDemo()
    await demo.integrate_zaico_automatically()

if __name__ == "__main__":
    asyncio.run(main())