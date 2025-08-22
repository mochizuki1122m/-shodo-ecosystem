"""
可視ログイン検知システム

Playwrightを使用してヘッドフルブラウザでのログインプロセスを制御し、
成功を検知してセキュアな認証情報を取得します。
"""

import asyncio
import secrets
import hashlib
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import logging

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
import structlog

# 構造化ログ
logger = structlog.get_logger()

@dataclass
class LoginDetectionResult:
    """ログイン検知結果"""
    success: bool
    method: str  # "cookie", "url", "dom", "api", "composite"
    confidence: float  # 0.0 - 1.0
    cookies: Optional[List[Dict]] = None
    session_data: Optional[Dict] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    detection_time: Optional[datetime] = None

@dataclass
class LoginDetectionRule:
    """ログイン検知ルール"""
    name: str
    type: str  # "cookie", "url", "dom", "api"
    pattern: str
    weight: float = 1.0  # 複合判定での重み
    required: bool = False  # 必須条件か

class VisibleLoginDetector:
    """可視ログイン検知器"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.detection_rules: Dict[str, List[LoginDetectionRule]] = {}
        self._init_default_rules()
    
    def _init_default_rules(self):
        """デフォルト検知ルールの初期化"""
        # 汎用的なルール（サービス固有のルールは動的に追加）
        self.detection_rules["default"] = [
            LoginDetectionRule(
                name="session_cookie",
                type="cookie",
                pattern="session|sess|sid|token",
                weight=2.0
            ),
            LoginDetectionRule(
                name="auth_cookie",
                type="cookie",
                pattern="auth|jwt|access",
                weight=1.5
            ),
            LoginDetectionRule(
                name="dashboard_url",
                type="url",
                pattern="/dashboard|/home|/account|/profile",
                weight=1.0
            ),
            LoginDetectionRule(
                name="logout_button",
                type="dom",
                pattern="button:has-text('Logout')|a:has-text('Sign out')",
                weight=1.0
            ),
        ]
    
    async def start(self, headless: bool = False):
        """ブラウザを起動"""
        self.playwright = await async_playwright().start()
        
        # セキュリティ設定を含むブラウザ起動
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',  # Dockerでの実行用
                '--disable-setuid-sandbox',
            ]
        )
        
        logger.info("Visible browser started", headless=headless)
    
    async def stop(self):
        """ブラウザを停止"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        logger.info("Visible browser stopped")
    
    async def detect_login(
        self,
        login_url: str,
        service_name: str = "default",
        timeout: int = 120,
        auto_fill: Optional[Dict[str, str]] = None,
        custom_rules: Optional[List[LoginDetectionRule]] = None,
    ) -> LoginDetectionResult:
        """ログインを検知"""
        
        if not self.browser:
            await self.start(headless=False)  # 可視ブラウザで起動
        
        context = None
        page = None
        
        try:
            # 新しいコンテキストを作成（クリーンな状態）
            context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                locale='ja-JP',
                timezone_id='Asia/Tokyo',
            )
            
            # ページを作成
            page = await context.new_page()
            
            # ネットワーク監視を開始
            api_calls = []
            async def on_response(response):
                if response.status == 200:
                    url = response.url
                    if any(pattern in url for pattern in ['/api/', '/auth/', '/login']):
                        api_calls.append({
                            'url': url,
                            'status': response.status,
                            'headers': await response.all_headers(),
                        })
            
            page.on("response", on_response)
            
            # ログインページに移動
            await page.goto(login_url, wait_until='networkidle')
            
            # 自動入力（オプション）
            if auto_fill:
                await self._auto_fill_form(page, auto_fill)
            
            # カスタムルールを追加
            if custom_rules:
                self.detection_rules[service_name] = custom_rules
            
            # ルールを取得
            rules = self.detection_rules.get(service_name, self.detection_rules["default"])
            
            # ログイン検知ループ
            start_time = asyncio.get_event_loop().time()
            detection_interval = 1.0  # 1秒ごとにチェック
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                # 複合的な検知
                detection_results = await self._perform_detection(page, rules, api_calls)
                
                # 成功判定
                if detection_results['success']:
                    # Cookieを取得
                    cookies = await context.cookies()
                    
                    # スクリーンショット保存
                    screenshot_path = f"/tmp/login_success_{secrets.token_hex(8)}.png"
                    await page.screenshot(path=screenshot_path)
                    
                    return LoginDetectionResult(
                        success=True,
                        method=detection_results['method'],
                        confidence=detection_results['confidence'],
                        cookies=cookies,
                        session_data=detection_results.get('session_data'),
                        screenshot_path=screenshot_path,
                        detection_time=datetime.now(timezone.utc),
                    )
                
                # 次のチェックまで待機
                await asyncio.sleep(detection_interval)
            
            # タイムアウト
            return LoginDetectionResult(
                success=False,
                method="timeout",
                confidence=0.0,
                error_message=f"Login detection timed out after {timeout} seconds",
            )
            
        except Exception as e:
            logger.error("Login detection failed", error=str(e))
            return LoginDetectionResult(
                success=False,
                method="error",
                confidence=0.0,
                error_message=str(e),
            )
        
        finally:
            # クリーンアップ
            if page:
                await page.close()
            if context:
                await context.close()
    
    async def _auto_fill_form(self, page: Page, fields: Dict[str, str]):
        """フォームを自動入力"""
        for selector, value in fields.items():
            try:
                # 要素が表示されるまで待機
                await page.wait_for_selector(selector, state='visible', timeout=5000)
                
                # 人間的な入力をシミュレート
                await page.fill(selector, value, timeout=5000)
                
                # 少し待機（人間的な動作）
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Failed to fill {selector}", error=str(e))
    
    async def _perform_detection(
        self,
        page: Page,
        rules: List[LoginDetectionRule],
        api_calls: List[Dict]
    ) -> Dict[str, Any]:
        """複合的なログイン検知を実行"""
        
        total_weight = 0.0
        matched_weight = 0.0
        matched_rules = []
        session_data = {}
        
        for rule in rules:
            matched = False
            
            try:
                if rule.type == "cookie":
                    # Cookie検知
                    cookies = await page.context.cookies()
                    for cookie in cookies:
                        if rule.pattern.lower() in cookie['name'].lower():
                            matched = True
                            session_data[cookie['name']] = cookie['value']
                            break
                
                elif rule.type == "url":
                    # URL検知
                    current_url = page.url
                    if any(pattern in current_url for pattern in rule.pattern.split('|')):
                        matched = True
                
                elif rule.type == "dom":
                    # DOM要素検知
                    elements = await page.query_selector_all(rule.pattern)
                    if elements:
                        matched = True
                
                elif rule.type == "api":
                    # API呼び出し検知
                    for call in api_calls:
                        if rule.pattern in call['url']:
                            matched = True
                            # レスポンスヘッダーからセッション情報を抽出
                            headers = call.get('headers', {})
                            if 'set-cookie' in headers:
                                session_data['api_cookie'] = headers['set-cookie']
                            break
                
            except Exception as e:
                logger.debug(f"Rule check failed: {rule.name}", error=str(e))
            
            # 重み計算
            total_weight += rule.weight
            if matched:
                matched_weight += rule.weight
                matched_rules.append(rule.name)
            elif rule.required:
                # 必須ルールが満たされない場合は失敗
                return {
                    'success': False,
                    'method': 'required_rule_failed',
                    'confidence': 0.0,
                }
        
        # 信頼度計算
        confidence = matched_weight / total_weight if total_weight > 0 else 0.0
        
        # 成功判定（信頼度60%以上）
        success = confidence >= 0.6
        
        # 検知方法の決定
        if len(matched_rules) > 1:
            method = "composite"
        elif matched_rules:
            method = matched_rules[0]
        else:
            method = "none"
        
        return {
            'success': success,
            'method': method,
            'confidence': confidence,
            'matched_rules': matched_rules,
            'session_data': session_data,
        }
    
    async def extract_device_fingerprint(self, page: Page) -> Dict[str, Any]:
        """デバイス指紋を抽出"""
        
        # JavaScriptでブラウザ情報を取得
        fingerprint_script = """
        () => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillText('fingerprint', 2, 2);
            const canvasData = canvas.toDataURL();
            
            return {
                userAgent: navigator.userAgent,
                language: navigator.language,
                languages: navigator.languages,
                platform: navigator.platform,
                screenResolution: `${screen.width}x${screen.height}`,
                colorDepth: screen.colorDepth,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                hardwareConcurrency: navigator.hardwareConcurrency,
                deviceMemory: navigator.deviceMemory,
                canvasFingerprint: canvasData.substring(0, 50),  // 一部のみ
                webglVendor: (() => {
                    try {
                        const canvas = document.createElement('canvas');
                        const gl = canvas.getContext('webgl');
                        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                        return gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                    } catch (e) {
                        return null;
                    }
                })(),
            };
        }
        """
        
        try:
            fingerprint = await page.evaluate(fingerprint_script)
            return fingerprint
        except Exception as e:
            logger.error("Failed to extract device fingerprint", error=str(e))
            return {}

class SecureSessionStorage:
    """セキュアなセッション保存"""
    
    def __init__(self):
        self.storage: Dict[str, Dict] = {}  # メモリ内保存（一時的）
    
    async def store_session(
        self,
        user_id: str,
        cookies: List[Dict],
        ttl_seconds: int = 300  # 5分
    ) -> str:
        """セッションを一時保存"""
        
        session_id = secrets.token_urlsafe(32)
        
        # セッションデータを暗号化して保存（実装簡略化のため平文）
        self.storage[session_id] = {
            'user_id': user_id,
            'cookies': cookies,
            'expires_at': datetime.now(timezone.utc).timestamp() + ttl_seconds,
        }
        
        # 期限切れセッションをクリーンアップ
        await self._cleanup_expired()
        
        logger.info("Session stored", session_id=session_id, user_id=user_id)
        return session_id
    
    async def retrieve_session(self, session_id: str) -> Optional[Dict]:
        """セッションを取得"""
        
        session = self.storage.get(session_id)
        
        if not session:
            return None
        
        # 期限チェック
        if datetime.now(timezone.utc).timestamp() > session['expires_at']:
            del self.storage[session_id]
            return None
        
        return session
    
    async def delete_session(self, session_id: str) -> bool:
        """セッションを削除"""
        
        if session_id in self.storage:
            del self.storage[session_id]
            logger.info("Session deleted", session_id=session_id)
            return True
        
        return False
    
    async def _cleanup_expired(self):
        """期限切れセッションをクリーンアップ"""
        
        now = datetime.now(timezone.utc).timestamp()
        expired = [
            sid for sid, data in self.storage.items()
            if data['expires_at'] < now
        ]
        
        for sid in expired:
            del self.storage[sid]
        
        if expired:
            logger.info("Cleaned up expired sessions", count=len(expired))

# シングルトンインスタンス
visible_login_detector = VisibleLoginDetector()
secure_session_storage = SecureSessionStorage()

async def init_visible_login():
    """可視ログインシステムの初期化"""
    # 必要に応じてブラウザを事前起動
    # await visible_login_detector.start(headless=True)
    logger.info("Visible login system initialized")

async def cleanup_visible_login():
    """クリーンアップ"""
    await visible_login_detector.stop()
    logger.info("Visible login system cleaned up")