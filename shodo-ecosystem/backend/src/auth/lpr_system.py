"""
LPR (Limited Permission Receipt) 認証システム
ユーザーの正当なログインセッションを一時的に証明し、プログラムが代理操作できるようにする
"""

import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import asyncio
from playwright.async_api import async_playwright, Page
import httpx

@dataclass
class LPR:
    """
    Limited Permission Receipt
    ユーザーのログインセッションの一時的な証明書
    """
    # 識別情報
    lpr_id: str
    service_name: str
    service_url: str
    
    # ユーザー情報（匿名化）
    user_pseudonym: str
    
    # 時間情報
    issued_at: datetime
    expires_at: datetime
    
    # セッション情報
    session_cookies: List[Dict[str, Any]]
    auth_headers: Dict[str, str] = field(default_factory=dict)
    
    # デバイス情報
    device_fingerprint: str
    browser_fingerprint: str
    
    # 監査情報
    audit_enabled: bool = True
    operations_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # 状態
    is_active: bool = True
    revoked_at: Optional[datetime] = None
    
    def is_valid(self) -> bool:
        """LPRが有効かチェック"""
        if not self.is_active:
            return False
        if self.revoked_at:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'lpr_id': self.lpr_id,
            'service_name': self.service_name,
            'service_url': self.service_url,
            'user_pseudonym': self.user_pseudonym,
            'issued_at': self.issued_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'device_fingerprint': self.device_fingerprint,
            'browser_fingerprint': self.browser_fingerprint,
            'is_active': self.is_active,
            'operations_count': len(self.operations_log)
        }

class LPRAuthenticator:
    """
    LPR認証を行うクラス
    ユーザーの手動ログインを検知し、LPRを発行する
    """
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        
    async def authenticate(
        self,
        service_url: str,
        service_name: Optional[str] = None,
        ttl_hours: int = 2
    ) -> LPR:
        """
        ユーザーに手動ログインしてもらい、LPRを発行
        
        Args:
            service_url: ログイン対象のサービスURL
            service_name: サービス名（自動検出も可能）
            ttl_hours: LPRの有効時間（デフォルト2時間）
        
        Returns:
            発行されたLPR
        """
        
        # サービス名の自動検出
        if not service_name:
            service_name = self._detect_service_name(service_url)
        
        print(f"🔐 LPR Authentication for {service_name}")
        print(f"📍 URL: {service_url}")
        print("-" * 50)
        
        # ブラウザを起動（ユーザーに見える形で）
        async with async_playwright() as p:
            # ユーザーが見えるブラウザを起動
            self.browser = await p.chromium.launch(
                headless=False,  # 必ずGUIモードで起動
                args=['--start-maximized']
            )
            
            # コンテキスト作成（セッション管理用）
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            self.page = await self.context.new_page()
            
            # ログインページへ遷移
            await self.page.goto(service_url)
            
            print("👤 Please login manually in the opened browser window")
            print("⏳ Waiting for successful login...")
            print("-" * 50)
            
            # ログイン成功を検知
            login_success = await self._detect_login_success(
                self.page,
                service_name
            )
            
            if login_success:
                print("✅ Login detected successfully!")
                
                # LPRを発行
                lpr = await self._issue_lpr(
                    service_name=service_name,
                    service_url=service_url,
                    ttl_hours=ttl_hours
                )
                
                print(f"🎫 LPR issued: {lpr.lpr_id}")
                print(f"⏰ Valid until: {lpr.expires_at}")
                
                # ブラウザは開いたままにする（ユーザーが閉じるまで）
                print("\n📌 You can close the browser when done")
                
                return lpr
            else:
                raise Exception("Login detection failed")
    
    async def _detect_login_success(
        self,
        page: Page,
        service_name: str,
        timeout: int = 300
    ) -> bool:
        """
        ログイン成功を検知する
        複数の方法を組み合わせて確実に検知
        """
        
        # サービス別の検知ロジック
        detectors = {
            'shopify': self._detect_shopify_login,
            'stripe': self._detect_stripe_login,
            'gmail': self._detect_gmail_login,
            'generic': self._detect_generic_login
        }
        
        # 適切な検知器を選択
        detector = detectors.get(
            service_name.lower(),
            self._detect_generic_login
        )
        
        # タイムアウト付きで検知を実行
        try:
            result = await asyncio.wait_for(
                detector(page),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            print("⏱️ Login detection timeout")
            return False
    
    async def _detect_shopify_login(self, page: Page) -> bool:
        """Shopify固有のログイン検知"""
        while True:
            # 複数の条件をチェック
            checks = []
            
            # 1. URLチェック（管理画面に遷移）
            if 'admin.shopify.com' in page.url or '/admin' in page.url:
                checks.append(True)
            
            # 2. Cookie確認
            cookies = await page.context.cookies()
            has_session = any(
                c['name'] in ['_shopify_s', '_master_udr', 'logged_in']
                for c in cookies
            )
            if has_session:
                checks.append(True)
            
            # 3. DOM要素確認（ユーザーメニュー等）
            try:
                user_menu = await page.query_selector('[data-user-menu], .user-menu, #AppFrameNav')
                if user_menu:
                    checks.append(True)
            except:
                pass
            
            # 2つ以上の条件が満たされたら成功
            if sum(checks) >= 2:
                return True
            
            # 1秒待って再チェック
            await asyncio.sleep(1)
    
    async def _detect_stripe_login(self, page: Page) -> bool:
        """Stripe固有のログイン検知"""
        while True:
            # ダッシュボードURLチェック
            if 'dashboard.stripe.com' in page.url:
                return True
            
            # APIキー表示要素
            try:
                api_section = await page.query_selector('[data-test="api-keys-section"]')
                if api_section:
                    return True
            except:
                pass
            
            await asyncio.sleep(1)
    
    async def _detect_gmail_login(self, page: Page) -> bool:
        """Gmail固有のログイン検知"""
        while True:
            # Gmail URLチェック
            if 'mail.google.com' in page.url:
                # 受信トレイの要素確認
                try:
                    inbox = await page.query_selector('[role="main"], .AO')
                    if inbox:
                        return True
                except:
                    pass
            
            await asyncio.sleep(1)
    
    async def _detect_generic_login(self, page: Page) -> bool:
        """
        汎用的なログイン検知
        どのサービスでも使える一般的なパターン
        """
        initial_url = page.url
        
        while True:
            current_url = page.url
            
            # URLが大きく変わった（ログイン→ダッシュボード）
            if self._is_significant_url_change(initial_url, current_url):
                # ログイン関連のURLでなくなった
                login_keywords = ['login', 'signin', 'auth', 'sso']
                if not any(kw in current_url.lower() for kw in login_keywords):
                    return True
            
            # Cookieの増加を確認
            cookies = await page.context.cookies()
            session_cookies = [
                c for c in cookies
                if any(kw in c['name'].lower() for kw in ['session', 'auth', 'token', 'user'])
            ]
            if len(session_cookies) > 0:
                return True
            
            # ユーザー関連の要素を探す
            user_selectors = [
                '[class*="user"]',
                '[id*="user"]',
                '[class*="account"]',
                '[class*="profile"]',
                'img[alt*="avatar"]',
                '.avatar',
                '.user-menu'
            ]
            
            for selector in user_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return True
                except:
                    continue
            
            await asyncio.sleep(1)
    
    def _is_significant_url_change(self, initial_url: str, current_url: str) -> bool:
        """URLが大きく変わったかチェック"""
        from urllib.parse import urlparse
        
        initial = urlparse(initial_url)
        current = urlparse(current_url)
        
        # ドメインが同じでパスが変わった
        if initial.netloc == current.netloc:
            # パスが大きく変わった
            if initial.path != current.path:
                # ログインページから離れた
                if 'login' not in current.path.lower():
                    return True
        
        return False
    
    async def _issue_lpr(
        self,
        service_name: str,
        service_url: str,
        ttl_hours: int
    ) -> LPR:
        """
        LPRを発行する
        """
        
        # セッション情報を取得
        cookies = await self.context.cookies()
        
        # デバイス/ブラウザのフィンガープリント生成
        device_fingerprint = self._generate_device_fingerprint()
        browser_fingerprint = await self._generate_browser_fingerprint(self.page)
        
        # ユーザーの匿名化ID生成
        user_pseudonym = self._generate_user_pseudonym(cookies)
        
        # LPR作成
        lpr = LPR(
            lpr_id=f"lpr_{secrets.token_urlsafe(16)}",
            service_name=service_name,
            service_url=service_url,
            user_pseudonym=user_pseudonym,
            issued_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
            session_cookies=cookies,
            device_fingerprint=device_fingerprint,
            browser_fingerprint=browser_fingerprint,
            audit_enabled=True,
            is_active=True
        )
        
        return lpr
    
    def _detect_service_name(self, url: str) -> str:
        """URLからサービス名を自動検出"""
        from urllib.parse import urlparse
        
        domain = urlparse(url).netloc.lower()
        
        # 既知のサービス
        known_services = {
            'shopify': 'Shopify',
            'stripe': 'Stripe',
            'gmail': 'Gmail',
            'google': 'Google',
            'github': 'GitHub',
            'slack': 'Slack',
            'notion': 'Notion',
            'airtable': 'Airtable'
        }
        
        for key, name in known_services.items():
            if key in domain:
                return name
        
        # 不明な場合はドメイン名を使用
        return domain.split('.')[0].capitalize()
    
    def _generate_device_fingerprint(self) -> str:
        """デバイスフィンガープリント生成"""
        import platform
        
        device_info = {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'python_version': platform.python_version()
        }
        
        return hashlib.sha256(
            json.dumps(device_info, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    async def _generate_browser_fingerprint(self, page: Page) -> str:
        """ブラウザフィンガープリント生成"""
        # ブラウザ情報を取得
        user_agent = await page.evaluate('navigator.userAgent')
        
        browser_info = {
            'user_agent': user_agent,
            'viewport': await page.viewport_size()
        }
        
        return hashlib.sha256(
            json.dumps(browser_info, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def _generate_user_pseudonym(self, cookies: List[Dict]) -> str:
        """ユーザーの匿名化ID生成"""
        # セッション情報から一意なIDを生成（個人情報は含まない）
        session_data = json.dumps(
            sorted([c['name'] for c in cookies])
        )
        
        return f"user_{hashlib.sha256(session_data.encode()).hexdigest()[:12]}"

class LPRSession:
    """
    LPRを使用してHTTPリクエストを実行するセッション
    """
    
    def __init__(self, lpr: LPR):
        self.lpr = lpr
        self.client = None
        self._setup_client()
    
    def _setup_client(self):
        """HTTPクライアントをセットアップ"""
        # Cookieをヘッダーに変換
        cookie_header = '; '.join([
            f"{c['name']}={c['value']}"
            for c in self.lpr.session_cookies
        ])
        
        headers = {
            'Cookie': cookie_header,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # 追加の認証ヘッダーがあれば追加
        headers.update(self.lpr.auth_headers)
        
        self.client = httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=30.0
        )
    
    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        LPRを使用してHTTPリクエストを実行
        
        Args:
            method: HTTPメソッド
            url: リクエストURL
            **kwargs: その他のhttpxパラメータ
        
        Returns:
            HTTPレスポンス
        """
        
        # LPRの有効性チェック
        if not self.lpr.is_valid():
            raise Exception(f"LPR {self.lpr.lpr_id} is no longer valid")
        
        # 監査ログに記録
        operation = {
            'timestamp': datetime.utcnow().isoformat(),
            'method': method,
            'url': url,
            'lpr_id': self.lpr.lpr_id
        }
        
        try:
            # リクエスト実行
            response = await self.client.request(method, url, **kwargs)
            
            # 成功を記録
            operation['status'] = response.status_code
            operation['success'] = True
            
            return response
            
        except Exception as e:
            # エラーを記録
            operation['error'] = str(e)
            operation['success'] = False
            raise
            
        finally:
            # 監査ログに追加
            if self.lpr.audit_enabled:
                self.lpr.operations_log.append(operation)
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET リクエスト"""
        return await self.request('GET', url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST リクエスト"""
        return await self.request('POST', url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> httpx.Response:
        """PUT リクエスト"""
        return await self.request('PUT', url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """DELETE リクエスト"""
        return await self.request('DELETE', url, **kwargs)
    
    async def close(self):
        """セッションをクローズ"""
        if self.client:
            await self.client.aclose()

class LPRManager:
    """
    LPRのライフサイクル管理
    """
    
    def __init__(self):
        self.active_lprs: Dict[str, LPR] = {}
        self.revoked_lprs: List[str] = []
    
    def register(self, lpr: LPR):
        """LPRを登録"""
        self.active_lprs[lpr.lpr_id] = lpr
    
    def get(self, lpr_id: str) -> Optional[LPR]:
        """LPRを取得"""
        return self.active_lprs.get(lpr_id)
    
    def revoke(self, lpr_id: str):
        """LPRを無効化"""
        if lpr_id in self.active_lprs:
            lpr = self.active_lprs[lpr_id]
            lpr.is_active = False
            lpr.revoked_at = datetime.utcnow()
            self.revoked_lprs.append(lpr_id)
            del self.active_lprs[lpr_id]
    
    def cleanup_expired(self):
        """期限切れLPRをクリーンアップ"""
        expired = []
        for lpr_id, lpr in self.active_lprs.items():
            if not lpr.is_valid():
                expired.append(lpr_id)
        
        for lpr_id in expired:
            del self.active_lprs[lpr_id]
    
    def get_audit_log(self, lpr_id: str) -> List[Dict[str, Any]]:
        """監査ログを取得"""
        lpr = self.get(lpr_id)
        if lpr:
            return lpr.operations_log
        return []

# 使用例
async def example_usage():
    """
    LPRシステムの使用例
    """
    
    # 1. ユーザーに手動ログインしてもらう
    authenticator = LPRAuthenticator()
    lpr = await authenticator.authenticate(
        service_url="https://mystore.myshopify.com/admin",
        service_name="Shopify",
        ttl_hours=2  # 2時間有効
    )
    
    # 2. LPRを使ってAPIリクエスト
    session = LPRSession(lpr)
    
    # ユーザーの全権限で操作可能
    response = await session.get("https://mystore.myshopify.com/admin/api/2024-01/orders.json")
    _ = response.json()
    
    # 3. 監査ログの確認
    print(f"Operations performed: {len(lpr.operations_log)}")
    for op in lpr.operations_log:
        print(f"  - {op['method']} {op['url']} at {op['timestamp']}")
    
    # 4. セッションクローズ
    await session.close()

if __name__ == "__main__":
    asyncio.run(example_usage())