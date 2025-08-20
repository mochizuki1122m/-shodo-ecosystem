"""
Universal Protocol Engine - 汎用自動プロトコル実行システム
ほぼ全てのSaaSで自動的にプロトコルが実行される抽象化エンジン
"""

import asyncio
import json
import re
import ast
from typing import Dict, Any, List, Optional, Callable, Union, Type
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import structlog
import importlib.util
from pathlib import Path

# AI/ML dependencies for pattern recognition
import torch
import transformers
from sklearn.cluster import KMeans
import cv2
import numpy as np
from PIL import Image
import pytesseract

logger = structlog.get_logger()

class UniversalPattern(Enum):
    """汎用パターン定義"""
    # UI パターン
    LOGIN_FORM = "login_form"
    DATA_TABLE = "data_table"
    CREATE_BUTTON = "create_button"
    EDIT_BUTTON = "edit_button"
    DELETE_BUTTON = "delete_button"
    SEARCH_BOX = "search_box"
    PAGINATION = "pagination"
    MODAL_DIALOG = "modal_dialog"
    DROPDOWN_MENU = "dropdown_menu"
    FILE_UPLOAD = "file_upload"
    
    # データパターン
    LIST_RESPONSE = "list_response"
    ITEM_RESPONSE = "item_response"
    ERROR_RESPONSE = "error_response"
    SUCCESS_RESPONSE = "success_response"
    PAGINATION_META = "pagination_meta"
    
    # 認証パターン
    TOKEN_AUTH = "token_auth"
    SESSION_AUTH = "session_auth"
    OAUTH2_AUTH = "oauth2_auth"
    API_KEY_AUTH = "api_key_auth"
    BASIC_AUTH = "basic_auth"
    
    # 操作パターン
    CRUD_OPERATIONS = "crud_operations"
    BULK_OPERATIONS = "bulk_operations"
    SEARCH_OPERATIONS = "search_operations"
    EXPORT_OPERATIONS = "export_operations"
    IMPORT_OPERATIONS = "import_operations"

@dataclass
class PatternMatch:
    """パターンマッチ結果"""
    pattern: UniversalPattern
    confidence: float  # 0.0-1.0
    location: Dict[str, Any]  # 位置情報
    attributes: Dict[str, Any]  # 属性情報
    extraction_method: str  # 抽出方法

@dataclass
class UniversalOperation:
    """汎用操作定義"""
    name: str
    pattern_requirements: List[UniversalPattern]
    execution_template: str
    parameter_mapping: Dict[str, str]
    success_indicators: List[str]
    error_indicators: List[str]

class PatternRecognitionEngine:
    """パターン認識エンジン - AI駆動でUI/データパターンを自動認識"""
    
    def __init__(self):
        self.ui_model = None  # Computer Vision model for UI recognition
        self.text_model = None  # NLP model for text pattern recognition
        self.pattern_database = {}
        self.learning_data = []
        
        # パターン認識の信頼度閾値
        self.confidence_threshold = 0.7
        
    async def initialize_models(self):
        """AI モデルの初期化"""
        try:
            # UI認識用のComputer Visionモデル
            # 実際の実装では、事前訓練されたモデルまたはカスタムモデルを使用
            self.ui_model = self._load_ui_recognition_model()
            
            # テキスト解析用のNLPモデル
            self.text_model = self._load_text_analysis_model()
            
            logger.info("Pattern recognition models initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize AI models: {e}")
            # フォールバック: ルールベースの認識
            self.ui_model = None
            self.text_model = None
    
    def _load_ui_recognition_model(self):
        """UI認識モデルの読み込み"""
        # 実装例: YOLOv5やCustom CNN for UI element detection
        # ここではモックモデルを返す
        class MockUIModel:
            def predict(self, image):
                return []  # モック結果
        return MockUIModel()
    
    def _load_text_analysis_model(self):
        """テキスト解析モデルの読み込み"""
        # 実装例: BERT, RoBERTa for text classification
        class MockTextModel:
            def analyze(self, text):
                return {"intent": "unknown", "confidence": 0.5}
        return MockTextModel()
    
    async def recognize_patterns(
        self, 
        page_content: Dict[str, Any]
    ) -> List[PatternMatch]:
        """ページコンテンツからパターンを認識"""
        
        recognized_patterns = []
        
        # 1. HTML構造解析
        html_patterns = await self._analyze_html_structure(
            page_content.get('html', '')
        )
        recognized_patterns.extend(html_patterns)
        
        # 2. CSS解析
        css_patterns = await self._analyze_css_structure(
            page_content.get('css', '')
        )
        recognized_patterns.extend(css_patterns)
        
        # 3. JavaScript解析
        js_patterns = await self._analyze_javascript_behavior(
            page_content.get('javascript', '')
        )
        recognized_patterns.extend(js_patterns)
        
        # 4. 視覚的パターン認識（スクリーンショットがある場合）
        if 'screenshot' in page_content:
            visual_patterns = await self._analyze_visual_patterns(
                page_content['screenshot']
            )
            recognized_patterns.extend(visual_patterns)
        
        # 5. ネットワークトラフィック解析
        if 'network_requests' in page_content:
            network_patterns = await self._analyze_network_patterns(
                page_content['network_requests']
            )
            recognized_patterns.extend(network_patterns)
        
        # 6. パターンの統合・重複除去
        unified_patterns = self._unify_patterns(recognized_patterns)
        
        return unified_patterns
    
    async def _analyze_html_structure(self, html: str) -> List[PatternMatch]:
        """HTML構造の解析"""
        patterns = []
        
        if not html:
            return patterns
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # ログインフォームの検出
            login_forms = soup.find_all('form')
            for form in login_forms:
                # パスワードフィールドがあるかチェック
                if form.find('input', {'type': 'password'}):
                    patterns.append(PatternMatch(
                        pattern=UniversalPattern.LOGIN_FORM,
                        confidence=0.9,
                        location={'selector': self._get_css_selector(form)},
                        attributes={
                            'action': form.get('action', ''),
                            'method': form.get('method', 'POST'),
                            'fields': [inp.get('name') for inp in form.find_all('input')]
                        },
                        extraction_method='html_parsing'
                    ))
            
            # データテーブルの検出
            tables = soup.find_all('table')
            for table in tables:
                # ヘッダー行があるかチェック
                if table.find('thead') or table.find('th'):
                    patterns.append(PatternMatch(
                        pattern=UniversalPattern.DATA_TABLE,
                        confidence=0.8,
                        location={'selector': self._get_css_selector(table)},
                        attributes={
                            'headers': [th.get_text(strip=True) for th in table.find_all('th')],
                            'row_count': len(table.find_all('tr'))
                        },
                        extraction_method='html_parsing'
                    ))
            
            # ボタンの検出
            buttons = soup.find_all(['button', 'input[type="submit"]', 'input[type="button"]'])
            for button in buttons:
                button_text = button.get_text(strip=True).lower()
                button_type = self._classify_button_type(button_text)
                
                if button_type:
                    patterns.append(PatternMatch(
                        pattern=button_type,
                        confidence=0.7,
                        location={'selector': self._get_css_selector(button)},
                        attributes={
                            'text': button.get_text(strip=True),
                            'type': button.get('type', ''),
                            'onclick': button.get('onclick', '')
                        },
                        extraction_method='html_parsing'
                    ))
            
            # 検索ボックスの検出
            search_inputs = soup.find_all('input', {'type': 'search'})
            search_inputs.extend(soup.find_all('input', {'placeholder': re.compile(r'search|検索', re.I)}))
            
            for search_input in search_inputs:
                patterns.append(PatternMatch(
                    pattern=UniversalPattern.SEARCH_BOX,
                    confidence=0.8,
                    location={'selector': self._get_css_selector(search_input)},
                    attributes={
                        'placeholder': search_input.get('placeholder', ''),
                        'name': search_input.get('name', '')
                    },
                    extraction_method='html_parsing'
                ))
            
        except Exception as e:
            logger.warning(f"HTML analysis failed: {e}")
        
        return patterns
    
    def _classify_button_type(self, button_text: str) -> Optional[UniversalPattern]:
        """ボタンテキストからタイプを分類"""
        
        button_text = button_text.lower()
        
        if any(word in button_text for word in ['create', 'add', 'new', '作成', '追加', '新規']):
            return UniversalPattern.CREATE_BUTTON
        elif any(word in button_text for word in ['edit', 'modify', 'update', '編集', '修正', '更新']):
            return UniversalPattern.EDIT_BUTTON
        elif any(word in button_text for word in ['delete', 'remove', 'del', '削除', '除去']):
            return UniversalPattern.DELETE_BUTTON
        
        return None
    
    def _get_css_selector(self, element) -> str:
        """要素のCSSセレクタを生成"""
        # 簡易実装：実際はより複雑なセレクタ生成が必要
        if element.get('id'):
            return f"#{element['id']}"
        elif element.get('class'):
            classes = ' '.join(element['class']) if isinstance(element['class'], list) else element['class']
            return f".{classes.replace(' ', '.')}"
        else:
            return element.name
    
    async def _analyze_network_patterns(self, network_requests: List[Dict]) -> List[PatternMatch]:
        """ネットワークリクエストパターンの解析"""
        patterns = []
        
        for request in network_requests:
            url = request.get('url', '')
            method = request.get('method', 'GET')
            response = request.get('response', {})
            
            # API エンドポイントの分類
            if '/api/' in url or url.endswith('.json'):
                # CRUD操作の推定
                if method == 'GET' and ('list' in url or 'items' in url):
                    patterns.append(PatternMatch(
                        pattern=UniversalPattern.LIST_RESPONSE,
                        confidence=0.8,
                        location={'url': url, 'method': method},
                        attributes={
                            'endpoint': url,
                            'response_structure': self._analyze_response_structure(response)
                        },
                        extraction_method='network_analysis'
                    ))
                elif method == 'POST':
                    patterns.append(PatternMatch(
                        pattern=UniversalPattern.CRUD_OPERATIONS,
                        confidence=0.7,
                        location={'url': url, 'method': method},
                        attributes={'operation': 'create', 'endpoint': url},
                        extraction_method='network_analysis'
                    ))
        
        return patterns
    
    def _analyze_response_structure(self, response: Dict) -> Dict[str, Any]:
        """レスポンス構造の解析"""
        structure = {
            'type': 'unknown',
            'fields': [],
            'pagination': False,
            'nested_objects': False
        }
        
        if isinstance(response, dict):
            structure['fields'] = list(response.keys())
            
            # ページネーション検出
            if any(key in response for key in ['page', 'limit', 'total', 'next', 'prev']):
                structure['pagination'] = True
            
            # ネストしたオブジェクト検出
            if any(isinstance(v, (dict, list)) for v in response.values()):
                structure['nested_objects'] = True
        
        return structure
    
    def _unify_patterns(self, patterns: List[PatternMatch]) -> List[PatternMatch]:
        """パターンの統合・重複除去"""
        
        # 同じパターンタイプで信頼度の高いものを選択
        unified = {}
        
        for pattern in patterns:
            key = pattern.pattern
            if key not in unified or pattern.confidence > unified[key].confidence:
                unified[key] = pattern
        
        return list(unified.values())

class UniversalProtocolGenerator:
    """汎用プロトコル生成器 - 認識されたパターンから実行可能プロトコルを生成"""
    
    def __init__(self):
        self.pattern_engine = PatternRecognitionEngine()
        self.operation_templates = {}
        self._initialize_operation_templates()
    
    def _initialize_operation_templates(self):
        """操作テンプレートの初期化"""
        
        # CRUD操作テンプレート
        self.operation_templates['create_item'] = UniversalOperation(
            name='create_item',
            pattern_requirements=[UniversalPattern.CREATE_BUTTON, UniversalPattern.LOGIN_FORM],
            execution_template='''
async def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
    # 1. 認証確認
    if not await self.ensure_authenticated():
        return {"success": False, "error": "Authentication required"}
    
    # 2. 作成ボタンの検索・クリック
    create_button = await self.find_element("{create_button_selector}")
    if create_button:
        await create_button.click()
    
    # 3. フォーム入力
    await self.fill_form(data, "{form_selector}")
    
    # 4. 送信
    submit_button = await self.find_element("{submit_selector}")
    await submit_button.click()
    
    # 5. 結果確認
    return await self.verify_operation_result("create")
            ''',
            parameter_mapping={
                'create_button_selector': 'CREATE_BUTTON.location.selector',
                'form_selector': 'MODAL_DIALOG.location.selector or LOGIN_FORM.location.selector',
                'submit_selector': 'button[type="submit"]'
            },
            success_indicators=['success', 'created', 'added', '作成', '追加'],
            error_indicators=['error', 'failed', 'invalid', 'エラー', '失敗']
        )
        
        self.operation_templates['list_items'] = UniversalOperation(
            name='list_items',
            pattern_requirements=[UniversalPattern.DATA_TABLE],
            execution_template='''
async def list_items(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
    # 1. 認証確認
    if not await self.ensure_authenticated():
        return {"success": False, "error": "Authentication required"}
    
    # 2. 検索フィルタ適用（ある場合）
    if filters and await self.find_element("{search_selector}"):
        await self.apply_search_filters(filters)
    
    # 3. テーブルデータ抽出
    table_data = await self.extract_table_data("{table_selector}")
    
    return {"success": True, "data": table_data}
            ''',
            parameter_mapping={
                'table_selector': 'DATA_TABLE.location.selector',
                'search_selector': 'SEARCH_BOX.location.selector'
            },
            success_indicators=['data', 'items', 'results'],
            error_indicators=['no data', 'empty', 'error']
        )
        
        # 他の操作テンプレートも同様に定義...
    
    async def generate_protocol(
        self, 
        service_name: str,
        recognized_patterns: List[PatternMatch]
    ) -> str:
        """認識されたパターンから汎用プロトコルを生成"""
        
        logger.info(f"Generating universal protocol for {service_name}")
        
        # 1. 利用可能な操作の特定
        available_operations = self._identify_available_operations(recognized_patterns)
        
        # 2. プロトコルクラスの生成
        protocol_code = self._generate_protocol_class(
            service_name, available_operations, recognized_patterns
        )
        
        return protocol_code
    
    def _identify_available_operations(
        self, 
        patterns: List[PatternMatch]
    ) -> List[UniversalOperation]:
        """パターンから利用可能な操作を特定"""
        
        available_operations = []
        pattern_types = {p.pattern for p in patterns}
        
        for operation in self.operation_templates.values():
            # 必要なパターンが全て揃っているかチェック
            required_patterns = set(operation.pattern_requirements)
            if required_patterns.issubset(pattern_types):
                available_operations.append(operation)
        
        return available_operations
    
    def _generate_protocol_class(
        self,
        service_name: str,
        operations: List[UniversalOperation],
        patterns: List[PatternMatch]
    ) -> str:
        """プロトコルクラスのコード生成"""
        
        # パターン情報をマッピングに変換
        pattern_mapping = {p.pattern: p for p in patterns}
        
        code_parts = [
            f"# Universal Protocol for {service_name}",
            "import asyncio",
            "from typing import Dict, Any, Optional",
            "from playwright.async_api import Page, Browser",
            "",
            f"class {service_name.title()}UniversalProtocol:",
            "    def __init__(self, page: Page):",
            "        self.page = page",
            "        self.authenticated = False",
            "        self.patterns = {}",
            ""
        ]
        
        # パターン情報の埋め込み
        code_parts.append("    def _initialize_patterns(self):")
        for pattern in patterns:
            code_parts.append(f"        self.patterns['{pattern.pattern.value}'] = {pattern.location}")
        code_parts.append("")
        
        # 基本メソッドの追加
        code_parts.extend([
            "    async def ensure_authenticated(self) -> bool:",
            "        if not self.authenticated:",
            "            return await self.authenticate()",
            "        return True",
            "",
            "    async def authenticate(self) -> bool:",
            "        # 汎用認証ロジック",
            "        login_form = self.patterns.get('login_form')",
            "        if login_form:",
            "            # ログインフォームを使用した認証",
            "            return await self._form_based_auth(login_form)",
            "        return False",
            "",
            "    async def find_element(self, selector: str):",
            "        try:",
            "            return await self.page.wait_for_selector(selector, timeout=5000)",
            "        except:",
            "            return None",
            "",
            "    async def extract_table_data(self, table_selector: str) -> List[Dict]:",
            "        # 汎用テーブルデータ抽出",
            "        rows = await self.page.query_selector_all(f'{table_selector} tr')",
            "        data = []",
            "        # 実装詳細...",
            "        return data",
            ""
        ])
        
        # 操作メソッドの生成
        for operation in operations:
            # テンプレートのパラメータを実際の値に置換
            method_code = self._substitute_template_parameters(
                operation.execution_template,
                operation.parameter_mapping,
                pattern_mapping
            )
            
            code_parts.extend(method_code.split('\n'))
            code_parts.append("")
        
        return '\n'.join(code_parts)
    
    def _substitute_template_parameters(
        self,
        template: str,
        parameter_mapping: Dict[str, str],
        pattern_mapping: Dict[UniversalPattern, PatternMatch]
    ) -> str:
        """テンプレートパラメータの置換"""
        
        result = template
        
        for param_name, param_path in parameter_mapping.items():
            # パラメータパスを評価して実際の値を取得
            try:
                value = self._evaluate_parameter_path(param_path, pattern_mapping)
                result = result.replace(f"{{{param_name}}}", str(value))
            except Exception as e:
                logger.warning(f"Failed to substitute parameter {param_name}: {e}")
                result = result.replace(f"{{{param_name}}}", "unknown")
        
        return result
    
    def _evaluate_parameter_path(
        self,
        path: str,
        pattern_mapping: Dict[UniversalPattern, PatternMatch]
    ) -> Any:
        """パラメータパスの評価"""
        
        # 例: "CREATE_BUTTON.location.selector" -> pattern_mapping[CREATE_BUTTON].location['selector']
        
        parts = path.split('.')
        if len(parts) >= 2:
            pattern_name = parts[0]
            
            # パターン名をEnumに変換
            try:
                pattern_enum = UniversalPattern(pattern_name.lower())
                if pattern_enum in pattern_mapping:
                    obj = pattern_mapping[pattern_enum]
                    
                    # 残りのパスを評価
                    for part in parts[1:]:
                        if hasattr(obj, part):
                            obj = getattr(obj, part)
                        elif isinstance(obj, dict) and part in obj:
                            obj = obj[part]
                        else:
                            return "unknown"
                    
                    return obj
            except:
                pass
        
        return "unknown"

class UniversalProtocolEngine:
    """汎用プロトコル実行エンジン - 自動生成されたプロトコルを実行"""
    
    def __init__(self):
        self.pattern_engine = PatternRecognitionEngine()
        self.protocol_generator = UniversalProtocolGenerator()
        self.active_protocols: Dict[str, Any] = {}
        self.browser_pool = None
    
    async def initialize(self):
        """エンジンの初期化"""
        await self.pattern_engine.initialize_models()
        
        # ブラウザプールの初期化
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
    
    async def auto_connect_service(
        self,
        service_url: str,
        service_name: str,
        credentials: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """サービスへの自動接続・プロトコル生成・実行"""
        
        logger.info(f"Auto-connecting to {service_name} at {service_url}")
        
        try:
            # 1. ページ分析
            page_content = await self._analyze_page(service_url)
            
            # 2. パターン認識
            recognized_patterns = await self.pattern_engine.recognize_patterns(page_content)
            
            if not recognized_patterns:
                return {
                    "success": False,
                    "error": "No recognizable patterns found",
                    "service_name": service_name
                }
            
            # 3. プロトコル生成
            protocol_code = await self.protocol_generator.generate_protocol(
                service_name, recognized_patterns
            )
            
            # 4. プロトコル実行環境の作成
            protocol_instance = await self._instantiate_protocol(
                service_name, protocol_code, service_url
            )
            
            # 5. 認証（認証情報がある場合）
            if credentials:
                auth_result = await protocol_instance.authenticate()
                if not auth_result:
                    return {
                        "success": False,
                        "error": "Authentication failed",
                        "service_name": service_name
                    }
            
            # 6. 利用可能操作の取得
            available_operations = self._extract_available_operations(protocol_instance)
            
            # 7. プロトコル登録
            self.active_protocols[service_name] = protocol_instance
            
            logger.info(f"Successfully connected to {service_name}")
            
            return {
                "success": True,
                "service_name": service_name,
                "recognized_patterns": [p.pattern.value for p in recognized_patterns],
                "available_operations": available_operations,
                "protocol_generated": True,
                "authentication_required": bool(credentials)
            }
            
        except Exception as e:
            logger.error(f"Auto-connection failed for {service_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "service_name": service_name
            }
    
    async def _analyze_page(self, url: str) -> Dict[str, Any]:
        """ページの包括的分析"""
        
        context = await self.browser.new_context()
        page = await context.new_page()
        
        try:
            # ページロード
            await page.goto(url, wait_until='networkidle')
            
            # コンテンツ取得
            content = {
                'html': await page.content(),
                'url': url,
                'title': await page.title()
            }
            
            # スクリーンショット取得
            screenshot = await page.screenshot()
            content['screenshot'] = screenshot
            
            # ネットワークリクエスト監視（簡易版）
            # 実際の実装では、より詳細なネットワーク分析が必要
            
            return content
            
        finally:
            await context.close()
    
    async def _instantiate_protocol(
        self, 
        service_name: str, 
        protocol_code: str,
        service_url: str
    ) -> Any:
        """プロトコルの動的インスタンス化"""
        
        # 新しいブラウザコンテキストとページを作成
        context = await self.browser.new_context()
        page = await context.new_page()
        await page.goto(service_url)
        
        # プロトコルコードの実行
        module_name = f"universal_protocol_{service_name}"
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        module = importlib.util.module_from_spec(spec)
        
        # Playwrightをモジュールに注入
        module.Page = page.__class__
        exec(protocol_code, module.__dict__)
        
        # プロトコルクラスのインスタンス化
        protocol_class_name = f"{service_name.title()}UniversalProtocol"
        protocol_class = getattr(module, protocol_class_name)
        
        return protocol_class(page)
    
    def _extract_available_operations(self, protocol_instance: Any) -> List[str]:
        """プロトコルインスタンスから利用可能操作を抽出"""
        
        operations = []
        for attr_name in dir(protocol_instance):
            if (not attr_name.startswith('_') and 
                callable(getattr(protocol_instance, attr_name)) and
                attr_name not in ['authenticate', 'ensure_authenticated', 'find_element']):
                operations.append(attr_name)
        
        return operations
    
    async def execute_operation(
        self,
        service_name: str,
        operation: str,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """汎用操作の実行"""
        
        if service_name not in self.active_protocols:
            return {
                "success": False,
                "error": f"No active protocol for service: {service_name}"
            }
        
        protocol = self.active_protocols[service_name]
        
        try:
            if hasattr(protocol, operation):
                method = getattr(protocol, operation)
                
                if parameters:
                    result = await method(**parameters)
                else:
                    result = await method()
                
                return result
            else:
                return {
                    "success": False,
                    "error": f"Operation {operation} not available"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Operation execution failed: {str(e)}"
            }

# 使用例とデモ
async def demonstrate_universal_protocol():
    """汎用プロトコルエンジンのデモンストレーション"""
    
    print("🚀 Universal Protocol Engine - Auto SaaS Connection Demo")
    print("=" * 70)
    
    engine = UniversalProtocolEngine()
    await engine.initialize()
    
    # 複数のSaaSに自動接続
    services_to_test = [
        {"url": "https://web.zaico.co.jp", "name": "zaico"},
        {"url": "https://app.notion.so", "name": "notion"},
        {"url": "https://trello.com", "name": "trello"},
        {"url": "https://airtable.com", "name": "airtable"}
    ]
    
    for service in services_to_test:
        print(f"\n📋 Auto-connecting to {service['name']}...")
        
        result = await engine.auto_connect_service(
            service_url=service['url'],
            service_name=service['name']
        )
        
        if result['success']:
            print(f"✅ {service['name']} connected successfully!")
            print(f"   - Patterns: {result['recognized_patterns']}")
            print(f"   - Operations: {result['available_operations']}")
            
            # 操作テスト
            if 'list_items' in result['available_operations']:
                list_result = await engine.execute_operation(
                    service['name'], 'list_items'
                )
                print(f"   - List test: {'✅' if list_result.get('success') else '❌'}")
        else:
            print(f"❌ {service['name']} connection failed: {result['error']}")
    
    print(f"\n🎯 Universal Protocol Engine Results:")
    print(f"   - Services analyzed: {len(services_to_test)}")
    print(f"   - Successful connections: {len(engine.active_protocols)}")
    print(f"   - Auto-generated protocols: {len(engine.active_protocols)}")

if __name__ == "__main__":
    asyncio.run(demonstrate_universal_protocol())