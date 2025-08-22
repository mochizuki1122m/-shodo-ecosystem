"""
APIキー自動取得・管理システム
各SaaSサービスのAPIキーを自動的に取得、更新、管理
"""

import os
import hashlib
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import httpx
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

class ServiceType(Enum):
    """対応サービスタイプ"""
    SHOPIFY = "shopify"
    STRIPE = "stripe"
    GMAIL = "gmail"
    SLACK = "slack"
    NOTION = "notion"
    GITHUB = "github"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    ZENDESK = "zendesk"
    MAILCHIMP = "mailchimp"

@dataclass
class APIKeyConfig:
    """APIキー設定"""
    service: ServiceType
    key_id: str
    encrypted_key: str
    created_at: datetime
    expires_at: Optional[datetime]
    auto_renew: bool
    permissions: List[str]
    metadata: Dict[str, Any]

@dataclass
class OAuthConfig:
    """OAuth設定"""
    client_id: str
    client_secret: str
    redirect_uri: str
    authorization_url: str
    token_url: str
    scopes: List[str]

class APIKeyManager:
    """
    APIキー自動取得・管理システム
    
    機能:
    1. OAuth2.0フローによる自動認証
    2. APIキーの暗号化保存
    3. 有効期限管理と自動更新
    4. 権限スコープの最小化
    5. 監査ログ
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        # 暗号化キーの初期化
        if encryption_key:
            self.cipher = self._create_cipher(encryption_key)
        else:
            self.cipher = self._create_cipher(self._generate_key())
        
        # OAuth設定
        self.oauth_configs = self._load_oauth_configs()
        
        # キャッシュ
        self.key_cache: Dict[str, APIKeyConfig] = {}
        
        # HTTPクライアント
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
    def _generate_key(self) -> str:
        """暗号化キーを生成"""
        return Fernet.generate_key().decode()
    
    def _create_cipher(self, key: str) -> Fernet:
        """暗号化オブジェクトを作成"""
        if len(key) < 32:
            # キーが短い場合はPBKDF2で拡張
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'shodo-ecosystem',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        else:
            key = key.encode() if isinstance(key, str) else key
            
        return Fernet(key)
    
    def _load_oauth_configs(self) -> Dict[ServiceType, OAuthConfig]:
        """OAuth設定をロード"""
        return {
            ServiceType.SHOPIFY: OAuthConfig(
                client_id=os.getenv("SHOPIFY_CLIENT_ID", ""),
                client_secret=os.getenv("SHOPIFY_CLIENT_SECRET", ""),
                redirect_uri="http://localhost:8000/callback/shopify",
                authorization_url="https://{shop}.myshopify.com/admin/oauth/authorize",
                token_url="https://{shop}.myshopify.com/admin/oauth/access_token",
                scopes=["read_products", "write_products", "read_orders"]
            ),
            ServiceType.STRIPE: OAuthConfig(
                client_id=os.getenv("STRIPE_CLIENT_ID", ""),
                client_secret=os.getenv("STRIPE_CLIENT_SECRET", ""),
                redirect_uri="http://localhost:8000/callback/stripe",
                authorization_url="https://connect.stripe.com/oauth/authorize",
                token_url="https://connect.stripe.com/oauth/token",
                scopes=["read_only"]
            ),
            ServiceType.GMAIL: OAuthConfig(
                client_id=os.getenv("GMAIL_CLIENT_ID", ""),
                client_secret=os.getenv("GMAIL_CLIENT_SECRET", ""),
                redirect_uri="http://localhost:8000/callback/gmail",
                authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
                token_url="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/gmail.readonly"]
            ),
            ServiceType.GITHUB: OAuthConfig(
                client_id=os.getenv("GITHUB_CLIENT_ID", ""),
                client_secret=os.getenv("GITHUB_CLIENT_SECRET", ""),
                redirect_uri="http://localhost:8000/callback/github",
                authorization_url="https://github.com/login/oauth/authorize",
                token_url="https://github.com/login/oauth/access_token",
                scopes=["repo", "user"]
            ),
            ServiceType.SLACK: OAuthConfig(
                client_id=os.getenv("SLACK_CLIENT_ID", ""),
                client_secret=os.getenv("SLACK_CLIENT_SECRET", ""),
                redirect_uri="http://localhost:8000/callback/slack",
                authorization_url="https://slack.com/oauth/v2/authorize",
                token_url="https://slack.com/api/oauth.v2.access",
                scopes=["channels:read", "chat:write", "users:read"]
            ),
        }
    
    async def initiate_oauth_flow(
        self, 
        service: ServiceType,
        state: str,
        additional_params: Optional[Dict] = None
    ) -> str:
        """
        OAuth認証フローを開始
        
        Args:
            service: サービスタイプ
            state: CSRF対策用のstate
            additional_params: 追加パラメータ（shop名など）
            
        Returns:
            認証URL
        """
        config = self.oauth_configs.get(service)
        if not config:
            raise ValueError(f"OAuth config not found for {service}")
        
        # 認証URLを構築
        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state
        }
        
        if additional_params:
            params.update(additional_params)
        
        # URLを構築
        auth_url = config.authorization_url
        if "{shop}" in auth_url and additional_params and "shop" in additional_params:
            auth_url = auth_url.format(shop=additional_params["shop"])
        
        # クエリパラメータを追加
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{auth_url}?{query_string}"
        
        return full_url
    
    async def exchange_code_for_token(
        self,
        service: ServiceType,
        code: str,
        additional_params: Optional[Dict] = None
    ) -> APIKeyConfig:
        """
        認証コードをアクセストークンに交換
        
        Args:
            service: サービスタイプ
            code: 認証コード
            additional_params: 追加パラメータ
            
        Returns:
            APIキー設定
        """
        config = self.oauth_configs.get(service)
        if not config:
            raise ValueError(f"OAuth config not found for {service}")
        
        # トークン交換リクエスト
        data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config.redirect_uri
        }
        
        if additional_params:
            data.update(additional_params)
        
        # トークンURLを構築
        token_url = config.token_url
        if "{shop}" in token_url and additional_params and "shop" in additional_params:
            token_url = token_url.format(shop=additional_params["shop"])
        
        # トークンを取得
        response = await self.http_client.post(token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # APIキー設定を作成
        api_key_config = APIKeyConfig(
            service=service,
            key_id=self._generate_key_id(service),
            encrypted_key=self._encrypt_key(token_data.get("access_token")),
            created_at=datetime.utcnow(),
            expires_at=self._calculate_expiry(token_data),
            auto_renew=True,
            permissions=config.scopes,
            metadata={
                "token_type": token_data.get("token_type", "Bearer"),
                "refresh_token": token_data.get("refresh_token"),
                "scope": token_data.get("scope")
            }
        )
        
        # キャッシュに保存
        self.key_cache[api_key_config.key_id] = api_key_config
        
        # 永続化（データベースなど）
        await self._persist_key(api_key_config)
        
        return api_key_config
    
    async def auto_acquire_key(
        self,
        service: ServiceType,
        credentials: Dict[str, str]
    ) -> APIKeyConfig:
        """
        APIキーを自動取得（直接認証方式）
        
        Args:
            service: サービスタイプ
            credentials: 認証情報（ユーザー名、パスワードなど）
            
        Returns:
            APIキー設定
        """
        # サービス別の取得ロジック
        if service == ServiceType.SHOPIFY:
            return await self._acquire_shopify_key(credentials)
        elif service == ServiceType.STRIPE:
            return await self._acquire_stripe_key(credentials)
        elif service == ServiceType.GITHUB:
            return await self._acquire_github_key(credentials)
        else:
            raise NotImplementedError(f"Auto-acquire not implemented for {service}")
    
    async def _acquire_shopify_key(self, credentials: Dict) -> APIKeyConfig:
        """Shopify APIキーを取得"""
        shop = credentials.get("shop")
        api_key = credentials.get("api_key")
        api_secret = credentials.get("api_secret")
        
        # Private App認証
        auth_header = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
        
        # APIキー設定を作成
        return APIKeyConfig(
            service=ServiceType.SHOPIFY,
            key_id=self._generate_key_id(ServiceType.SHOPIFY),
            encrypted_key=self._encrypt_key(auth_header),
            created_at=datetime.utcnow(),
            expires_at=None,  # Private Appは期限なし
            auto_renew=False,
            permissions=["full_access"],
            metadata={
                "shop": shop,
                "auth_type": "private_app"
            }
        )
    
    async def _acquire_stripe_key(self, credentials: Dict) -> APIKeyConfig:
        """Stripe APIキーを取得"""
        secret_key = credentials.get("secret_key")
        
        # Stripeキーの検証
        headers = {"Authorization": f"Bearer {secret_key}"}
        response = await self.http_client.get(
            "https://api.stripe.com/v1/account",
            headers=headers
        )
        
        if response.status_code != 200:
            raise ValueError("Invalid Stripe API key")
        
        account_data = response.json()
        
        return APIKeyConfig(
            service=ServiceType.STRIPE,
            key_id=self._generate_key_id(ServiceType.STRIPE),
            encrypted_key=self._encrypt_key(secret_key),
            created_at=datetime.utcnow(),
            expires_at=None,
            auto_renew=False,
            permissions=self._detect_stripe_permissions(secret_key),
            metadata={
                "account_id": account_data.get("id"),
                "account_name": account_data.get("business_profile", {}).get("name")
            }
        )
    
    async def _acquire_github_key(self, credentials: Dict) -> APIKeyConfig:
        """GitHub Personal Access Tokenを取得"""
        username = credentials.get("username")
        password = credentials.get("password")
        otp = credentials.get("otp")  # 2FA用
        
        # Personal Access Token作成
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        
        if otp:
            headers["X-GitHub-OTP"] = otp
        
        auth = (username, password)
        
        data = {
            "scopes": ["repo", "user"],
            "note": f"Shodo Ecosystem - {datetime.utcnow().isoformat()}",
            "note_url": "https://shodo.ecosystem"
        }
        
        response = await self.http_client.post(
            "https://api.github.com/authorizations",
            json=data,
            headers=headers,
            auth=auth
        )
        
        if response.status_code == 201:
            token_data = response.json()
            return APIKeyConfig(
                service=ServiceType.GITHUB,
                key_id=self._generate_key_id(ServiceType.GITHUB),
                encrypted_key=self._encrypt_key(token_data["token"]),
                created_at=datetime.utcnow(),
                expires_at=None,
                auto_renew=False,
                permissions=token_data["scopes"],
                metadata={
                    "app_id": token_data["id"],
                    "app_url": token_data["url"]
                }
            )
        else:
            raise ValueError(f"Failed to create GitHub token: {response.text}")
    
    async def refresh_key(self, key_id: str) -> APIKeyConfig:
        """
        APIキーを更新
        
        Args:
            key_id: キーID
            
        Returns:
            更新されたAPIキー設定
        """
        config = self.key_cache.get(key_id)
        if not config:
            config = await self._load_key(key_id)
        
        if not config:
            raise ValueError(f"Key not found: {key_id}")
        
        # リフレッシュトークンがある場合
        if config.metadata.get("refresh_token"):
            return await self._refresh_oauth_token(config)
        
        # APIキーローテーション
        return await self._rotate_api_key(config)
    
    async def _refresh_oauth_token(self, config: APIKeyConfig) -> APIKeyConfig:
        """OAuthトークンをリフレッシュ"""
        oauth_config = self.oauth_configs.get(config.service)
        if not oauth_config:
            raise ValueError(f"OAuth config not found for {config.service}")
        
        data = {
            "client_id": oauth_config.client_id,
            "client_secret": oauth_config.client_secret,
            "refresh_token": config.metadata["refresh_token"],
            "grant_type": "refresh_token"
        }
        
        response = await self.http_client.post(oauth_config.token_url, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # 設定を更新
        config.encrypted_key = self._encrypt_key(token_data["access_token"])
        config.expires_at = self._calculate_expiry(token_data)
        config.metadata.update({
            "refresh_token": token_data.get("refresh_token", config.metadata["refresh_token"]),
            "scope": token_data.get("scope")
        })
        
        # 永続化
        await self._persist_key(config)
        
        return config
    
    async def _rotate_api_key(self, config: APIKeyConfig) -> APIKeyConfig:
        """APIキーをローテーション"""
        # サービス別のローテーションロジック
        if config.service == ServiceType.STRIPE:
            # Stripeの制限付きキーを再生成
            old_key = self._decrypt_key(config.encrypted_key)
            headers = {"Authorization": f"Bearer {old_key}"}
            
            response = await self.http_client.post(
                "https://api.stripe.com/v1/api_keys",
                headers=headers
            )
            
            if response.status_code == 200:
                new_key_data = response.json()
                config.encrypted_key = self._encrypt_key(new_key_data["secret"])
                config.created_at = datetime.utcnow()
                
                # 古いキーを無効化
                await self.http_client.delete(
                    f"https://api.stripe.com/v1/api_keys/{config.metadata.get('key_id')}",
                    headers=headers
                )
                
                config.metadata["key_id"] = new_key_data["id"]
        
        await self._persist_key(config)
        return config
    
    def _encrypt_key(self, key: str) -> str:
        """キーを暗号化"""
        return self.cipher.encrypt(key.encode()).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """キーを復号化"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
    def _generate_key_id(self, service: ServiceType) -> str:
        """キーIDを生成"""
        timestamp = datetime.utcnow().isoformat()
        data = f"{service.value}:{timestamp}".encode()
        return hashlib.sha256(data).hexdigest()[:16]
    
    def _calculate_expiry(self, token_data: Dict) -> Optional[datetime]:
        """有効期限を計算"""
        if "expires_in" in token_data:
            return datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        return None
    
    def _detect_stripe_permissions(self, key: str) -> List[str]:
        """Stripeキーの権限を検出"""
        if key.startswith("sk_live_"):
            return ["live_mode", "full_access"]
        elif key.startswith("sk_test_"):
            return ["test_mode", "full_access"]
        elif key.startswith("rk_live_"):
            return ["live_mode", "restricted_access"]
        elif key.startswith("rk_test_"):
            return ["test_mode", "restricted_access"]
        else:
            return ["unknown"]
    
    async def _persist_key(self, config: APIKeyConfig):
        """キーを永続化（データベースなど）"""
        # TODO: データベースへの保存実装
        pass
    
    async def _load_key(self, key_id: str) -> Optional[APIKeyConfig]:
        """キーをロード"""
        # TODO: データベースからのロード実装
        return None
    
    async def revoke_key(self, key_id: str):
        """
        APIキーを無効化
        
        Args:
            key_id: キーID
        """
        config = self.key_cache.get(key_id)
        if not config:
            config = await self._load_key(key_id)
        
        if not config:
            raise ValueError(f"Key not found: {key_id}")
        
        # サービス別の無効化処理
        if config.service == ServiceType.GITHUB:
            # GitHubトークンを削除
            key = self._decrypt_key(config.encrypted_key)
            headers = {
                "Authorization": f"token {key}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            if "app_id" in config.metadata:
                await self.http_client.delete(
                    f"https://api.github.com/authorizations/{config.metadata['app_id']}",
                    headers=headers
                )
        
        # キャッシュから削除
        if key_id in self.key_cache:
            del self.key_cache[key_id]
        
        # データベースから削除
        # TODO: データベース削除実装
    
    async def get_active_key(self, service: ServiceType) -> Optional[str]:
        """
        アクティブなAPIキーを取得
        
        Args:
            service: サービスタイプ
            
        Returns:
            復号化されたAPIキー
        """
        # キャッシュから検索
        for config in self.key_cache.values():
            if config.service == service:
                # 有効期限チェック
                if config.expires_at and config.expires_at < datetime.utcnow():
                    if config.auto_renew:
                        config = await self.refresh_key(config.key_id)
                    else:
                        continue
                
                return self._decrypt_key(config.encrypted_key)
        
        # データベースから検索
        # TODO: データベース検索実装
        
        return None
    
    async def cleanup(self):
        """クリーンアップ"""
        await self.http_client.aclose()