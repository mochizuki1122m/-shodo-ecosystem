"""
Audit Logger Service
MUST: Complete audit trail with tamper resistance
"""

import json
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum
import structlog

from ...core.config import settings

logger = structlog.get_logger()

class AuditEventType(Enum):
    """Audit event types"""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REVOKED = "token_revoked"
    
    # LPR Operations
    LPR_ISSUED = "lpr_issued"
    LPR_VERIFIED = "lpr_verified"
    LPR_REVOKED = "lpr_revoked"
    LPR_OPERATION = "lpr_operation"
    
    # Data Operations
    DATA_CREATE = "data_create"
    DATA_READ = "data_read"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # Security Events
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SECURITY_VIOLATION = "security_violation"
    
    # System Events
    CONFIG_CHANGE = "config_change"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    ERROR = "error"

class AuditSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AuditLogEntry(dict):
    """シンプルな辞書ベースのログエントリ型（テスト互換用）"""
    pass

class AuditLogger:
    """
    Centralized audit logging with tamper resistance
    
    MUST requirements:
    - Immutable logs with cryptographic integrity
    - Correlation ID tracking
    - PII masking
    - 13+ month retention
    - SIEM integration ready
    """
    
    def __init__(self, storage_backend=None):
        self.storage = storage_backend
        self.signing_key = settings.secret_key.get_secret_value().encode()
        self.chain_hash = None  # For hash chaining
    
    async def log(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        severity: str = "INFO"
    ) -> str:
        """
        Create an audit log entry
        
        Returns:
            Audit log ID
        """
        
        # Create audit entry
        entry = {
            "id": self._generate_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "user_id": user_id,
            "correlation_id": correlation_id,
            "success": success,
            "severity": severity,
            "details": details or {},
            "metadata": {
                "ip_address": self._mask_ip(ip_address) if ip_address else None,
                "user_agent": user_agent,
                "service": settings.service_name,
                "environment": settings.environment,
                "version": settings.app_version
            }
        }
        
        # Add integrity fields
        entry["hash"] = self._calculate_hash(entry)
        entry["signature"] = self._sign_entry(entry)
        
        # Chain hash for tamper detection
        if self.chain_hash:
            entry["previous_hash"] = self.chain_hash
        self.chain_hash = entry["hash"]
        
        # Store the entry
        await self._store_entry(entry)
        
        # Log to structured logger
        logger.info(
            "Audit event",
            audit_id=entry["id"],
            event_type=event_type.value,
            user_id=user_id,
            correlation_id=correlation_id,
            success=success
        )
        
        # Send to SIEM if configured
        if settings.environment == "production":
            await self._send_to_siem(entry)
        
        return entry["id"]
    
    async def log_authentication(
        self,
        success: bool,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        correlation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        failure_reason: Optional[str] = None
    ):
        """Log authentication event"""
        
        event_type = AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILURE
        
        details = {
            "username": username,
            "authentication_method": "password"
        }
        
        if failure_reason:
            details["failure_reason"] = failure_reason
        
        await self.log(
            event_type=event_type,
            user_id=user_id,
            correlation_id=correlation_id,
            details=details,
            ip_address=ip_address,
            success=success,
            severity="INFO" if success else "WARNING"
        )
    
    async def log_data_access(
        self,
        operation: str,
        resource_type: str,
        resource_id: str,
        user_id: str,
        correlation_id: Optional[str] = None,
        success: bool = True,
        data_classification: str = "internal"
    ):
        """Log data access event"""
        
        event_map = {
            "create": AuditEventType.DATA_CREATE,
            "read": AuditEventType.DATA_READ,
            "update": AuditEventType.DATA_UPDATE,
            "delete": AuditEventType.DATA_DELETE,
            "export": AuditEventType.DATA_EXPORT
        }
        
        event_type = event_map.get(operation.lower(), AuditEventType.DATA_READ)
        
        details = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "operation": operation,
            "data_classification": data_classification
        }
        
        await self.log(
            event_type=event_type,
            user_id=user_id,
            correlation_id=correlation_id,
            details=details,
            success=success,
            severity="INFO" if success else "ERROR"
        )
    
    async def log_security_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        threat_level: str = "medium",
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ):
        """Log security event"""
        
        severity_map = {
            "low": "WARNING",
            "medium": "ERROR",
            "high": "CRITICAL",
            "critical": "CRITICAL"
        }
        
        await self.log(
            event_type=AuditEventType.SECURITY_VIOLATION,
            user_id=user_id,
            correlation_id=correlation_id,
            details={
                "security_event": event_type,
                "threat_level": threat_level,
                **(details or {})
            },
            ip_address=ip_address,
            success=False,
            severity=severity_map.get(threat_level, "ERROR")
        )
    
    async def query(
        self,
        start_time: datetime,
        end_time: datetime,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Query audit logs
        
        MUST: Support 13+ month retention
        """
        
        # Implementation depends on storage backend
        # This is a placeholder
        
        filters = {
            "timestamp": {"$gte": start_time, "$lte": end_time}
        }
        
        if event_types:
            filters["event_type"] = {"$in": [e.value for e in event_types]}
        
        if user_id:
            filters["user_id"] = user_id
        
        if correlation_id:
            filters["correlation_id"] = correlation_id
        
        # Query from storage
        # results = await self.storage.query(filters, limit=limit)
        
        return []
    
    async def verify_integrity(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Verify audit log integrity
        
        Checks:
        - Hash validity
        - Signature validity
        - Chain integrity
        """
        
        logs = await self.query(start_time, end_time, limit=10000)
        
        total = len(logs)
        valid = 0
        invalid = 0
        broken_chain = 0
        
        previous_hash = None
        
        for log in logs:
            # Verify hash
            calculated_hash = self._calculate_hash(log)
            if calculated_hash != log.get("hash"):
                invalid += 1
                continue
            
            # Verify signature
            if not self._verify_signature(log):
                invalid += 1
                continue
            
            # Verify chain
            if previous_hash and log.get("previous_hash") != previous_hash:
                broken_chain += 1
            
            valid += 1
            previous_hash = log.get("hash")
        
        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "broken_chain": broken_chain,
            "integrity": valid == total and broken_chain == 0
        }
    
    def _generate_id(self) -> str:
        """Generate unique audit log ID"""
        import uuid
        return f"audit_{uuid.uuid4().hex}"
    
    def _calculate_hash(self, entry: Dict) -> str:
        """Calculate entry hash for integrity"""
        # Remove hash and signature fields for calculation
        data = {k: v for k, v in entry.items() if k not in ["hash", "signature"]}
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _sign_entry(self, entry: Dict) -> str:
        """Sign entry for authenticity"""
        data = entry.get("hash", "")
        signature = hmac.new(
            self.signing_key,
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _verify_signature(self, entry: Dict) -> bool:
        """Verify entry signature"""
        expected = self._sign_entry(entry)
        return hmac.compare_digest(expected, entry.get("signature", ""))
    
    def _mask_ip(self, ip: str) -> str:
        """Mask IP address for privacy"""
        if "." in ip:  # IPv4
            parts = ip.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.xxx.xxx"
        elif ":" in ip:  # IPv6
            parts = ip.split(":")
            if len(parts) >= 4:
                return f"{parts[0]}:{parts[1]}:xxxx:xxxx::"
        return "xxx.xxx.xxx.xxx"
    
    async def _store_entry(self, entry: Dict):
        """Store audit entry"""
        if self.storage:
            await self.storage.store(entry)
        else:
            # Fallback to file
            with open("/var/log/shodo/audit.jsonl", "a") as f:
                f.write(json.dumps(entry) + "\n")
    
    async def _send_to_siem(self, entry: Dict):
        """Send to SIEM system"""
        # Implementation for SIEM integration
        # e.g., Splunk, ELK, Datadog

# Singleton instance
audit_logger = None

async def get_audit_logger() -> AuditLogger:
    """Get audit logger instance"""
    global audit_logger
    if audit_logger is None:
        # Initialize with storage backend
        # storage = await get_audit_storage()
        audit_logger = AuditLogger()
    return audit_logger

async def init_audit_logger():
    """Initialize audit logger at startup"""
    global audit_logger
    audit_logger = AuditLogger()
    await audit_logger.log(
        event_type=AuditEventType.SERVICE_START,
        details={
            "service": settings.service_name,
            "version": settings.app_version,
            "environment": settings.environment
        }
    )
    logger.info("Audit logger initialized")