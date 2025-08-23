"""
Perfect Execution Engine - 完璧な実行エンジン
マルチブラウザ、フォールバック、監視を統合した究極の実行システム
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime

import psutil
import httpx

from .perfect_mcp_engine import MCPOperationResult, MCPConnectionStrategy

# Browser automation
from playwright.async_api import async_playwright, Browser, Page, TimeoutError

# Monitoring and metrics


logger = structlog.get_logger()

class ExecutionStatus(Enum):
    """実行ステータス"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class BrowserEngine(Enum):
    """ブラウザエンジン"""
    PLAYWRIGHT_CHROMIUM = "playwright_chromium"
    PLAYWRIGHT_FIREFOX = "playwright_firefox"
    PLAYWRIGHT_WEBKIT = "playwright_webkit"
    SELENIUM_CHROME = "selenium_chrome"
    SELENIUM_FIREFOX = "selenium_firefox"
    SELENIUM_EDGE = "selenium_edge"

@dataclass
class ExecutionContext:
    """実行コンテキスト"""
    operation_id: str
    service_name: str
    operation_type: str
    parameters: Dict[str, Any]
    user_context: Dict[str, Any]
    execution_config: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    
    # 実行状態
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_strategy: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    
    # 結果
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0
    
    # 監視データ
    metrics: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)

class PerfectBrowserManager:
    """完璧なブラウザマネージャー"""
    
    def __init__(self):
        self.browser_pool: Dict[BrowserEngine, List[Browser]] = {}
        self.active_contexts: Dict[str, BrowserContext] = {}
        self.active_pages: Dict[str, Page] = {}
        self.pool_sizes = {
            BrowserEngine.PLAYWRIGHT_CHROMIUM: 3,
            BrowserEngine.PLAYWRIGHT_FIREFOX: 2,
            BrowserEngine.SELENIUM_CHROME: 2
        }
        self.initialization_lock = asyncio.Lock()
        
    async def initialize_browser_pool(self):
        """ブラウザプールの初期化"""
        
        async with self.initialization_lock:
            if self.browser_pool:
                return  # 既に初期化済み
            
            logger.info("Initializing browser pool")
            
            # Playwright browsers
            self.playwright = await async_playwright().start()
            
            for engine in [BrowserEngine.PLAYWRIGHT_CHROMIUM, BrowserEngine.PLAYWRIGHT_FIREFOX, BrowserEngine.PLAYWRIGHT_WEBKIT]:
                self.browser_pool[engine] = []
                pool_size = self.pool_sizes.get(engine, 1)
                
                for _ in range(pool_size):
                    try:
                        browser = await self._create_browser(engine)
                        if browser:
                            self.browser_pool[engine].append(browser)
                    except Exception as e:
                        logger.warning(f"Failed to create browser {engine.value}: {e}")
            
            logger.info(f"Browser pool initialized with {sum(len(browsers) for browsers in self.browser_pool.values())} browsers")
    
    async def _create_browser(self, engine: BrowserEngine) -> Optional[Browser]:
        """ブラウザの作成"""
        
        try:
            if engine == BrowserEngine.PLAYWRIGHT_CHROMIUM:
                return await self.playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-extensions',
                        '--disable-default-apps',
                        '--disable-background-timer-throttling',
                        '--disable-renderer-backgrounding',
                        '--disable-backgrounding-occluded-windows'
                    ]
                )
            elif engine == BrowserEngine.PLAYWRIGHT_FIREFOX:
                return await self.playwright.firefox.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
            elif engine == BrowserEngine.PLAYWRIGHT_WEBKIT:
                return await self.playwright.webkit.launch(
                    headless=True
                )
        except Exception as e:
            logger.error(f"Failed to create browser {engine.value}: {e}")
            return None
    
    async def acquire_browser_context(
        self, 
        engine: BrowserEngine = BrowserEngine.PLAYWRIGHT_CHROMIUM,
        stealth: bool = True
    ) -> Optional[BrowserContext]:
        """ブラウザコンテキストの取得"""
        
        if engine not in self.browser_pool or not self.browser_pool[engine]:
            logger.warning(f"No available browsers for engine {engine.value}")
            return None
        
        browser = self.browser_pool[engine][0]  # ラウンドロビンは後で実装
        
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'locale': 'ja-JP',
            'timezone_id': 'Asia/Tokyo'
        }
        
        if stealth:
            # ステルス設定の追加
            context_options.update({
                'java_script_enabled': True,
                'accept_downloads': False,
                'ignore_https_errors': False
            })
        
        try:
            context = await browser.new_context(**context_options)
            
            if stealth:
                await self._apply_stealth_techniques(context)
            
            context_id = str(uuid.uuid4())
            self.active_contexts[context_id] = context
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to create browser context: {e}")
            return None
    
    async def _apply_stealth_techniques(self, context: BrowserContext):
        """ステルス技術の適用"""
        
        # JavaScript injection for stealth
        stealth_script = """
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        
        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // Mock languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ja-JP', 'ja', 'en-US', 'en'],
        });
        
        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Mock chrome runtime
        window.chrome = {
            runtime: {},
        };
        """
        
        await context.add_init_script(stealth_script)
    
    async def acquire_page(self, context: BrowserContext) -> Optional[Page]:
        """ページの取得"""
        
        try:
            page = await context.new_page()
            
            # ページレベルの設定
            await page.set_extra_http_headers({
                'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # ページイベントリスナー
            page.on('response', self._handle_page_response)
            page.on('request', self._handle_page_request)
            page.on('console', self._handle_console_message)
            
            page_id = str(uuid.uuid4())
            self.active_pages[page_id] = page
            
            return page
            
        except Exception as e:
            logger.error(f"Failed to create page: {e}")
            return None
    
    async def _handle_page_response(self, response):
        """ページレスポンスの処理"""
        logger.debug(f"Response: {response.status} {response.url}")
    
    async def _handle_page_request(self, request):
        """ページリクエストの処理"""
        logger.debug(f"Request: {request.method} {request.url}")
    
    async def _handle_console_message(self, msg):
        """コンソールメッセージの処理"""
        if msg.type in ['error', 'warning']:
            logger.warning(f"Browser console {msg.type}: {msg.text}")

class PerfectExecutionEngine:
    """完璧な実行エンジン"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.browser_manager = PerfectBrowserManager()
        self.execution_queue = asyncio.Queue()
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.execution_workers = []
        self.monitoring_enabled = True
        
        # メトリクス
        self.metrics = {
            'operations_total': Counter('mcp_operations_total', 'Total MCP operations', ['service', 'operation', 'status']),
            'operation_duration': Histogram('mcp_operation_duration_seconds', 'Operation duration', ['service', 'operation']),
            'active_operations': Gauge('mcp_active_operations', 'Currently active operations'),
            'browser_pool_size': Gauge('mcp_browser_pool_size', 'Browser pool size', ['engine']),
            'success_rate': Summary('mcp_success_rate', 'Operation success rate', ['service'])
        }
        
    async def initialize(self, worker_count: int = 5):
        """実行エンジンの初期化"""
        
        logger.info("Initializing Perfect Execution Engine")
        
        # ブラウザプールの初期化
        await self.browser_manager.initialize_browser_pool()
        
        # ワーカーの起動
        for i in range(worker_count):
            worker = asyncio.create_task(self._execution_worker(f"worker-{i}"))
            self.execution_workers.append(worker)
        
        # 監視タスクの起動
        if self.monitoring_enabled:
            asyncio.create_task(self._monitoring_worker())
        
        logger.info(f"Execution engine initialized with {worker_count} workers")
    
    async def execute_operation(
        self,
        service_name: str,
        operation_type: str,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any] = None,
        execution_config: Dict[str, Any] = None
    ) -> MCPOperationResult:
        """操作の実行"""
        
        operation_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 実行コンテキストの作成
        context = ExecutionContext(
            operation_id=operation_id,
            service_name=service_name,
            operation_type=operation_type,
            parameters=parameters or {},
            user_context=user_context or {},
            execution_config=execution_config or {}
        )
        
        # メトリクス更新
        self.metrics['active_operations'].inc()
        
        try:
            # 実行キューに追加
            await self.execution_queue.put(context)
            
            # 実行完了を待機
            while context.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING, ExecutionStatus.RETRYING]:
                await asyncio.sleep(0.1)
                
                # タイムアウトチェック
                if time.time() - start_time > context.execution_config.get('timeout_ms', 30000) / 1000:
                    context.status = ExecutionStatus.TIMEOUT
                    context.error = "Operation timeout"
                    break
            
            # 結果の作成
            execution_time = (time.time() - start_time) * 1000
            
            result = MCPOperationResult(
                success=context.status == ExecutionStatus.SUCCESS,
                operation_id=operation_id,
                service_name=service_name,
                operation_type=operation_type,
                data=context.result,
                error=context.error,
                execution_time_ms=execution_time,
                strategy_used=MCPConnectionStrategy(context.current_strategy) if context.current_strategy else None,
                confidence_score=context.metrics.get('confidence_score', 0.0),
                metadata=context.metrics
            )
            
            # メトリクス記録
            self._record_operation_metrics(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Operation execution failed: {e}")
            
            return MCPOperationResult(
                success=False,
                operation_id=operation_id,
                service_name=service_name,
                operation_type=operation_type,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
        finally:
            self.metrics['active_operations'].dec()
            if operation_id in self.active_executions:
                del self.active_executions[operation_id]
    
    async def _execution_worker(self, worker_id: str):
        """実行ワーカー"""
        
        logger.info(f"Execution worker {worker_id} started")
        
        while True:
            try:
                # キューから実行コンテキストを取得
                context = await self.execution_queue.get()
                
                if context is None:  # 終了シグナル
                    break
                
                context.status = ExecutionStatus.RUNNING
                self.active_executions[context.operation_id] = context
                
                # 操作の実行
                await self._execute_operation_with_fallback(context)
                
                # キュータスクの完了
                self.execution_queue.task_done()
                
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)  # エラー時の短い待機
    
    async def _execute_operation_with_fallback(self, context: ExecutionContext):
        """フォールバック付き操作実行"""
        
        strategies = [
            "official_api",
            "browser_automation", 
            "form_submission",
            "screen_scraping"
        ]
        
        for strategy in strategies:
            if context.attempt_count >= context.max_attempts:
                context.status = ExecutionStatus.FAILED
                context.error = "Max attempts exceeded"
                break
            
            context.attempt_count += 1
            context.current_strategy = strategy
            context.status = ExecutionStatus.RUNNING if context.attempt_count == 1 else ExecutionStatus.RETRYING
            
            try:
                # 戦略別実行
                result = await self._execute_with_strategy(context, strategy)
                
                if result.get("success", False):
                    context.status = ExecutionStatus.SUCCESS
                    context.result = result.get("data")
                    context.metrics.update(result.get("metrics", {}))
                    break
                else:
                    context.error = result.get("error", f"Strategy {strategy} failed")
                    logger.warning(f"Strategy {strategy} failed for {context.operation_id}: {context.error}")
                    
                    # 次の戦略まで待機
                    if context.attempt_count < context.max_attempts:
                        await asyncio.sleep(2 ** context.attempt_count)  # 指数バックオフ
                    
            except Exception as e:
                context.error = str(e)
                logger.error(f"Strategy {strategy} exception for {context.operation_id}: {e}")
        
        if context.status not in [ExecutionStatus.SUCCESS]:
            context.status = ExecutionStatus.FAILED
    
    async def _execute_with_strategy(
        self, 
        context: ExecutionContext, 
        strategy: str
    ) -> Dict[str, Any]:
        """戦略別実行"""
        
        if strategy == "official_api":
            return await self._execute_official_api(context)
        elif strategy == "browser_automation":
            return await self._execute_browser_automation(context)
        elif strategy == "form_submission":
            return await self._execute_form_submission(context)
        elif strategy == "screen_scraping":
            return await self._execute_screen_scraping(context)
        else:
            return {"success": False, "error": f"Unknown strategy: {strategy}"}
    
    async def _execute_official_api(self, context: ExecutionContext) -> Dict[str, Any]:
        """公式API実行"""
        
        # サービス固有のAPI設定を取得
        api_config = await self._get_api_config(context.service_name)
        
        if not api_config:
            return {"success": False, "error": "No API configuration found"}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                
                # 認証ヘッダーの設定
                headers = {"Content-Type": "application/json"}
                if api_config.get("auth_type") == "bearer":
                    token = context.user_context.get("api_token")
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                
                # 操作タイプに基づくAPI呼び出し
                if context.operation_type == "list_items":
                    response = await client.get(
                        f"{api_config['base_url']}/items",
                        headers=headers,
                        params=context.parameters
                    )
                elif context.operation_type == "create_item":
                    response = await client.post(
                        f"{api_config['base_url']}/items",
                        headers=headers,
                        json=context.parameters
                    )
                elif context.operation_type == "update_item":
                    item_id = context.parameters.get("id")
                    response = await client.put(
                        f"{api_config['base_url']}/items/{item_id}",
                        headers=headers,
                        json=context.parameters
                    )
                elif context.operation_type == "delete_item":
                    item_id = context.parameters.get("id")
                    response = await client.delete(
                        f"{api_config['base_url']}/items/{item_id}",
                        headers=headers
                    )
                else:
                    return {"success": False, "error": f"Unsupported operation: {context.operation_type}"}
                
                if response.status_code < 400:
                    try:
                        data = response.json()
                    except:
                        data = response.text
                    
                    return {
                        "success": True,
                        "data": data,
                        "metrics": {
                            "response_time_ms": response.elapsed.total_seconds() * 1000,
                            "status_code": response.status_code,
                            "confidence_score": 0.95
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code} {response.text}",
                        "metrics": {"status_code": response.status_code}
                    }
                    
        except Exception as e:
            return {"success": False, "error": f"API execution failed: {str(e)}"}
    
    async def _execute_browser_automation(self, context: ExecutionContext) -> Dict[str, Any]:
        """ブラウザ自動化実行"""
        
        browser_context = await self.browser_manager.acquire_browser_context()
        if not browser_context:
            return {"success": False, "error": "Failed to acquire browser context"}
        
        try:
            page = await self.browser_manager.acquire_page(browser_context)
            if not page:
                return {"success": False, "error": "Failed to acquire page"}
            
            # サービスページへの移動
            service_url = await self._get_service_url(context.service_name)
            await page.goto(service_url, wait_until='networkidle')
            
            # 認証の実行
            auth_result = await self._perform_browser_authentication(page, context)
            if not auth_result.get("success", False):
                return {"success": False, "error": "Authentication failed"}
            
            # 操作の実行
            operation_result = await self._perform_browser_operation(page, context)
            
            return operation_result
            
        except Exception as e:
            return {"success": False, "error": f"Browser automation failed: {str(e)}"}
        finally:
            try:
                await browser_context.close()
            except:
                pass
    
    async def _perform_browser_authentication(
        self, 
        page: Page, 
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """ブラウザ認証の実行"""
        
        credentials = context.user_context.get("credentials", {})
        if not credentials:
            return {"success": True}  # 認証不要
        
        try:
            # ログインフォームの検索
            login_form = await page.wait_for_selector('form', timeout=5000)
            if not login_form:
                return {"success": False, "error": "Login form not found"}
            
            # ユーザー名入力
            username_field = await page.query_selector('input[type="email"], input[type="text"], input[name*="user"], input[name*="email"]')
            if username_field and credentials.get("username"):
                await username_field.fill(credentials["username"])
                await asyncio.sleep(0.5)  # 人間らしい遅延
            
            # パスワード入力
            password_field = await page.query_selector('input[type="password"]')
            if password_field and credentials.get("password"):
                await password_field.fill(credentials["password"])
                await asyncio.sleep(0.5)
            
            # ログインボタンのクリック
            login_button = await page.query_selector('button[type="submit"], input[type="submit"], button:has-text("ログイン"), button:has-text("Login")')
            if login_button:
                await login_button.click()
                
                # ページ遷移の待機
                try:
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                    # ログイン成功の確認
                    current_url = page.url
                    if 'login' not in current_url.lower() and 'signin' not in current_url.lower():
                        return {"success": True}
                    
                except TimeoutError:
                    pass
            
            # エラーメッセージの確認
            error_elements = await page.query_selector_all('.error, .alert, [class*="error"], [class*="alert"]')
            if error_elements:
                error_text = await error_elements[0].text_content()
                return {"success": False, "error": f"Authentication error: {error_text}"}
            
            return {"success": False, "error": "Authentication result unclear"}
            
        except Exception as e:
            return {"success": False, "error": f"Authentication failed: {str(e)}"}
    
    async def _perform_browser_operation(
        self, 
        page: Page, 
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """ブラウザ操作の実行"""
        
        operation_type = context.operation_type
        parameters = context.parameters
        
        try:
            if operation_type == "list_items":
                return await self._browser_list_items(page, parameters)
            elif operation_type == "create_item":
                return await self._browser_create_item(page, parameters)
            elif operation_type == "update_item":
                return await self._browser_update_item(page, parameters)
            elif operation_type == "delete_item":
                return await self._browser_delete_item(page, parameters)
            elif operation_type == "search":
                return await self._browser_search(page, parameters)
            else:
                return {"success": False, "error": f"Unsupported operation: {operation_type}"}
                
        except Exception as e:
            return {"success": False, "error": f"Browser operation failed: {str(e)}"}
    
    async def _browser_list_items(self, page: Page, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """ブラウザでのアイテム一覧取得"""
        
        try:
            # テーブルまたはリストの検索
            table = await page.query_selector('table, [class*="table"], [class*="list"], [class*="grid"]')
            
            if table:
                # テーブルデータの抽出
                rows = await table.query_selector_all('tr, [class*="row"], [class*="item"]')
                
                items = []
                for row in rows[1:]:  # ヘッダー行をスキップ
                    cells = await row.query_selector_all('td, [class*="cell"], [class*="col"]')
                    
                    if cells:
                        item_data = {}
                        for i, cell in enumerate(cells):
                            cell_text = await cell.text_content()
                            item_data[f"column_{i}"] = cell_text.strip()
                        
                        items.append(item_data)
                
                return {
                    "success": True,
                    "data": items,
                    "metrics": {
                        "items_count": len(items),
                        "confidence_score": 0.8
                    }
                }
            else:
                return {"success": False, "error": "No data table found"}
                
        except Exception as e:
            return {"success": False, "error": f"List operation failed: {str(e)}"}
    
    async def _browser_create_item(self, page: Page, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """ブラウザでのアイテム作成"""
        
        try:
            # 作成ボタンの検索
            create_button = await page.query_selector(
                'button:has-text("作成"), button:has-text("追加"), button:has-text("新規"), '
                'button:has-text("Create"), button:has-text("Add"), button:has-text("New"), '
                '[class*="create"], [class*="add"], [class*="new"]'
            )
            
            if create_button:
                await create_button.click()
                await page.wait_for_load_state('networkidle')
                
                # フォームの入力
                form_result = await self._fill_form_with_data(page, parameters)
                
                if form_result.get("success"):
                    # 送信ボタンのクリック
                    submit_button = await page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button:has-text("保存"), button:has-text("作成"), '
                        'button:has-text("Save"), button:has-text("Create")'
                    )
                    
                    if submit_button:
                        await submit_button.click()
                        await page.wait_for_load_state('networkidle')
                        
                        # 成功メッセージの確認
                        success_indicators = await page.query_selector_all(
                            '.success, .alert-success, [class*="success"], '
                            ':has-text("成功"), :has-text("作成"), :has-text("Success")'
                        )
                        
                        if success_indicators:
                            return {
                                "success": True,
                                "data": {"created": True, "parameters": parameters},
                                "metrics": {"confidence_score": 0.9}
                            }
                        else:
                            return {"success": False, "error": "Create operation result unclear"}
                    else:
                        return {"success": False, "error": "Submit button not found"}
                else:
                    return {"success": False, "error": "Form filling failed"}
            else:
                return {"success": False, "error": "Create button not found"}
                
        except Exception as e:
            return {"success": False, "error": f"Create operation failed: {str(e)}"}
    
    async def _fill_form_with_data(self, page: Page, data: Dict[str, Any]) -> Dict[str, Any]:
        """フォームへのデータ入力"""
        
        try:
            filled_fields = 0
            
            for key, value in data.items():
                # フィールドの検索（複数のセレクタを試行）
                field_selectors = [
                    f'input[name="{key}"]',
                    f'input[id="{key}"]',
                    f'textarea[name="{key}"]',
                    f'select[name="{key}"]',
                    f'input[placeholder*="{key}"]',
                    f'[data-field="{key}"]'
                ]
                
                field_element = None
                for selector in field_selectors:
                    try:
                        field_element = await page.query_selector(selector)
                        if field_element:
                            break
                    except:
                        continue
                
                if field_element:
                    # フィールドタイプに応じた入力
                    tag_name = await field_element.evaluate('el => el.tagName.toLowerCase()')
                    
                    if tag_name == 'select':
                        await field_element.select_option(value=str(value))
                    else:
                        await field_element.fill(str(value))
                    
                    filled_fields += 1
                    await asyncio.sleep(0.2)  # 人間らしい入力間隔
            
            return {
                "success": filled_fields > 0,
                "filled_fields": filled_fields,
                "total_fields": len(data)
            }
            
        except Exception as e:
            return {"success": False, "error": f"Form filling failed: {str(e)}"}
    
    async def _get_api_config(self, service_name: str) -> Optional[Dict[str, Any]]:
        """サービスのAPI設定取得"""
        
        # 実装: データベースまたは設定ファイルからAPI設定を取得
        api_configs = {
            "zaico": {
                "base_url": "https://api.zaico.co.jp/v1",
                "auth_type": "bearer",
                "rate_limits": {"requests_per_minute": 60}
            },
            # 他のサービスの設定...
        }
        
        return api_configs.get(service_name)
    
    async def _get_service_url(self, service_name: str) -> str:
        """サービスURLの取得"""
        
        service_urls = {
            "zaico": "https://web.zaico.co.jp",
            "notion": "https://notion.so",
            "trello": "https://trello.com",
            "airtable": "https://airtable.com"
        }
        
        return service_urls.get(service_name, f"https://{service_name}.com")
    
    def _record_operation_metrics(self, result: MCPOperationResult):
        """操作メトリクスの記録"""
        
        # 操作総数
        status = "success" if result.success else "failed"
        self.metrics['operations_total'].labels(
            service=result.service_name,
            operation=result.operation_type,
            status=status
        ).inc()
        
        # 実行時間
        self.metrics['operation_duration'].labels(
            service=result.service_name,
            operation=result.operation_type
        ).observe(result.execution_time_ms / 1000)
        
        # 成功率
        self.metrics['success_rate'].labels(
            service=result.service_name
        ).observe(1.0 if result.success else 0.0)
    
    async def _monitoring_worker(self):
        """監視ワーカー"""
        
        logger.info("Monitoring worker started")
        
        while True:
            try:
                # システム状態の監視
                await self._monitor_system_health()
                
                # ブラウザプールの監視
                await self._monitor_browser_pool()
                
                # 実行キューの監視
                await self._monitor_execution_queue()
                
                # 30秒間隔で監視
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Monitoring worker error: {e}")
                await asyncio.sleep(10)
    
    async def _monitor_system_health(self):
        """システムヘルスの監視"""
        
        # CPU使用率
        cpu_percent = psutil.cpu_percent()
        
        # メモリ使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # ディスク使用率
        disk = psutil.disk_usage('/')
        disk_percent = disk.used / disk.total * 100
        
        # アラート条件
        if cpu_percent > 80:
            logger.warning(f"High CPU usage: {cpu_percent}%")
        
        if memory_percent > 80:
            logger.warning(f"High memory usage: {memory_percent}%")
        
        if disk_percent > 90:
            logger.warning(f"High disk usage: {disk_percent}%")
    
    async def _monitor_browser_pool(self):
        """ブラウザプールの監視"""
        
        for engine, browsers in self.browser_manager.browser_pool.items():
            self.metrics['browser_pool_size'].labels(engine=engine.value).set(len(browsers))
            
            # 非応答ブラウザの検出・再起動
            for browser in browsers:
                try:
                    # ヘルスチェック
                    contexts = browser.contexts
                    if len(contexts) > 10:  # コンテキスト数の制限
                        logger.warning(f"Too many contexts in browser {engine.value}: {len(contexts)}")
                except Exception as e:
                    logger.warning(f"Browser health check failed for {engine.value}: {e}")
    
    async def _monitor_execution_queue(self):
        """実行キューの監視"""
        
        queue_size = self.execution_queue.qsize()
        active_count = len(self.active_executions)
        
        if queue_size > 100:
            logger.warning(f"Large execution queue: {queue_size}")
        
        if active_count > 50:
            logger.warning(f"Many active executions: {active_count}")
    
    async def shutdown(self):
        """実行エンジンのシャットダウン"""
        
        logger.info("Shutting down Perfect Execution Engine")
        
        # ワーカーの停止
        for _ in self.execution_workers:
            await self.execution_queue.put(None)  # 終了シグナル
        
        await asyncio.gather(*self.execution_workers, return_exceptions=True)
        
        # ブラウザプールのクリーンアップ
        for browsers in self.browser_manager.browser_pool.values():
            for browser in browsers:
                try:
                    await browser.close()
                except:
                    pass
        
        if hasattr(self.browser_manager, 'playwright'):
            await self.browser_manager.playwright.stop()
        
        logger.info("Execution engine shutdown completed")

# 使用例
async def demonstrate_perfect_execution():
    """完璧な実行エンジンのデモ"""
    
    print("🚀 Perfect Execution Engine Demo")
    print("=" * 50)
    
    # LLMクライアントの初期化（モック）
    class MockLLMClient:
        class Chat:
            class Completions:
                async def create(self, **kwargs):
                    class MockResponse:
                        class Choice:
                            class Message:
                                content = '{"compliance_level": "conditionally_compliant", "legal_score": 0.8}'
                        choices = [Choice()]
                    return MockResponse()
            completions = Completions()
        chat = Chat()
    
    llm_client = MockLLMClient()
    
    # 実行エンジンの初期化
    engine = PerfectExecutionEngine(llm_client)
    await engine.initialize(worker_count=3)
    
    # 複数操作の並列実行
    operations = [
        {"service": "zaico", "operation": "list_items", "params": {}},
        {"service": "notion", "operation": "create_item", "params": {"title": "Test Page"}},
        {"service": "trello", "operation": "list_items", "params": {"board_id": "test"}}
    ]
    
    tasks = []
    for op in operations:
        task = engine.execute_operation(
            service_name=op["service"],
            operation_type=op["operation"],
            parameters=op["params"]
        )
        tasks.append(task)
    
    # 結果の取得
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print("📊 Execution Results:")
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"   Operation {i+1}: ❌ Exception: {result}")
        else:
            print(f"   Operation {i+1}: {'✅' if result.success else '❌'} {result.service_name}.{result.operation_type}")
            if result.success:
                print(f"      Time: {result.execution_time_ms:.1f}ms")
                print(f"      Strategy: {result.strategy_used}")
            else:
                print(f"      Error: {result.error}")
    
    # シャットダウン
    await engine.shutdown()

if __name__ == "__main__":
    asyncio.run(demonstrate_perfect_execution())