"""
MCP Protocol Analyzer - API導線自動分析・生成システム
既存SaaSの制限を超越し、必要な機能を自動的に実現する
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

logger = structlog.get_logger()

class ProtocolType(Enum):
    """プロトコルタイプ"""
    REST_API = "rest_api"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    WEB_SCRAPING = "web_scraping"
    BROWSER_AUTOMATION = "browser_automation"
    FORM_SUBMISSION = "form_submission"

@dataclass
class APIEndpoint:
    """API エンドポイント情報"""
    url: str
    method: str
    headers: Dict[str, str]
    params: Dict[str, Any]
    auth_type: str
    response_schema: Dict[str, Any]
    rate_limit: Optional[Dict[str, Any]] = None

@dataclass
class DataFlow:
    """データフロー定義"""
    source: str
    target: str
    transformation: Dict[str, Any]
    validation: Dict[str, Any]
    frequency: str

@dataclass
class ProtocolSpec:
    """プロトコル仕様"""
    service_name: str
    base_url: str
    protocol_type: ProtocolType
    endpoints: List[APIEndpoint]
    auth_flow: Dict[str, Any]
    data_flows: List[DataFlow]
    capabilities: List[str]

class ProtocolAnalyzer:
    """プロトコル分析器 - SaaSの機能を分析し、必要なAPIを自動生成"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True
        )
        self.discovered_protocols = {}
    
    async def analyze_service(self, service_url: str, service_name: str) -> ProtocolSpec:
        """
        サービスを分析し、プロトコル仕様を生成
        
        Args:
            service_url: 対象サービスのURL
            service_name: サービス名
            
        Returns:
            自動生成されたプロトコル仕様
        """
        logger.info(f"Analyzing service: {service_name} at {service_url}")
        
        # 1. サービス探索
        discovery_result = await self._discover_service_structure(service_url)
        
        # 2. API エンドポイント分析
        endpoints = await self._analyze_api_endpoints(service_url, discovery_result)
        
        # 3. 認証フロー分析
        auth_flow = await self._analyze_auth_flow(service_url, discovery_result)
        
        # 4. データスキーマ分析
        data_schemas = await self._analyze_data_schemas(endpoints)
        
        # 5. 機能分析
        capabilities = await self._analyze_capabilities(service_url, discovery_result)
        
        # 6. プロトコル仕様生成
        protocol_spec = ProtocolSpec(
            service_name=service_name,
            base_url=service_url,
            protocol_type=self._determine_protocol_type(discovery_result),
            endpoints=endpoints,
            auth_flow=auth_flow,
            data_flows=self._generate_data_flows(endpoints, data_schemas),
            capabilities=capabilities
        )
        
        logger.info(f"Protocol analysis completed for {service_name}")
        return protocol_spec
    
    async def _discover_service_structure(self, base_url: str) -> Dict[str, Any]:
        """サービス構造の探索"""
        discovery_result = {
            "pages": [],
            "forms": [],
            "api_hints": [],
            "auth_elements": [],
            "data_elements": []
        }
        
        try:
            # メインページ分析
            response = await self.client.get(base_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # API ヒントの検出
            api_hints = self._detect_api_hints(soup, base_url)
            discovery_result["api_hints"].extend(api_hints)
            
            # フォーム分析
            forms = self._analyze_forms(soup, base_url)
            discovery_result["forms"].extend(forms)
            
            # 認証要素の検出
            auth_elements = self._detect_auth_elements(soup)
            discovery_result["auth_elements"].extend(auth_elements)
            
            # よく使われるAPIパスの探索
            common_paths = [
                "/api", "/api/v1", "/api/v2", "/graphql",
                "/rest", "/oauth", "/login", "/auth"
            ]
            
            for path in common_paths:
                try:
                    test_url = urljoin(base_url, path)
                    test_response = await self.client.get(test_url)
                    if test_response.status_code in [200, 401, 403]:
                        discovery_result["api_hints"].append({
                            "url": test_url,
                            "status": test_response.status_code,
                            "content_type": test_response.headers.get("content-type", ""),
                            "potential_api": True
                        })
                except:
                    continue
            
        except Exception as e:
            logger.warning(f"Service discovery failed: {e}")
        
        return discovery_result
    
    def _detect_api_hints(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """API ヒントの検出"""
        hints = []
        
        # JavaScript内のAPI呼び出し検出
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # fetch, axios, XMLHttpRequest の検出
                api_calls = re.findall(r'(?:fetch|axios|XMLHttpRequest).*?["\']([^"\']+)["\']', script.string)
                for call in api_calls:
                    if call.startswith('/') or call.startswith('http'):
                        hints.append({
                            "url": urljoin(base_url, call),
                            "source": "javascript",
                            "type": "api_call"
                        })
        
        # data-api 属性の検出
        elements_with_api = soup.find_all(attrs={"data-api": True})
        for element in elements_with_api:
            api_url = element.get("data-api")
            if api_url:
                hints.append({
                    "url": urljoin(base_url, api_url),
                    "source": "data_attribute",
                    "type": "api_endpoint"
                })
        
        return hints
    
    def _analyze_forms(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """フォーム分析"""
        forms = []
        
        for form in soup.find_all('form'):
            form_data = {
                "action": urljoin(base_url, form.get('action', '')),
                "method": form.get('method', 'GET').upper(),
                "fields": [],
                "potential_api": False
            }
            
            # フィールド分析
            for field in form.find_all(['input', 'select', 'textarea']):
                field_info = {
                    "name": field.get('name'),
                    "type": field.get('type', 'text'),
                    "required": field.has_attr('required'),
                    "value": field.get('value')
                }
                form_data["fields"].append(field_info)
            
            # API的なフォームかどうかの判定
            action = form_data["action"]
            if any(keyword in action.lower() for keyword in ['api', 'ajax', 'json']):
                form_data["potential_api"] = True
            
            forms.append(form_data)
        
        return forms
    
    def _detect_auth_elements(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """認証要素の検出"""
        auth_elements = []
        
        # ログインフォーム
        login_forms = soup.find_all('form', class_=re.compile(r'login|signin|auth'))
        for form in login_forms:
            auth_elements.append({
                "type": "login_form",
                "action": form.get('action'),
                "method": form.get('method', 'POST'),
                "fields": [field.get('name') for field in form.find_all('input')]
            })
        
        # OAuth ボタン
        oauth_buttons = soup.find_all(['a', 'button'], href=re.compile(r'oauth|auth'))
        for button in oauth_buttons:
            auth_elements.append({
                "type": "oauth_button",
                "href": button.get('href'),
                "text": button.get_text(strip=True)
            })
        
        return auth_elements
    
    async def _analyze_api_endpoints(self, base_url: str, discovery_result: Dict[str, Any]) -> List[APIEndpoint]:
        """API エンドポイントの分析"""
        endpoints = []
        
        for hint in discovery_result["api_hints"]:
            try:
                endpoint_info = await self._probe_endpoint(hint["url"])
                if endpoint_info:
                    endpoints.append(endpoint_info)
            except Exception as e:
                logger.debug(f"Failed to probe endpoint {hint['url']}: {e}")
        
        return endpoints
    
    async def _probe_endpoint(self, url: str) -> Optional[APIEndpoint]:
        """エンドポイントの詳細調査"""
        methods_to_test = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        
        for method in methods_to_test:
            try:
                response = await self.client.request(method, url)
                
                # 成功またはAPI的なレスポンスの場合
                if (response.status_code < 500 or 
                    'application/json' in response.headers.get('content-type', '')):
                    
                    return APIEndpoint(
                        url=url,
                        method=method,
                        headers=dict(response.headers),
                        params={},
                        auth_type=self._detect_auth_type(response),
                        response_schema=self._analyze_response_schema(response),
                        rate_limit=self._detect_rate_limit(response)
                    )
            except:
                continue
        
        return None
    
    def _detect_auth_type(self, response: httpx.Response) -> str:
        """認証タイプの検出"""
        www_auth = response.headers.get('www-authenticate', '').lower()
        
        if 'bearer' in www_auth:
            return 'bearer_token'
        elif 'basic' in www_auth:
            return 'basic_auth'
        elif response.status_code == 401:
            return 'required'
        else:
            return 'none'
    
    def _analyze_response_schema(self, response: httpx.Response) -> Dict[str, Any]:
        """レスポンススキーマの分析"""
        try:
            if 'application/json' in response.headers.get('content-type', ''):
                data = response.json()
                return self._infer_schema(data)
        except:
            pass
        
        return {"type": "unknown"}
    
    def _infer_schema(self, data: Any) -> Dict[str, Any]:
        """データからスキーマを推論"""
        if isinstance(data, dict):
            schema = {"type": "object", "properties": {}}
            for key, value in data.items():
                schema["properties"][key] = self._infer_schema(value)
            return schema
        elif isinstance(data, list):
            if data:
                return {"type": "array", "items": self._infer_schema(data[0])}
            return {"type": "array", "items": {"type": "unknown"}}
        elif isinstance(data, str):
            return {"type": "string"}
        elif isinstance(data, int):
            return {"type": "integer"}
        elif isinstance(data, float):
            return {"type": "number"}
        elif isinstance(data, bool):
            return {"type": "boolean"}
        else:
            return {"type": "unknown"}
    
    def _detect_rate_limit(self, response: httpx.Response) -> Optional[Dict[str, Any]]:
        """レート制限の検出"""
        rate_limit_headers = [
            'x-ratelimit-limit',
            'x-ratelimit-remaining',
            'x-ratelimit-reset',
            'rate-limit-limit',
            'rate-limit-remaining'
        ]
        
        rate_limit_info = {}
        for header in rate_limit_headers:
            value = response.headers.get(header)
            if value:
                rate_limit_info[header] = value
        
        return rate_limit_info if rate_limit_info else None
    
    async def _analyze_auth_flow(self, base_url: str, discovery_result: Dict[str, Any]) -> Dict[str, Any]:
        """認証フローの分析"""
        auth_flow = {
            "type": "unknown",
            "endpoints": [],
            "required_fields": [],
            "flow_steps": []
        }
        
        # 認証要素から認証フローを推論
        for auth_element in discovery_result["auth_elements"]:
            if auth_element["type"] == "login_form":
                auth_flow["type"] = "form_based"
                auth_flow["endpoints"].append({
                    "url": urljoin(base_url, auth_element["action"]),
                    "method": auth_element["method"]
                })
                auth_flow["required_fields"].extend(auth_element["fields"])
            elif auth_element["type"] == "oauth_button":
                auth_flow["type"] = "oauth"
                auth_flow["endpoints"].append({
                    "url": auth_element["href"],
                    "method": "GET"
                })
        
        return auth_flow
    
    async def _analyze_capabilities(self, base_url: str, discovery_result: Dict[str, Any]) -> List[str]:
        """機能分析"""
        capabilities = []
        
        # フォームから機能を推論
        for form in discovery_result["forms"]:
            action = form["action"].lower()
            if "create" in action or "add" in action:
                capabilities.append("create")
            if "update" in action or "edit" in action:
                capabilities.append("update")
            if "delete" in action or "remove" in action:
                capabilities.append("delete")
            if "search" in action or "query" in action:
                capabilities.append("search")
        
        # API ヒントから機能を推論
        for hint in discovery_result["api_hints"]:
            url = hint["url"].lower()
            if any(keyword in url for keyword in ["inventory", "stock", "item"]):
                capabilities.append("inventory_management")
            if any(keyword in url for keyword in ["user", "account", "profile"]):
                capabilities.append("user_management")
            if any(keyword in url for keyword in ["order", "purchase", "transaction"]):
                capabilities.append("order_management")
        
        return list(set(capabilities))
    
    def _determine_protocol_type(self, discovery_result: Dict[str, Any]) -> ProtocolType:
        """プロトコルタイプの決定"""
        # API ヒントがある場合
        if discovery_result["api_hints"]:
            for hint in discovery_result["api_hints"]:
                if "graphql" in hint["url"].lower():
                    return ProtocolType.GRAPHQL
                if "api" in hint["url"].lower():
                    return ProtocolType.REST_API
        
        # フォームベースの場合
        if discovery_result["forms"]:
            return ProtocolType.FORM_SUBMISSION
        
        # デフォルトはWebスクレイピング
        return ProtocolType.WEB_SCRAPING
    
    def _generate_data_flows(self, endpoints: List[APIEndpoint], schemas: Dict[str, Any]) -> List[DataFlow]:
        """データフローの生成"""
        data_flows = []
        
        for endpoint in endpoints:
            # CRUD操作の推論
            if endpoint.method == "GET":
                data_flows.append(DataFlow(
                    source=endpoint.url,
                    target="local_storage",
                    transformation={"type": "extract"},
                    validation=endpoint.response_schema,
                    frequency="on_demand"
                ))
            elif endpoint.method in ["POST", "PUT", "PATCH"]:
                data_flows.append(DataFlow(
                    source="local_storage",
                    target=endpoint.url,
                    transformation={"type": "format"},
                    validation=endpoint.response_schema,
                    frequency="on_change"
                ))
        
        return data_flows

class MCPProtocolGenerator:
    """MCP プロトコル生成器"""
    
    def __init__(self):
        self.analyzer = ProtocolAnalyzer()
    
    async def generate_mcp_connector(self, service_url: str, service_name: str) -> str:
        """MCPコネクタの自動生成"""
        
        # 1. プロトコル分析
        protocol_spec = await self.analyzer.analyze_service(service_url, service_name)
        
        # 2. MCPコネクタコード生成
        connector_code = self._generate_connector_code(protocol_spec)
        
        return connector_code
    
    def _generate_connector_code(self, spec: ProtocolSpec) -> str:
        """コネクタコードの生成"""
        
        code_template = f'''"""
自動生成MCPコネクタ: {spec.service_name}
プロトコルタイプ: {spec.protocol_type.value}
"""

import asyncio
from typing import Dict, Any, List, Optional
from ..base import BaseMCPConnector, MCPResult
import httpx
import structlog

logger = structlog.get_logger()

class {spec.service_name.title()}Connector(BaseMCPConnector):
    """
    {spec.service_name} 自動生成コネクタ
    
    機能: {', '.join(spec.capabilities)}
    """
    
    def __init__(self):
        super().__init__()
        self.base_url = "{spec.base_url}"
        self.client = httpx.AsyncClient()
        self.auth_info = None
    
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """認証処理"""
        try:
            # 自動検出された認証フロー
            auth_flow = {json.dumps(spec.auth_flow, indent=12)}
            
            if auth_flow["type"] == "form_based":
                return await self._form_based_auth(credentials, auth_flow)
            elif auth_flow["type"] == "oauth":
                return await self._oauth_auth(credentials, auth_flow)
            else:
                return True  # 認証不要
                
        except Exception as e:
            logger.error(f"Authentication failed: {{e}}")
            return False
    
    async def _form_based_auth(self, credentials: Dict[str, Any], auth_flow: Dict[str, Any]) -> bool:
        """フォームベース認証"""
        # 実装は認証フローに基づいて自動生成
        pass
    
    async def _oauth_auth(self, credentials: Dict[str, Any], auth_flow: Dict[str, Any]) -> bool:
        """OAuth認証"""
        # 実装は認証フローに基づいて自動生成
        pass
'''

        # エンドポイント別メソッド生成
        for endpoint in spec.endpoints:
            method_name = self._generate_method_name(endpoint)
            method_code = self._generate_endpoint_method(endpoint)
            code_template += f"\n    {method_code}"
        
        code_template += '''
    
    async def execute_command(self, command: str, params: Dict[str, Any]) -> MCPResult:
        """コマンド実行"""
        try:
            if command == "list_items":
                return await self.list_items(params)
            elif command == "create_item":
                return await self.create_item(params)
            elif command == "update_item":
                return await self.update_item(params)
            elif command == "delete_item":
                return await self.delete_item(params)
            else:
                return MCPResult(
                    success=False,
                    error=f"Unknown command: {command}"
                )
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return MCPResult(
                success=False,
                error=str(e)
            )
'''
        
        return code_template
    
    def _generate_method_name(self, endpoint: APIEndpoint) -> str:
        """メソッド名の生成"""
        url_parts = endpoint.url.split('/')
        path = url_parts[-1] if url_parts else "action"
        return f"{endpoint.method.lower()}_{path}"
    
    def _generate_endpoint_method(self, endpoint: APIEndpoint) -> str:
        """エンドポイントメソッドの生成"""
        method_name = self._generate_method_name(endpoint)
        
        return f'''async def {method_name}(self, params: Dict[str, Any]) -> MCPResult:
        """自動生成メソッド: {endpoint.url}"""
        try:
            response = await self.client.request(
                "{endpoint.method}",
                "{endpoint.url}",
                json=params if "{endpoint.method}" in ["POST", "PUT", "PATCH"] else None,
                params=params if "{endpoint.method}" == "GET" else None
            )
            
            if response.status_code < 400:
                return MCPResult(
                    success=True,
                    data=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
                )
            else:
                return MCPResult(
                    success=False,
                    error=f"HTTP {{response.status_code}}: {{response.text}}"
                )
                
        except Exception as e:
            return MCPResult(
                success=False,
                error=str(e)
            )'''

# 使用例
async def analyze_zaico():
    """ZAICO分析例"""
    generator = MCPProtocolGenerator()
    
    # ZAICOを分析してコネクタを自動生成
    connector_code = await generator.generate_mcp_connector(
        "https://web.zaico.co.jp",
        "zaico"
    )
    
    print("Generated ZAICO Connector:")
    print(connector_code)

if __name__ == "__main__":
    asyncio.run(analyze_zaico())