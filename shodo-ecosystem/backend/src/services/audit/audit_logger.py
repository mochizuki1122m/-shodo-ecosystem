"""
監査ログシステム
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from ...models.models import AuditLog

logger = logging.getLogger(__name__)

class AuditLogger:
    """監査ログクラス"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log(
        self,
        user_id: Optional[str],
        action: str,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success"
    ) -> AuditLog:
        """監査ログ記録"""
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            created_at=datetime.utcnow()
        )
        
        self.db.add(audit_log)
        await self.db.commit()
        
        # ログ出力
        logger.info(f"Audit log: {action} by {user_id} on {resource}/{resource_id}")
        
        return audit_log

# グローバル監査ログ関数
_audit_logger: Optional[AuditLogger] = None

async def init_audit_logger(db: AsyncSession):
    """監査ログ初期化"""
    global _audit_logger
    _audit_logger = AuditLogger(db)

async def log_action(
    user_id: Optional[str],
    action: str,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success"
):
    """アクション記録"""
    if _audit_logger:
        await _audit_logger.log(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status
        )

async def log_error(
    user_id: Optional[str],
    action: str,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """エラー記録"""
    await log_action(
        user_id=user_id,
        action=action,
        resource=resource,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        status="error"
    )