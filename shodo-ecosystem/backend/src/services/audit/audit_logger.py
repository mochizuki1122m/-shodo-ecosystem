"""
監査ログシステム

改竄耐性のある監査ログを実装。
ハッシュチェーンと署名により、ログの完全性を保証。
"""

import json
import hashlib
import hmac
import time
import asyncio
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
import logging

import aioredis
from pydantic import BaseModel, Field
import structlog
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

from ...utils.config import settings

# 構造化ログ
logger = structlog.get_logger()

class AuditEventType(str, Enum):
    """監査イベントタイプ"""
    # 認証関連
    LOGIN_ATTEMPT = "login_attempt"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    
    # LPR関連
    LPR_ISSUED = "lpr_issued"
    LPR_VERIFIED = "lpr_verified"
    LPR_INVALID = "lpr_invalid"
    LPR_REVOKED = "lpr_revoked"
    LPR_EXPIRED = "lpr_expired"
    
    # アクセス制御
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGED = "permission_changed"
    
    # データ操作
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # セキュリティイベント
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SECURITY_VIOLATION = "security_violation"
    
    # システムイベント
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"

class AuditSeverity(str, Enum):
    """監査イベントの重要度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class AuditLogEntry:
    """監査ログエントリ"""
    # 基本フィールド（5W1H）
    who: str  # 誰が（ユーザーID、システムIDなど）
    when: datetime  # いつ
    what: str  # 何を（リソース、データなど）
    where: str  # どこで（エンドポイント、サービスなど）
    why: str  # なぜ（目的、理由）
    how: str  # どのように（メソッド、プロトコルなど）
    
    # 追加フィールド
    event_type: AuditEventType
    severity: AuditSeverity
    result: str  # success, failure, partial
    correlation_id: str
    session_id: Optional[str] = None
    
    # メタデータ
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    
    # データ
    details: Optional[Dict[str, Any]] = None
    
    # チェーン情報
    sequence_number: Optional[int] = None
    previous_hash: Optional[str] = None
    entry_hash: Optional[str] = None
    signature: Optional[str] = None
    
    def calculate_hash(self) -> str:
        """エントリのハッシュを計算"""
        # ハッシュ対象のデータを準備
        hash_data = {
            "sequence_number": self.sequence_number,
            "previous_hash": self.previous_hash,
            "who": self.who,
            "when": self.when.isoformat(),
            "what": self.what,
            "where": self.where,
            "why": self.why,
            "how": self.how,
            "event_type": self.event_type,
            "severity": self.severity,
            "result": self.result,
            "correlation_id": self.correlation_id,
        }
        
        # 安定したJSON表現
        json_str = json.dumps(hash_data, sort_keys=True)
        
        # SHA-256ハッシュ
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        data = asdict(self)
        data["when"] = self.when.isoformat()
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        return data

class AuditLogger:
    """監査ログ記録システム"""
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.signing_key: Optional[rsa.RSAPrivateKey] = None
        self.verification_key: Optional[rsa.RSAPublicKey] = None
        self.sequence_counter = 0
        self.last_hash = "0" * 64  # 初期ハッシュ
        self._init_keys()
        self._lock = asyncio.Lock()
    
    def _init_keys(self):
        """署名鍵の初期化"""
        # 本番環境では環境変数やKMSから鍵を取得
        # ここではデモ用に新規生成
        self.signing_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self.verification_key = self.signing_key.public_key()
    
    async def connect_redis(self, redis_url: str):
        """Redis接続"""
        self.redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # 最後のシーケンス番号とハッシュを復元
        await self._restore_chain_state()
    
    async def log(
        self,
        event_type: AuditEventType,
        who: str,
        what: str,
        where: str,
        why: str = "",
        how: str = "",
        result: str = "success",
        severity: Optional[AuditSeverity] = None,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """監査ログを記録"""
        
        # デフォルト値の設定
        if severity is None:
            severity = self._determine_severity(event_type, result)
        
        if correlation_id is None:
            import secrets
            correlation_id = secrets.token_urlsafe(16)
        
        # エントリ作成
        entry = AuditLogEntry(
            who=who,
            when=datetime.now(timezone.utc),
            what=what,
            where=where,
            why=why or "automated",
            how=how or "system",
            event_type=event_type,
            severity=severity,
            result=result,
            correlation_id=correlation_id,
            session_id=session_id,
            client_ip=client_ip,
            user_agent=user_agent,
            details=details,
        )
        
        # ハッシュチェーンの更新（排他制御）
        async with self._lock:
            # シーケンス番号の割り当て
            self.sequence_counter += 1
            entry.sequence_number = self.sequence_counter
            entry.previous_hash = self.last_hash
            
            # エントリハッシュの計算
            entry.entry_hash = entry.calculate_hash()
            
            # デジタル署名
            entry.signature = self._sign_entry(entry)
            
            # 次のエントリ用にハッシュを更新
            self.last_hash = entry.entry_hash
            
            # 永続化
            await self._persist_entry(entry)
        
        # 構造化ログ出力
        logger.info(
            f"AUDIT: {event_type.value}",
            who=who,
            what=what,
            where=where,
            result=result,
            correlation_id=correlation_id,
        )
        
        # リアルタイム通知（重要なイベントの場合）
        if severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
            await self._send_alert(entry)
        
        return entry
    
    async def verify_chain(
        self,
        start_sequence: int = 1,
        end_sequence: Optional[int] = None
    ) -> Tuple[bool, List[str]]:
        """ハッシュチェーンの検証"""
        
        errors = []
        
        if end_sequence is None:
            end_sequence = self.sequence_counter
        
        previous_hash = "0" * 64 if start_sequence == 1 else None
        
        for seq in range(start_sequence, end_sequence + 1):
            entry = await self._get_entry(seq)
            
            if not entry:
                errors.append(f"Missing entry: sequence {seq}")
                continue
            
            # 前のハッシュとの連続性チェック
            if previous_hash and entry.previous_hash != previous_hash:
                errors.append(
                    f"Chain broken at sequence {seq}: "
                    f"expected previous_hash {previous_hash}, "
                    f"got {entry.previous_hash}"
                )
            
            # エントリハッシュの検証
            calculated_hash = entry.calculate_hash()
            if entry.entry_hash != calculated_hash:
                errors.append(
                    f"Hash mismatch at sequence {seq}: "
                    f"expected {calculated_hash}, got {entry.entry_hash}"
                )
            
            # デジタル署名の検証
            if not self._verify_signature(entry):
                errors.append(f"Invalid signature at sequence {seq}")
            
            previous_hash = entry.entry_hash
        
        return len(errors) == 0, errors
    
    async def search(
        self,
        event_type: Optional[AuditEventType] = None,
        who: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """監査ログを検索"""
        
        if not self.redis_client:
            return []
        
        # Redis Streamsから検索
        stream_key = "audit:log"
        
        # 時間範囲の設定
        if start_time:
            start_id = f"{int(start_time.timestamp() * 1000)}-0"
        else:
            start_id = "-"
        
        if end_time:
            end_id = f"{int(end_time.timestamp() * 1000)}-0"
        else:
            end_id = "+"
        
        # ストリームから読み取り
        entries = await self.redis_client.xrange(
            stream_key,
            min=start_id,
            max=end_id,
            count=limit
        )
        
        results = []
        for entry_id, data in entries:
            entry_dict = json.loads(data.get("entry", "{}"))
            entry = self._dict_to_entry(entry_dict)
            
            # フィルタリング
            if event_type and entry.event_type != event_type:
                continue
            if who and entry.who != who:
                continue
            if correlation_id and entry.correlation_id != correlation_id:
                continue
            
            results.append(entry)
        
        return results
    
    async def export(
        self,
        format: str = "json",
        start_sequence: int = 1,
        end_sequence: Optional[int] = None,
    ) -> str:
        """監査ログをエクスポート"""
        
        if end_sequence is None:
            end_sequence = self.sequence_counter
        
        entries = []
        for seq in range(start_sequence, end_sequence + 1):
            entry = await self._get_entry(seq)
            if entry:
                entries.append(entry.to_dict())
        
        if format == "json":
            return json.dumps(entries, indent=2)
        elif format == "csv":
            import csv
            import io
            
            if not entries:
                return ""
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=entries[0].keys())
            writer.writeheader()
            writer.writerows(entries)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    # ===== プライベートメソッド =====
    
    def _determine_severity(
        self,
        event_type: AuditEventType,
        result: str
    ) -> AuditSeverity:
        """イベントタイプと結果から重要度を決定"""
        
        if result == "failure":
            if event_type in [
                AuditEventType.LOGIN_FAILURE,
                AuditEventType.ACCESS_DENIED,
            ]:
                return AuditSeverity.WARNING
            else:
                return AuditSeverity.ERROR
        
        if event_type in [
            AuditEventType.SECURITY_VIOLATION,
            AuditEventType.SUSPICIOUS_ACTIVITY,
        ]:
            return AuditSeverity.CRITICAL
        
        if event_type in [
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.LPR_INVALID,
        ]:
            return AuditSeverity.WARNING
        
        return AuditSeverity.INFO
    
    def _sign_entry(self, entry: AuditLogEntry) -> str:
        """エントリにデジタル署名"""
        
        if not self.signing_key:
            return ""
        
        # 署名対象のデータ
        message = f"{entry.sequence_number}:{entry.entry_hash}".encode()
        
        # RSA-PSS署名
        signature = self.signing_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Base64エンコード
        import base64
        return base64.b64encode(signature).decode('utf-8')
    
    def _verify_signature(self, entry: AuditLogEntry) -> bool:
        """デジタル署名を検証"""
        
        if not self.verification_key or not entry.signature:
            return False
        
        try:
            # 署名対象のデータ
            message = f"{entry.sequence_number}:{entry.entry_hash}".encode()
            
            # Base64デコード
            import base64
            signature = base64.b64decode(entry.signature)
            
            # 署名検証
            self.verification_key.verify(
                signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception:
            return False
    
    async def _persist_entry(self, entry: AuditLogEntry):
        """エントリを永続化"""
        
        if not self.redis_client:
            return
        
        # Redis Streamsに追加（append-only）
        stream_key = "audit:log"
        await self.redis_client.xadd(
            stream_key,
            {"entry": json.dumps(entry.to_dict())},
            maxlen=1000000  # 最大100万エントリ
        )
        
        # シーケンス番号でインデックス
        index_key = f"audit:entry:{entry.sequence_number}"
        await self.redis_client.set(
            index_key,
            json.dumps(entry.to_dict()),
            ex=86400 * 30  # 30日間保持
        )
        
        # チェーン状態を保存
        await self._save_chain_state()
    
    async def _get_entry(self, sequence_number: int) -> Optional[AuditLogEntry]:
        """シーケンス番号でエントリを取得"""
        
        if not self.redis_client:
            return None
        
        index_key = f"audit:entry:{sequence_number}"
        data = await self.redis_client.get(index_key)
        
        if data:
            entry_dict = json.loads(data)
            return self._dict_to_entry(entry_dict)
        
        return None
    
    def _dict_to_entry(self, data: Dict[str, Any]) -> AuditLogEntry:
        """辞書からエントリを復元"""
        
        # datetimeの復元
        if isinstance(data.get("when"), str):
            data["when"] = datetime.fromisoformat(data["when"])
        
        # Enumの復元
        if isinstance(data.get("event_type"), str):
            data["event_type"] = AuditEventType(data["event_type"])
        if isinstance(data.get("severity"), str):
            data["severity"] = AuditSeverity(data["severity"])
        
        return AuditLogEntry(**data)
    
    async def _save_chain_state(self):
        """チェーン状態を保存"""
        
        if not self.redis_client:
            return
        
        state = {
            "sequence_counter": self.sequence_counter,
            "last_hash": self.last_hash,
        }
        
        await self.redis_client.set(
            "audit:chain:state",
            json.dumps(state)
        )
    
    async def _restore_chain_state(self):
        """チェーン状態を復元"""
        
        if not self.redis_client:
            return
        
        data = await self.redis_client.get("audit:chain:state")
        
        if data:
            state = json.loads(data)
            self.sequence_counter = state["sequence_counter"]
            self.last_hash = state["last_hash"]
            logger.info(
                "Audit chain state restored",
                sequence=self.sequence_counter,
            )
    
    async def _send_alert(self, entry: AuditLogEntry):
        """重要なイベントのアラート送信"""
        
        # TODO: メール、Slack、PagerDuty等への通知
        logger.warning(
            f"ALERT: {entry.event_type.value}",
            severity=entry.severity.value,
            who=entry.who,
            what=entry.what,
        )

# シングルトンインスタンス
audit_logger = AuditLogger()

async def init_audit_logger():
    """監査ログシステムの初期化"""
    await audit_logger.connect_redis(settings.redis_url)
    logger.info("Audit logger initialized")

async def get_audit_logger() -> AuditLogger:
    """監査ログインスタンスを取得"""
    return audit_logger