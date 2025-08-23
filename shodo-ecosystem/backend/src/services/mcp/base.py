"""
MCP Base Classes - Model Context Protocol基盤実装
「必要な機能を自動的に作成する」ための基盤クラス群
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger()

class MCPResultStatus(Enum):
    """MCP実行結果ステータス"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    RETRY_REQUIRED = "retry_required"

@dataclass
class MCPResult:
    """MCP実行結果"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    status: MCPResultStatus = MCPResultStatus.SUCCESS
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # ステータスの自動設定
        if not self.success and self.status == MCPResultStatus.SUCCESS:
            self.status = MCPResultStatus.ERROR

class MCPCapability(Enum):
    """MCP機能定義"""
    # 基本CRUD操作
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    
    # 検索・フィルタリング
    SEARCH = "search"
    FILTER = "filter"
    SORT = "sort"
    
    # 一括操作
    BULK_CREATE = "bulk_create"
    BULK_UPDATE = "bulk_update"
    BULK_DELETE = "bulk_delete"
    
    # データ同期
    SYNC = "sync"
    REAL_TIME_SYNC = "real_time_sync"
    
    # 認証・認可
    AUTHENTICATE = "authenticate"
    AUTHORIZE = "authorize"
    
    # 業務機能
    INVENTORY_MANAGEMENT = "inventory_management"
    USER_MANAGEMENT = "user_management"
    ORDER_MANAGEMENT = "order_management"
    PAYMENT_PROCESSING = "payment_processing"
    
    # 通知・アラート
    NOTIFICATIONS = "notifications"
    WEBHOOKS = "webhooks"
    
    # ファイル操作
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    
    # レポート・分析
    REPORTING = "reporting"
    ANALYTICS = "analytics"

@dataclass
class MCPCommand:
    """MCPコマンド定義"""
    name: str
    description: str
    parameters: Dict[str, Any]
    required_capabilities: List[MCPCapability]
    expected_result_type: type

class BaseMCPConnector(ABC):
    """
    MCP基盤コネクタ
    
    全ての自動生成コネクタの基底クラス
    統一されたインターフェースを提供
    """
    
    def __init__(self):
        self.service_name: str = ""
        self.is_authenticated: bool = False
        self.capabilities: List[MCPCapability] = []
        self.metadata: Dict[str, Any] = {}
        
    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        認証処理
        
        Args:
            credentials: 認証情報
            
        Returns:
            認証成功フラグ
        """
    
    @abstractmethod
    async def execute_command(self, command: str, params: Dict[str, Any]) -> MCPResult:
        """
        コマンド実行
        
        Args:
            command: 実行コマンド
            params: パラメータ
            
        Returns:
            実行結果
        """
    
    async def get_capabilities(self) -> List[MCPCapability]:
        """利用可能機能の取得"""
        return self.capabilities
    
    async def health_check(self) -> MCPResult:
        """ヘルスチェック"""
        try:
            # 基本的な接続テスト
            await self.execute_command("health", {})
            return MCPResult(
                success=True,
                data={"status": "healthy", "capabilities": len(self.capabilities)},
                metadata={"timestamp": "now"}
            )
        except Exception as e:
            return MCPResult(
                success=False,
                error=f"Health check failed: {str(e)}",
                status=MCPResultStatus.ERROR
            )
    
    async def get_schema(self) -> Dict[str, Any]:
        """データスキーマの取得"""
        return {
            "service": self.service_name,
            "capabilities": [cap.value for cap in self.capabilities],
            "commands": await self._get_available_commands(),
            "data_types": await self._get_data_types()
        }
    
    async def _get_available_commands(self) -> List[Dict[str, Any]]:
        """利用可能コマンド一覧"""
        # 基本コマンド
        commands = [
            {
                "name": "list_items",
                "description": "アイテム一覧取得",
                "parameters": {"limit": "int", "offset": "int"},
                "capabilities": [MCPCapability.READ.value]
            },
            {
                "name": "create_item",
                "description": "アイテム作成",
                "parameters": {"data": "object"},
                "capabilities": [MCPCapability.CREATE.value]
            },
            {
                "name": "update_item",
                "description": "アイテム更新",
                "parameters": {"id": "string", "data": "object"},
                "capabilities": [MCPCapability.UPDATE.value]
            },
            {
                "name": "delete_item",
                "description": "アイテム削除",
                "parameters": {"id": "string"},
                "capabilities": [MCPCapability.DELETE.value]
            }
        ]
        
        return commands
    
    async def _get_data_types(self) -> Dict[str, Any]:
        """データ型定義"""
        return {
            "item": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "price": {"type": "number"},
                    "created_at": {"type": "string", "format": "datetime"}
                }
            }
        }

class UniversalMCPConnector(BaseMCPConnector):
    """
    汎用MCPコネクタ
    
    任意のサービスに対応できる汎用実装
    プロトコル分析結果に基づいて動的に動作を決定
    """
    
    def __init__(self, protocol_spec: Dict[str, Any]):
        super().__init__()
        self.protocol_spec = protocol_spec
        self.service_name = protocol_spec.get("service_name", "unknown")
        self.endpoints = protocol_spec.get("endpoints", [])
        self.auth_flow = protocol_spec.get("auth_flow", {})
        
        # 機能の自動検出
        self._auto_detect_capabilities()
    
    def _auto_detect_capabilities(self):
        """機能の自動検出"""
        detected_capabilities = []
        
        # エンドポイントから機能を推論
        for endpoint in self.endpoints:
            method = endpoint.get("method", "").upper()
            url = endpoint.get("url", "").lower()
            
            if method == "GET":
                detected_capabilities.append(MCPCapability.READ)
            elif method == "POST":
                detected_capabilities.append(MCPCapability.CREATE)
            elif method in ["PUT", "PATCH"]:
                detected_capabilities.append(MCPCapability.UPDATE)
            elif method == "DELETE":
                detected_capabilities.append(MCPCapability.DELETE)
            
            # URL から業務機能を推論
            if any(keyword in url for keyword in ["inventory", "stock", "item"]):
                detected_capabilities.append(MCPCapability.INVENTORY_MANAGEMENT)
            elif any(keyword in url for keyword in ["user", "account"]):
                detected_capabilities.append(MCPCapability.USER_MANAGEMENT)
            elif any(keyword in url for keyword in ["order", "purchase"]):
                detected_capabilities.append(MCPCapability.ORDER_MANAGEMENT)
        
        self.capabilities = list(set(detected_capabilities))
    
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """汎用認証処理"""
        try:
            auth_type = self.auth_flow.get("type", "none")
            
            if auth_type == "none":
                self.is_authenticated = True
                return True
            elif auth_type == "form_based":
                return await self._form_based_auth(credentials)
            elif auth_type == "oauth":
                return await self._oauth_auth(credentials)
            elif auth_type == "api_key":
                return await self._api_key_auth(credentials)
            else:
                logger.warning(f"Unknown auth type: {auth_type}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    async def _form_based_auth(self, credentials: Dict[str, Any]) -> bool:
        """フォームベース認証"""
        # 実装は認証フローの詳細に基づく
        # 実際の実装では、フォーム送信、セッション管理等を行う
        self.is_authenticated = True
        return True
    
    async def _oauth_auth(self, credentials: Dict[str, Any]) -> bool:
        """OAuth認証"""
        # OAuth フローの実装
        self.is_authenticated = True
        return True
    
    async def _api_key_auth(self, credentials: Dict[str, Any]) -> bool:
        """APIキー認証"""
        api_key = credentials.get("api_key")
        if api_key:
            self.metadata["api_key"] = api_key
            self.is_authenticated = True
            return True
        return False
    
    async def execute_command(self, command: str, params: Dict[str, Any]) -> MCPResult:
        """汎用コマンド実行"""
        if not self.is_authenticated:
            return MCPResult(
                success=False,
                error="Authentication required",
                status=MCPResultStatus.ERROR
            )
        
        try:
            # コマンドとエンドポイントのマッピング
            endpoint = self._find_endpoint_for_command(command)
            if not endpoint:
                return MCPResult(
                    success=False,
                    error=f"No endpoint found for command: {command}",
                    status=MCPResultStatus.ERROR
                )
            
            # HTTP リクエスト実行
            result = await self._execute_http_request(endpoint, params)
            return result
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return MCPResult(
                success=False,
                error=str(e),
                status=MCPResultStatus.ERROR
            )
    
    def _find_endpoint_for_command(self, command: str) -> Optional[Dict[str, Any]]:
        """コマンドに対応するエンドポイントを検索"""
        
        command_mapping = {
            "list_items": ["GET"],
            "create_item": ["POST"],
            "update_item": ["PUT", "PATCH"],
            "delete_item": ["DELETE"],
            "search": ["GET"],
            "health": ["GET"]
        }
        
        target_methods = command_mapping.get(command, [])
        
        for endpoint in self.endpoints:
            if endpoint.get("method") in target_methods:
                return endpoint
        
        return None
    
    async def _execute_http_request(self, endpoint: Dict[str, Any], params: Dict[str, Any]) -> MCPResult:
        """HTTP リクエスト実行"""
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                method = endpoint.get("method", "GET")
                url = endpoint.get("url")
                headers = endpoint.get("headers", {})
                
                # API キーがあれば追加
                if "api_key" in self.metadata:
                    headers["Authorization"] = f"Bearer {self.metadata['api_key']}"
                
                if method == "GET":
                    response = await client.get(url, params=params, headers=headers)
                elif method == "POST":
                    response = await client.post(url, json=params, headers=headers)
                elif method in ["PUT", "PATCH"]:
                    response = await client.request(method, url, json=params, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                if response.status_code < 400:
                    try:
                        data = response.json()
                    except:
                        data = response.text
                    
                    return MCPResult(
                        success=True,
                        data=data,
                        metadata={
                            "status_code": response.status_code,
                            "headers": dict(response.headers)
                        }
                    )
                else:
                    return MCPResult(
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}",
                        status=MCPResultStatus.ERROR
                    )
                    
        except Exception as e:
            return MCPResult(
                success=False,
                error=str(e),
                status=MCPResultStatus.ERROR
            )

class MCPConnectorFactory:
    """MCPコネクタファクトリ"""
    
    @staticmethod
    def create_connector(
        protocol_spec: Dict[str, Any], 
        connector_type: str = "universal"
    ) -> BaseMCPConnector:
        """
        プロトコル仕様からコネクタを生成
        
        Args:
            protocol_spec: プロトコル仕様
            connector_type: コネクタタイプ
            
        Returns:
            生成されたコネクタ
        """
        
        if connector_type == "universal":
            return UniversalMCPConnector(protocol_spec)
        else:
            raise ValueError(f"Unknown connector type: {connector_type}")
    
    @staticmethod
    def create_from_analysis(analysis_result: Dict[str, Any]) -> BaseMCPConnector:
        """分析結果からコネクタを生成"""
        
        # 分析結果をプロトコル仕様に変換
        protocol_spec = {
            "service_name": analysis_result.get("service_name", "unknown"),
            "endpoints": analysis_result.get("endpoints", []),
            "auth_flow": analysis_result.get("auth_flow", {}),
            "capabilities": analysis_result.get("capabilities", [])
        }
        
        return MCPConnectorFactory.create_connector(protocol_spec)

# エクスポート
__all__ = [
    "BaseMCPConnector",
    "UniversalMCPConnector", 
    "MCPResult",
    "MCPCapability",
    "MCPCommand",
    "MCPConnectorFactory",
    "MCPResultStatus"
]