"""
データベース統合版APIキー管理システム
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload


from ...models.api_key import APIKey, APIKeyAuditLog, APIKeyUsage, ServiceType, APIKeyStatus


from .api_key_manager import APIKeyManager, APIKeyConfig

class DatabaseAPIKeyManager(APIKeyManager):
    """
    データベース統合版APIキーマネージャー
    
    APIキーマネージャーを拡張し、PostgreSQLでの永続化を実装
    """
    
    def __init__(self, db_session: AsyncSession, encryption_key: Optional[str] = None):
        super().__init__(encryption_key)
        self.db = db_session
    
    async def _persist_key(self, config: APIKeyConfig, user_id: str, connection_id: Optional[str] = None):
        """
        APIキーをデータベースに保存
        
        Args:
            config: APIキー設定
            user_id: ユーザーID
            connection_id: サービス接続ID（オプション）
        """
        # 既存のキーを確認
        existing = await self.db.execute(
            select(APIKey).where(
                and_(
                    APIKey.user_id == user_id,
                    APIKey.service == config.service.value,
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            )
        )
        existing_key = existing.scalar_one_or_none()
        
        # 既存のキーがある場合は無効化
        if existing_key:
            existing_key.status = APIKeyStatus.REVOKED
            await self._audit_log(
                api_key_id=existing_key.id,
                user_id=user_id,
                action="revoke",
                details={"reason": "replaced_by_new_key"}
            )
        
        # 新しいキーを作成
        api_key = APIKey(
            key_id=config.key_id,
            service=config.service.value,
            status=APIKeyStatus.ACTIVE,
            encrypted_key=config.encrypted_key,
            encrypted_refresh_token=config.metadata.get("refresh_token"),
            user_id=user_id,
            service_connection_id=connection_id,
            expires_at=config.expires_at,
            last_refreshed_at=datetime.utcnow() if config.expires_at else None,
            auto_renew=config.auto_renew,
            permissions=config.permissions,
            metadata=config.metadata
        )
        
        self.db.add(api_key)
        await self.db.flush()
        
        # 監査ログを記録
        await self._audit_log(
            api_key_id=api_key.id,
            user_id=user_id,
            action="create",
            details={"service": config.service.value}
        )
        
        await self.db.commit()
        
        # キャッシュに追加
        self.key_cache[config.key_id] = config
    
    async def _load_key(self, key_id: str) -> Optional[APIKeyConfig]:
        """
        データベースからAPIキーをロード
        
        Args:
            key_id: キーID
            
        Returns:
            APIキー設定
        """
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_id == key_id)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return None
        
        # APIKeyConfigに変換
        config = APIKeyConfig(
            service=ServiceType(api_key.service),
            key_id=api_key.key_id,
            encrypted_key=api_key.encrypted_key,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            auto_renew=api_key.auto_renew,
            permissions=api_key.permissions,
            metadata=api_key.metadata
        )
        
        # リフレッシュトークンがある場合は追加
        if api_key.encrypted_refresh_token:
            config.metadata["refresh_token"] = api_key.encrypted_refresh_token
        
        # キャッシュに追加
        self.key_cache[key_id] = config
        
        return config
    
    async def get_active_key_for_user(
        self,
        user_id: str,
        service: ServiceType
    ) -> Optional[str]:
        """
        ユーザーのアクティブなAPIキーを取得
        
        Args:
            user_id: ユーザーID
            service: サービスタイプ
            
        Returns:
            復号化されたAPIキー
        """
        result = await self.db.execute(
            select(APIKey).where(
                and_(
                    APIKey.user_id == user_id,
                    APIKey.service == service.value,
                    APIKey.status == APIKeyStatus.ACTIVE
                )
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return None
        
        # 有効期限チェック
        if api_key.is_expired():
            if api_key.auto_renew:
                # 自動更新
                config = await self._load_key(api_key.key_id)
                if config:
                    updated_config = await self.refresh_key(api_key.key_id)
                    return self._decrypt_key(updated_config.encrypted_key)
            else:
                # 期限切れとして記録
                api_key.status = APIKeyStatus.EXPIRED
                await self.db.commit()
                return None
        
        # 使用回数をインクリメント
        api_key.increment_usage()
        await self.db.commit()
        
        return self._decrypt_key(api_key.encrypted_key)
    
    async def list_user_keys(self, user_id: str) -> List[Dict]:
        """
        ユーザーのすべてのAPIキーを取得
        
        Args:
            user_id: ユーザーID
            
        Returns:
            APIキーのリスト
        """
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .options(selectinload(APIKey.service_connection))
            .order_by(APIKey.created_at.desc())
        )
        api_keys = result.scalars().all()
        
        return [
            {
                "id": key.id,
                "key_id": key.key_id,
                "service": key.service,
                "status": key.status,
                "created_at": key.created_at.isoformat(),
                "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                "auto_renew": key.auto_renew,
                "usage_count": key.usage_count,
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                "connection": {
                    "name": key.service_connection.service_name,
                    "account": key.service_connection.service_account_name
                } if key.service_connection else None
            }
            for key in api_keys
        ]
    
    async def revoke_key_by_id(self, key_id: str, user_id: str, reason: str = "user_requested"):
        """
        APIキーを無効化
        
        Args:
            key_id: キーID
            user_id: ユーザーID
            reason: 無効化理由
        """
        result = await self.db.execute(
            select(APIKey).where(
                and_(
                    APIKey.key_id == key_id,
                    APIKey.user_id == user_id
                )
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            raise ValueError(f"Key not found: {key_id}")
        
        # ステータスを更新
        api_key.status = APIKeyStatus.REVOKED
        
        # 監査ログを記録
        await self._audit_log(
            api_key_id=api_key.id,
            user_id=user_id,
            action="revoke",
            details={"reason": reason}
        )
        
        # サービス側でも無効化（可能な場合）
        await self.revoke_key(key_id)
        
        await self.db.commit()
        
        # キャッシュから削除
        if key_id in self.key_cache:
            del self.key_cache[key_id]
    
    async def _audit_log(
        self,
        api_key_id: str,
        user_id: str,
        action: str,
        details: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        監査ログを記録
        
        Args:
            api_key_id: APIキーID
            user_id: ユーザーID
            action: アクション
            details: 詳細情報
            success: 成功フラグ
            error_message: エラーメッセージ
            ip_address: IPアドレス
            user_agent: ユーザーエージェント
        """
        audit_log = APIKeyAuditLog(
            api_key_id=api_key_id,
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            success=success,
            error_message=error_message
        )
        
        self.db.add(audit_log)
        await self.db.flush()
    
    async def log_usage(
        self,
        api_key_id: str,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """
        API使用ログを記録
        
        Args:
            api_key_id: APIキーID
            endpoint: エンドポイント
            method: HTTPメソッド
            status_code: ステータスコード
            response_time_ms: レスポンス時間
            error_message: エラーメッセージ
            metadata: メタデータ
        """
        # APIキーを取得
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_id == api_key_id)
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return
        
        # 使用ログを記録
        usage_log = APIKeyUsage(
            api_key_id=api_key.id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            error_type="api_error" if error_message else None,
            error_message=error_message,
            metadata=metadata or {}
        )
        
        self.db.add(usage_log)
        
        # エラーの場合はAPIキーにも記録
        if error_message:
            api_key.record_error(error_message)
        
        await self.db.commit()
    
    async def check_and_refresh_expiring_keys(self):
        """
        期限切れ間近のキーをチェックして自動更新
        """
        # 24時間以内に期限切れになるキーを取得
        expiry_threshold = datetime.utcnow() + timedelta(hours=24)
        
        result = await self.db.execute(
            select(APIKey).where(
                and_(
                    APIKey.status == APIKeyStatus.ACTIVE,
                    APIKey.auto_renew == True,
                    APIKey.expires_at != None,
                    APIKey.expires_at <= expiry_threshold
                )
            )
        )
        expiring_keys = result.scalars().all()
        
        for api_key in expiring_keys:
            try:
                # キーをリフレッシュ
                config = await self._load_key(api_key.key_id)
                if config:
                    await self.refresh_key(api_key.key_id)
                    
                    # 監査ログ
                    await self._audit_log(
                        api_key_id=api_key.id,
                        user_id=api_key.user_id,
                        action="auto_refresh",
                        details={"old_expiry": api_key.expires_at.isoformat()}
                    )
            except Exception as e:
                # エラーを記録
                api_key.record_error(str(e))
                await self._audit_log(
                    api_key_id=api_key.id,
                    user_id=api_key.user_id,
                    action="auto_refresh",
                    success=False,
                    error_message=str(e)
                )
        
        await self.db.commit()
    
    async def get_usage_statistics(
        self,
        user_id: str,
        service: Optional[ServiceType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        使用統計を取得
        
        Args:
            user_id: ユーザーID
            service: サービスタイプ（オプション）
            start_date: 開始日（オプション）
            end_date: 終了日（オプション）
            
        Returns:
            使用統計
        """
        # クエリを構築
        query = select(APIKeyUsage).join(APIKey).where(APIKey.user_id == user_id)
        
        if service:
            query = query.where(APIKey.service == service.value)
        
        if start_date:
            query = query.where(APIKeyUsage.created_at >= start_date)
        
        if end_date:
            query = query.where(APIKeyUsage.created_at <= end_date)
        
        result = await self.db.execute(query)
        usage_logs = result.scalars().all()
        
        # 統計を計算
        total_requests = len(usage_logs)
        successful_requests = sum(1 for log in usage_logs if 200 <= (log.status_code or 0) < 300)
        failed_requests = total_requests - successful_requests
        avg_response_time = sum(log.response_time_ms or 0 for log in usage_logs) / max(total_requests, 1)
        
        # エンドポイント別統計
        endpoint_stats = {}
        for log in usage_logs:
            if log.endpoint not in endpoint_stats:
                endpoint_stats[log.endpoint] = {"count": 0, "errors": 0}
            endpoint_stats[log.endpoint]["count"] += 1
            if log.error_message:
                endpoint_stats[log.endpoint]["errors"] += 1
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / max(total_requests, 1)) * 100,
            "avg_response_time_ms": avg_response_time,
            "endpoint_stats": endpoint_stats,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
        }