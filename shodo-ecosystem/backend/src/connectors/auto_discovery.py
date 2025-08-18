"""
SaaS自動検出・連携システム
URLから自動的にSaaSを識別し、適切なコネクタを選択または生成
"""

import re
import httpx
from typing import Dict, Any, Optional, List, Type
from urllib.parse import urlparse
import json

from .base import BaseSaaSConnector, ConnectorCredentials
from .shopify import ShopifyConnector
from .stripe import StripeConnector
from .universal import UniversalSaaSConnector

class SaaSIdentifier:
    """SaaS識別クラス"""
    
    # 既知のSaaSパターン
    KNOWN_SAAS_PATTERNS = {
        'shopify': {
            'domains': ['.myshopify.com', 'shopify.com'],
            'api_patterns': ['/admin/api/', '/api/'],
            'connector_class': ShopifyConnector,
            'name': 'Shopify'
        },
        'stripe': {
            'domains': ['stripe.com', 'api.stripe.com'],
            'api_patterns': ['/v1/'],
            'connector_class': StripeConnector,
            'name': 'Stripe'
        },
        'salesforce': {
            'domains': ['salesforce.com', '.force.com', '.my.salesforce.com'],
            'api_patterns': ['/services/data/', '/services/oauth2/'],
            'connector_class': None,  # UniversalConnectorを使用
            'name': 'Salesforce'
        },
        'hubspot': {
            'domains': ['hubspot.com', 'api.hubapi.com'],
            'api_patterns': ['/crm/v3/', '/contacts/v1/'],
            'connector_class': None,
            'name': 'HubSpot'
        },
        'slack': {
            'domains': ['slack.com', 'api.slack.com'],
            'api_patterns': ['/api/', '/methods/'],
            'connector_class': None,
            'name': 'Slack'
        },
        'gmail': {
            'domains': ['gmail.com', 'googleapis.com/gmail'],
            'api_patterns': ['/gmail/v1/', '/users/'],
            'connector_class': None,
            'name': 'Gmail'
        },
        'github': {
            'domains': ['github.com', 'api.github.com'],
            'api_patterns': ['/repos/', '/users/', '/graphql'],
            'connector_class': None,
            'name': 'GitHub'
        },
        'jira': {
            'domains': ['atlassian.net', 'jira.com'],
            'api_patterns': ['/rest/api/', '/rest/'],
            'connector_class': None,
            'name': 'Jira'
        },
        'notion': {
            'domains': ['notion.so', 'api.notion.com'],
            'api_patterns': ['/v1/', '/databases/', '/pages/'],
            'connector_class': None,
            'name': 'Notion'
        },
        'airtable': {
            'domains': ['airtable.com', 'api.airtable.com'],
            'api_patterns': ['/v0/', '/bases/'],
            'connector_class': None,
            'name': 'Airtable'
        },
        'mailchimp': {
            'domains': ['mailchimp.com', 'api.mailchimp.com'],
            'api_patterns': ['/3.0/', '/campaigns/'],
            'connector_class': None,
            'name': 'Mailchimp'
        },
        'zendesk': {
            'domains': ['zendesk.com'],
            'api_patterns': ['/api/v2/', '/tickets/'],
            'connector_class': None,
            'name': 'Zendesk'
        },
        'twilio': {
            'domains': ['twilio.com', 'api.twilio.com'],
            'api_patterns': ['/2010-04-01/', '/Accounts/'],
            'connector_class': None,
            'name': 'Twilio'
        },
        'sendgrid': {
            'domains': ['sendgrid.com', 'api.sendgrid.com'],
            'api_patterns': ['/v3/', '/mail/'],
            'connector_class': None,
            'name': 'SendGrid'
        },
        'dropbox': {
            'domains': ['dropbox.com', 'api.dropboxapi.com'],
            'api_patterns': ['/2/', '/files/'],
            'connector_class': None,
            'name': 'Dropbox'
        },
        'google_drive': {
            'domains': ['drive.google.com', 'googleapis.com/drive'],
            'api_patterns': ['/drive/v3/', '/files/'],
            'connector_class': None,
            'name': 'Google Drive'
        },
        'zoom': {
            'domains': ['zoom.us', 'api.zoom.us'],
            'api_patterns': ['/v2/', '/users/', '/meetings/'],
            'connector_class': None,
            'name': 'Zoom'
        },
        'monday': {
            'domains': ['monday.com', 'api.monday.com'],
            'api_patterns': ['/v2/', '/boards/'],
            'connector_class': None,
            'name': 'Monday.com'
        },
        'asana': {
            'domains': ['asana.com', 'app.asana.com'],
            'api_patterns': ['/api/1.0/', '/tasks/'],
            'connector_class': None,
            'name': 'Asana'
        },
        'trello': {
            'domains': ['trello.com', 'api.trello.com'],
            'api_patterns': ['/1/', '/boards/'],
            'connector_class': None,
            'name': 'Trello'
        }
    }
    
    @classmethod
    async def identify_saas(cls, url: str) -> Optional[Dict[str, Any]]:
        """URLからSaaSを識別"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        path = parsed_url.path.lower()
        
        # 既知のSaaSパターンをチェック
        for saas_key, patterns in cls.KNOWN_SAAS_PATTERNS.items():
            # ドメインチェック
            for pattern_domain in patterns['domains']:
                if pattern_domain in domain:
                    return {
                        'type': saas_key,
                        'name': patterns['name'],
                        'connector_class': patterns['connector_class'],
                        'confidence': 0.9
                    }
            
            # APIパターンチェック
            for api_pattern in patterns['api_patterns']:
                if api_pattern in path:
                    return {
                        'type': saas_key,
                        'name': patterns['name'],
                        'connector_class': patterns['connector_class'],
                        'confidence': 0.8
                    }
        
        # HTTPヘッダーから推測
        saas_info = await cls._identify_from_headers(url)
        if saas_info:
            return saas_info
        
        # HTMLコンテンツから推測
        saas_info = await cls._identify_from_content(url)
        if saas_info:
            return saas_info
        
        return None
    
    @classmethod
    async def _identify_from_headers(cls, url: str) -> Optional[Dict[str, Any]]:
        """HTTPヘッダーからSaaSを識別"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(url, follow_redirects=True)
                headers = response.headers
                
                # X-Powered-Byヘッダー
                powered_by = headers.get('x-powered-by', '').lower()
                if 'shopify' in powered_by:
                    return {
                        'type': 'shopify',
                        'name': 'Shopify',
                        'connector_class': ShopifyConnector,
                        'confidence': 0.85
                    }
                
                # Serverヘッダー
                server = headers.get('server', '').lower()
                if 'nginx' in server and 'stripe' in headers.get('x-stripe-version', ''):
                    return {
                        'type': 'stripe',
                        'name': 'Stripe',
                        'connector_class': StripeConnector,
                        'confidence': 0.85
                    }
                
                # カスタムヘッダー
                for header_name, header_value in headers.items():
                    header_lower = header_name.lower()
                    value_lower = str(header_value).lower()
                    
                    for saas_key, patterns in cls.KNOWN_SAAS_PATTERNS.items():
                        if saas_key in header_lower or saas_key in value_lower:
                            return {
                                'type': saas_key,
                                'name': patterns['name'],
                                'connector_class': patterns['connector_class'],
                                'confidence': 0.7
                            }
        except:
            pass
        
        return None
    
    @classmethod
    async def _identify_from_content(cls, url: str) -> Optional[Dict[str, Any]]:
        """HTMLコンテンツからSaaSを識別"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True)
                content = response.text.lower()
                
                # メタタグをチェック
                if '<meta name="shopify-' in content:
                    return {
                        'type': 'shopify',
                        'name': 'Shopify',
                        'connector_class': ShopifyConnector,
                        'confidence': 0.9
                    }
                
                # JavaScript変数をチェック
                js_patterns = {
                    'window.stripe': ('stripe', 'Stripe', StripeConnector),
                    'salesforce.': ('salesforce', 'Salesforce', None),
                    'hubspot.': ('hubspot', 'HubSpot', None),
                }
                
                for pattern, (saas_type, name, connector) in js_patterns.items():
                    if pattern in content:
                        return {
                            'type': saas_type,
                            'name': name,
                            'connector_class': connector,
                            'confidence': 0.75
                        }
        except:
            pass
        
        return None

class AutoConnectorFactory:
    """自動コネクタファクトリー"""
    
    @classmethod
    async def create_connector(
        cls,
        url: str,
        credentials: ConnectorCredentials,
        force_universal: bool = False
    ) -> BaseSaaSConnector:
        """
        URLから自動的に適切なコネクタを作成
        
        Args:
            url: 接続先URL
            credentials: 認証情報
            force_universal: 強制的にUniversalConnectorを使用
        
        Returns:
            適切なSaaSコネクタインスタンス
        """
        
        if not force_universal:
            # SaaSの自動識別
            saas_info = await SaaSIdentifier.identify_saas(url)
            
            if saas_info and saas_info['connector_class']:
                # 専用コネクタが存在する場合
                connector_class = saas_info['connector_class']
                
                if connector_class == ShopifyConnector:
                    # Shopifyの場合
                    parsed = urlparse(url)
                    store_domain = parsed.netloc
                    return ShopifyConnector(store_domain, credentials)
                
                elif connector_class == StripeConnector:
                    # Stripeの場合
                    return StripeConnector(credentials, test_mode=True)
                
                # 他の専用コネクタがあればここに追加
            
            elif saas_info:
                # SaaSは識別できたが専用コネクタがない場合
                print(f"Identified {saas_info['name']} - using Universal Connector")
        
        # UniversalConnectorを使用
        parsed = urlparse(url)
        service_name = saas_info['name'] if saas_info else parsed.netloc
        
        connector = UniversalSaaSConnector(
            service_name=service_name,
            base_url=f"{parsed.scheme}://{parsed.netloc}",
            credentials=credentials
        )
        
        # 初期化
        await connector.initialize()
        
        return connector

class ConnectorRegistry:
    """コネクタレジストリ（プラグインシステム）"""
    
    _connectors: Dict[str, Type[BaseSaaSConnector]] = {}
    
    @classmethod
    def register(cls, saas_type: str, connector_class: Type[BaseSaaSConnector]):
        """コネクタを登録"""
        cls._connectors[saas_type] = connector_class
        
        # SaaSIdentifierのパターンも更新
        if saas_type in SaaSIdentifier.KNOWN_SAAS_PATTERNS:
            SaaSIdentifier.KNOWN_SAAS_PATTERNS[saas_type]['connector_class'] = connector_class
    
    @classmethod
    def get(cls, saas_type: str) -> Optional[Type[BaseSaaSConnector]]:
        """登録されたコネクタを取得"""
        return cls._connectors.get(saas_type)
    
    @classmethod
    def list_available(cls) -> List[str]:
        """利用可能なコネクタ一覧"""
        return list(cls._connectors.keys())

# デフォルトコネクタの登録
ConnectorRegistry.register('shopify', ShopifyConnector)
ConnectorRegistry.register('stripe', StripeConnector)

# 使用例
async def connect_to_any_saas(url: str, api_key: str) -> BaseSaaSConnector:
    """
    任意のSaaSに接続する簡単な関数
    
    Examples:
        # Shopifyに自動接続
        connector = await connect_to_any_saas(
            "https://mystore.myshopify.com",
            "shppa_xxxxx"
        )
        
        # Stripeに自動接続
        connector = await connect_to_any_saas(
            "https://api.stripe.com",
            "sk_test_xxxxx"
        )
        
        # 未知のSaaSに自動接続
        connector = await connect_to_any_saas(
            "https://api.example-saas.com",
            "api_key_xxxxx"
        )
    """
    credentials = ConnectorCredentials(api_key=api_key)
    return await AutoConnectorFactory.create_connector(url, credentials)