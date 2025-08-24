"""
SaaSコネクタ基底クラス
すべてのSaaSコネクタが実装すべきインターフェース
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import asyncio
import time
import random
import structlog
import httpx

class ConnectorType(str, Enum):
    """コネクタタイプ"""
    ECOMMERCE = "ecommerce"
    PAYMENT = "payment"
    COMMUNICATION = "communication"
    CRM = "crm"
    ANALYTICS = "analytics"
    STORAGE = "storage"

class AuthMethod(str, Enum):
    """認証方式"""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    BEARER = "bearer"
    CUSTOM = "custom"

@dataclass
class ConnectorConfig:
    """コネクタ設定"""
    name: str
    type: ConnectorType
    auth_method: AuthMethod
    base_url: str
    api_version: Optional[str] = None
    rate_limit: Optional[int] = 100  # requests per minute
    timeout: int = 30  # seconds
    retry_count: int = 3
    retry_delay: int = 1  # seconds
    
@dataclass
class ConnectorCredentials:
    """認証情報"""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    custom_headers: Optional[Dict[str, str]] = None

@dataclass
class ResourceSnapshot:
    """リソースのスナップショット"""
    resource_id: str
    resource_type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    captured_at: datetime
    checksum: str

@dataclass
class ChangeSet:
    """変更セット"""
    change_id: str
    resource_id: str
    resource_type: str
    changes: List[Dict[str, Any]]
    created_at: datetime
    applied_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None

class BaseSaaSConnector(ABC):
    """
    SaaSコネクタの基底クラス
    すべてのSaaSコネクタはこのクラスを継承して実装する
    """
    
    def __init__(self, config: ConnectorConfig, credentials: ConnectorCredentials):
        self.config = config
        self.credentials = credentials
        self._session = None
        self._rate_limiter = None
        self._initialized = False
        self._logger = structlog.get_logger().bind(connector=self.__class__.__name__, name=self.config.name)
        # Circuit breaker state
        self._cb_failure_count: int = 0
        self._cb_open_until_ts: float = 0.0
        self._cb_threshold: int = 5
        self._cb_open_seconds: int = 30
        
    @abstractmethod
    async def initialize(self) -> bool:
        """
        コネクタの初期化
        認証の確認、接続テストなどを実行
        """
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        認証処理
        APIキー検証、OAuth2トークン取得など
        """
    
    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        接続の検証
        APIエンドポイントへの到達性確認
        """
    
    # === 読み取り操作 ===
    
    @abstractmethod
    async def list_resources(
        self,
        resource_type: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        リソース一覧の取得
        """
    
    @abstractmethod
    async def get_resource(
        self,
        resource_type: str,
        resource_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        単一リソースの取得
        """
    
    @abstractmethod
    async def search_resources(
        self,
        resource_type: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        リソースの検索
        """
    
    # === スナップショット・プレビュー ===
    
    @abstractmethod
    async def create_snapshot(
        self,
        resource_type: str,
        resource_id: str
    ) -> ResourceSnapshot:
        """
        リソースのスナップショット作成
        現在の状態を保存
        """
    
    @abstractmethod
    async def generate_preview(
        self,
        snapshot: ResourceSnapshot,
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        変更のプレビュー生成
        実際の変更は行わない
        """
    
    @abstractmethod
    async def validate_changes(
        self,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        変更の検証
        返り値: (valid: bool, errors: List[str])
        """
    
    # === 変更操作 ===
    
    @abstractmethod
    async def apply_changes(
        self,
        resource_type: str,
        resource_id: str,
        changes: Dict[str, Any],
        dry_run: bool = False
    ) -> ChangeSet:
        """
        変更の適用
        dry_run=Trueの場合はシミュレーションのみ
        """
    
    @abstractmethod
    async def create_resource(
        self,
        resource_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        新規リソースの作成
        """
    
    @abstractmethod
    async def update_resource(
        self,
        resource_type: str,
        resource_id: str,
        data: Dict[str, Any],
        partial: bool = True
    ) -> Dict[str, Any]:
        """
        リソースの更新
        partial=Trueの場合は部分更新
        """
    
    @abstractmethod
    async def delete_resource(
        self,
        resource_type: str,
        resource_id: str,
        soft_delete: bool = True
    ) -> bool:
        """
        リソースの削除
        soft_delete=Trueの場合は論理削除
        """
    
    # === ロールバック ===
    
    @abstractmethod
    async def rollback(
        self,
        change_set: ChangeSet
    ) -> bool:
        """
        変更のロールバック
        """
    
    @abstractmethod
    async def can_rollback(
        self,
        change_set: ChangeSet
    ) -> bool:
        """
        ロールバック可能かチェック
        """
    
    # === Webhook ===
    
    async def register_webhook(
        self,
        event_types: List[str],
        callback_url: str
    ) -> str:
        """
        Webhookの登録
        返り値: webhook_id
        """
        return ""
    
    async def unregister_webhook(
        self,
        webhook_id: str
    ) -> bool:
        """
        Webhookの解除
        """
        return True
    
    async def process_webhook(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> bool:
        """
        Webhookペイロードの処理
        """
        return True
    
    # === バッチ操作 ===
    
    async def batch_read(
        self,
        operations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        バッチ読み取り
        """
        results = []
        for op in operations:
            result = await self.get_resource(
                op["resource_type"],
                op["resource_id"]
            )
            results.append(result)
        return results
    
    async def batch_write(
        self,
        operations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        バッチ書き込み
        """
        results = []
        for op in operations:
            if op["action"] == "create":
                result = await self.create_resource(
                    op["resource_type"],
                    op["data"]
                )
            elif op["action"] == "update":
                result = await self.update_resource(
                    op["resource_type"],
                    op["resource_id"],
                    op["data"]
                )
            elif op["action"] == "delete":
                result = await self.delete_resource(
                    op["resource_type"],
                    op["resource_id"]
                )
            else:
                result = {"error": f"Unknown action: {op['action']}"}
            results.append(result)
        return results
    
    # === ストリーミング ===
    
    async def stream_resources(
        self,
        resource_type: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        リソースのストリーミング取得
        """
        offset = 0
        limit = 100
        while True:
            resources = await self.list_resources(
                resource_type,
                filters,
                limit,
                offset
            )
            if not resources:
                break
            for resource in resources:
                yield resource
            offset += limit
    
    # === ユーティリティ ===
    
    async def _resilient_request(
        self,
        method: str,
        url: str,
        *,
        retry_count: Optional[int] = None,
        retry_delay: Optional[float] = None,
        retry_on_status: Optional[List[int]] = None,
        **kwargs,
    ) -> httpx.Response:
        """HTTP要求にリトライ/バックオフ/サーキットブレーカを適用して実行する。
        - 429/5xxでリトライ
        - 失敗が閾値を超えると一定時間オープン
        """
        # Circuit breaker check
        now = time.time()
        if self._cb_open_until_ts and now < self._cb_open_until_ts:
            raise RuntimeError("circuit_open")
        retry_count = self.config.retry_count if retry_count is None else retry_count
        base_delay = self.config.retry_delay if retry_delay is None else retry_delay
        retry_on_status = retry_on_status or [429, 500, 502, 503, 504]
        attempt = 0
        while True:
            try:
                resp = await self._session.request(method, url, **kwargs)
                if resp.status_code in retry_on_status:
                    # Honor Retry-After if present
                    ra = resp.headers.get('Retry-After')
                    delay = float(ra) if ra else None
                    raise httpx.HTTPStatusError("retryable status", request=resp.request, response=resp)
                # Success path
                self._cb_failure_count = 0
                return resp
            except Exception as e:
                attempt += 1
                self._cb_failure_count += 1
                self._logger.warning(
                    "request_failed",
                    method=method,
                    url=url,
                    attempt=attempt,
                    error=str(e)
                )
                if attempt > retry_count:
                    # Open circuit if persistent failures
                    if self._cb_failure_count >= self._cb_threshold:
                        self._cb_open_until_ts = time.time() + self._cb_open_seconds
                        self._logger.error("circuit_opened", open_seconds=self._cb_open_seconds)
                    raise
                # Exponential backoff with jitter
                sleep_sec = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.2)
                await asyncio.sleep(sleep_sec)

    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        レート制限の状態取得
        """
        return {
            "limit": self.config.rate_limit,
            "remaining": self.config.rate_limit,
            "reset_at": datetime.utcnow()
        }
    
    async def get_api_status(self) -> Dict[str, Any]:
        """
        API状態の取得
        """
        return {
            "status": "operational",
            "latency_ms": 0,
            "timestamp": datetime.utcnow()
        }
    
    async def close(self):
        """
        コネクタのクローズ
        """
        if self._session:
            await self._session.close()
        self._initialized = False
    
    def __str__(self) -> str:
        return f"{self.config.name} Connector ({self.config.type})"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.config.name}', type='{self.config.type}')>"