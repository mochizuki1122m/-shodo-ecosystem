"""
LPR (Limited Proxy Rights) システム実装
"""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import json
import uuid

from sqlalchemy import select

from ...models.models import User, Session  # noqa: F401
from ...core.exceptions import AuthenticationException, AuthorizationException
from ...core.security import JWTManager

class LPRToken:
    """LPRトークンクラス"""
    
    def __init__(
        self,
        token_id: str,
        user_id: str,
        service: str,
        scopes: List[str],
        device_fingerprint: str,
        expires_at: datetime
    ):
        self.token_id = token_id
        self.user_id = user_id
        self.service = service
        self.scopes = scopes
        self.device_fingerprint = device_fingerprint
        self.expires_at = expires_at
        self.created_at = datetime.utcnow()
        self.is_revoked = False
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "token_id": self.token_id,
            "user_id": self.user_id,
            "service": self.service,
            "scopes": self.scopes,
            "device_fingerprint": self.device_fingerprint,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "is_revoked": self.is_revoked
        }
    
    def is_valid(self) -> bool:
        """トークンの有効性チェック"""
        if self.is_revoked:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def has_scope(self, required_scope: str) -> bool:
        """スコープの確認"""
        return required_scope in self.scopes

class LPRService:
    """LPRサービスクラス"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tokens: Dict[str, LPRToken] = {}  # メモリ内トークンストア（本番ではRedis推奨）
    
    async def issue_token(
        self,
        user_id: str,
        service: str,
        scopes: List[str],
        device_info: Dict[str, Any],
        duration_minutes: int = 30
    ) -> str:
        """LPRトークン発行"""
        
        # デバイスフィンガープリント生成
        device_fingerprint = self._generate_device_fingerprint(device_info)
        
        # トークンID生成
        token_id = str(uuid.uuid4())
        
        # トークン作成
        token = LPRToken(
            token_id=token_id,
            user_id=user_id,
            service=service,
            scopes=scopes,
            device_fingerprint=device_fingerprint,
            expires_at=datetime.utcnow() + timedelta(minutes=duration_minutes)
        )
        
        # トークン保存
        self.tokens[token_id] = token
        
        # JWTトークン生成
        jwt_token = JWTManager.create_access_token(
            data={
                "sub": user_id,
                "token_id": token_id,
                "service": service,
                "scopes": scopes,
                "device_fingerprint": device_fingerprint
            },
            expires_delta=timedelta(minutes=duration_minutes)
        )
        
        # 監査ログ記録
        await self._log_token_issued(user_id, service, scopes, device_info)
        
        return jwt_token
    
    async def verify_token(
        self,
        token: str,
        required_scope: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """トークン検証"""
        
        # JWT検証
        try:
            payload = JWTManager.verify_token(token)
        except Exception as e:
            raise AuthenticationException(f"Invalid token: {str(e)}")
        
        token_id = payload.get("token_id")
        
        # トークン取得
        lpr_token = self.tokens.get(token_id)
        if not lpr_token:
            raise AuthenticationException("Token not found")
        
        # 有効性チェック
        if not lpr_token.is_valid():
            raise AuthenticationException("Token is invalid or expired")
        
        # デバイス検証
        if device_info:
            device_fingerprint = self._generate_device_fingerprint(device_info)
            if device_fingerprint != lpr_token.device_fingerprint:
                raise AuthorizationException("Device mismatch")
        
        # スコープ検証
        if required_scope and not lpr_token.has_scope(required_scope):
            raise AuthorizationException(f"Missing required scope: {required_scope}")
        
        return {
            "user_id": lpr_token.user_id,
            "service": lpr_token.service,
            "scopes": lpr_token.scopes,
            "token_id": lpr_token.token_id
        }
    
    async def revoke_token(self, token_id: str, user_id: str) -> bool:
        """トークン無効化"""
        
        lpr_token = self.tokens.get(token_id)
        if not lpr_token:
            return False
        
        # ユーザー確認
        if lpr_token.user_id != user_id:
            raise AuthorizationException("Unauthorized to revoke this token")
        
        # トークン無効化
        lpr_token.is_revoked = True
        
        # 監査ログ記録
        await self._log_token_revoked(user_id, token_id)
        
        return True
    
    async def list_active_tokens(self, user_id: str) -> List[Dict]:
        """アクティブトークン一覧"""
        
        active_tokens = []
        for token_id, token in self.tokens.items():
            if token.user_id == user_id and token.is_valid():
                active_tokens.append({
                    "token_id": token_id,
                    "service": token.service,
                    "scopes": token.scopes,
                    "expires_at": token.expires_at.isoformat(),
                    "created_at": token.created_at.isoformat()
                })
        
        return active_tokens
    
    async def cleanup_expired_tokens(self) -> int:
        """期限切れトークンのクリーンアップ"""
        
        expired_tokens = []
        for token_id, token in self.tokens.items():
            if not token.is_valid():
                expired_tokens.append(token_id)
        
        for token_id in expired_tokens:
            del self.tokens[token_id]
        
        return len(expired_tokens)
    
    def _generate_device_fingerprint(self, device_info: Dict[str, Any]) -> str:
        """デバイスフィンガープリント生成"""
        
        fingerprint_data = {
            "user_agent": device_info.get("user_agent", ""),
            "ip_address": device_info.get("ip_address", ""),
            "screen_resolution": device_info.get("screen_resolution", ""),
            "timezone": device_info.get("timezone", ""),
            "language": device_info.get("language", "")
        }
        
        fingerprint_string = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    async def _log_token_issued(
        self,
        user_id: str,
        service: str,
        scopes: List[str],
        device_info: Dict[str, Any]
    ):
        """トークン発行ログ"""
        # TODO: 監査ログテーブルに記録
        pass
    
    async def _log_token_revoked(self, user_id: str, token_id: str):
        """トークン無効化ログ"""
        # TODO: 監査ログテーブルに記録
        pass