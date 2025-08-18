"""
LPR (Limited Proxy Rights) エンフォーサーミドルウェア

すべての代理実行APIリクエストに対してLPRトークンの検証と
多層防御を適用するミドルウェア。
"""

import json
import time
import hashlib
import secrets
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone
import logging

from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import structlog

from ..services.auth.lpr import (
    lpr_service,
    DeviceFingerprint,
    LPRToken,
)
from ..utils.config import settings

# 構造化ログ
logger = structlog.get_logger()

# セキュリティヘッダー
security = HTTPBearer(auto_error=False)

class LPREnforcerMiddleware(BaseHTTPMiddleware):
    """LPRエンフォーサーミドルウェア"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        self.protected_paths = [
            "/api/v1/mcp/",
            "/api/v1/preview/",
            "/api/v1/nlp/execute",
            "/api/v1/proxy/",
        ]
        self.bypass_paths = [
            "/api/v1/lpr/",  # LPR管理API自体はバイパス
            "/api/v1/auth/",  # 認証APIはバイパス
            "/health",
            "/metrics",
        ]
        
        # レート制限用のウィンドウ
        self.rate_windows: Dict[str, Dict] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """リクエストを処理"""
        
        # バイパスパスのチェック
        if self._should_bypass(request.url.path):
            return await call_next(request)
        
        # 保護パスのチェック
        if not self._is_protected(request.url.path):
            return await call_next(request)
        
        # 開始時刻
        start_time = time.time()
        
        # 相関IDの生成
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            secrets.token_urlsafe(16)
        )
        
        try:
            # LPRトークンの取得
            token_str = await self._extract_token(request)
            if not token_str:
                await self._audit_log(
                    request,
                    "lpr_missing",
                    {"path": str(request.url.path)},
                    correlation_id
                )
                return JSONResponse(
                    status_code=401,
                    content={"error": "LPR token required"},
                    headers={"X-Correlation-ID": correlation_id}
                )
            
            # デバイス指紋の抽出
            device_fingerprint = await self._extract_device_fingerprint(request)
            
            # リクエスト情報
            request_method = request.method
            request_url = str(request.url)
            request_origin = request.headers.get("Origin", "")
            
            # トークン検証
            is_valid, token, error = await lpr_service.verify_token(
                token_str,
                request_method,
                request_url,
                request_origin,
                device_fingerprint
            )
            
            if not is_valid:
                await self._audit_log(
                    request,
                    "lpr_invalid",
                    {
                        "path": str(request.url.path),
                        "error": error,
                    },
                    correlation_id
                )
                return JSONResponse(
                    status_code=403,
                    content={"error": f"Invalid LPR token: {error}"},
                    headers={"X-Correlation-ID": correlation_id}
                )
            
            # リクエストにトークン情報を追加
            request.state.lpr_token = token
            request.state.correlation_id = correlation_id
            
            # Layer 2: デバイス拘束の追加チェック
            if token.policy.require_device_match:
                if not await self._verify_device_binding(request, token, device_fingerprint):
                    await self._audit_log(
                        request,
                        "device_binding_failed",
                        {"jti": token.jti},
                        correlation_id
                    )
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Device binding verification failed"},
                        headers={"X-Correlation-ID": correlation_id}
                    )
            
            # Layer 3: リクエストサイズ制限
            content_length = request.headers.get("Content-Length")
            if content_length and int(content_length) > token.policy.max_request_size:
                await self._audit_log(
                    request,
                    "request_size_exceeded",
                    {
                        "jti": token.jti,
                        "size": content_length,
                        "limit": token.policy.max_request_size,
                    },
                    correlation_id
                )
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request size exceeds limit"},
                    headers={"X-Correlation-ID": correlation_id}
                )
            
            # Layer 4: 追加のレート制限（ミドルウェアレベル）
            if not await self._check_rate_limit(request, token):
                await self._audit_log(
                    request,
                    "rate_limit_exceeded",
                    {"jti": token.jti},
                    correlation_id
                )
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded"},
                    headers={
                        "X-Correlation-ID": correlation_id,
                        "Retry-After": "1",
                    }
                )
            
            # Layer 4: ヒューマンスピード制御
            if token.policy.human_speed_jitter:
                await self._apply_human_speed_delay()
            
            # リクエスト処理
            response = await call_next(request)
            
            # Layer 5: レスポンスフィルタリング（データ最小化）
            response = await self._filter_response(response, token)
            
            # 処理時間の記録
            process_time = time.time() - start_time
            
            # 成功の監査ログ
            await self._audit_log(
                request,
                "lpr_request_completed",
                {
                    "jti": token.jti,
                    "path": str(request.url.path),
                    "method": request_method,
                    "status": response.status_code,
                    "process_time": process_time,
                },
                correlation_id
            )
            
            # レスポンスヘッダーの追加
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            logger.error(
                "LPR enforcement error",
                error=str(e),
                correlation_id=correlation_id
            )
            
            await self._audit_log(
                request,
                "lpr_enforcement_error",
                {
                    "path": str(request.url.path),
                    "error": str(e),
                },
                correlation_id
            )
            
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"},
                headers={"X-Correlation-ID": correlation_id}
            )
    
    def _is_protected(self, path: str) -> bool:
        """保護対象パスか確認"""
        for protected in self.protected_paths:
            if path.startswith(protected):
                return True
        return False
    
    def _should_bypass(self, path: str) -> bool:
        """バイパスすべきパスか確認"""
        for bypass in self.bypass_paths:
            if path.startswith(bypass):
                return True
        return False
    
    async def _extract_token(self, request: Request) -> Optional[str]:
        """リクエストからLPRトークンを抽出"""
        
        # Authorizationヘッダーから取得
        auth_header = request.headers.get("Authorization")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2:
                scheme, token = parts
                if scheme.upper() in ["BEARER", "LPR"]:
                    return token
        
        # カスタムヘッダーから取得
        lpr_header = request.headers.get("X-LPR-Token")
        if lpr_header:
            return lpr_header
        
        # クエリパラメータから取得（非推奨だが互換性のため）
        if "lpr_token" in request.query_params:
            return request.query_params["lpr_token"]
        
        return None
    
    async def _extract_device_fingerprint(self, request: Request) -> Optional[DeviceFingerprint]:
        """リクエストからデバイス指紋を抽出"""
        
        try:
            # ヘッダーから基本情報を取得
            user_agent = request.headers.get("User-Agent", "")
            accept_language = request.headers.get("Accept-Language", "")
            
            # カスタムヘッダーから追加情報を取得
            fingerprint_data = request.headers.get("X-Device-Fingerprint")
            
            if fingerprint_data:
                # Base64デコードしてJSON解析
                import base64
                decoded = base64.b64decode(fingerprint_data).decode('utf-8')
                fp_dict = json.loads(decoded)
                
                return DeviceFingerprint(
                    user_agent=user_agent,
                    accept_language=accept_language,
                    screen_resolution=fp_dict.get("screenResolution"),
                    timezone=fp_dict.get("timezone"),
                    platform=fp_dict.get("platform"),
                    hardware_concurrency=fp_dict.get("hardwareConcurrency"),
                    memory=fp_dict.get("memory"),
                    canvas_fp=fp_dict.get("canvasFingerprint"),
                    webgl_fp=fp_dict.get("webglFingerprint"),
                    audio_fp=fp_dict.get("audioFingerprint"),
                )
            else:
                # 最小限の指紋
                return DeviceFingerprint(
                    user_agent=user_agent,
                    accept_language=accept_language,
                )
        
        except Exception as e:
            logger.warning("Failed to extract device fingerprint", error=str(e))
            return None
    
    async def _verify_device_binding(
        self,
        request: Request,
        token: LPRToken,
        fingerprint: Optional[DeviceFingerprint]
    ) -> bool:
        """デバイスバインディングを検証"""
        
        if not fingerprint:
            return False
        
        # IPアドレスの一貫性チェック（オプション）
        client_ip = request.client.host if request.client else None
        if client_ip:
            # Redis等から前回のIPを取得して比較
            # ここでは簡略化
            pass
        
        # User-Agentの一貫性チェック
        stored_hash = token.device_fingerprint_hash
        current_hash = fingerprint.calculate_hash()
        
        if stored_hash != current_hash:
            # 部分一致を許可する場合の追加ロジック
            # 例: User-Agentのメジャーバージョンのみ比較
            return False
        
        return True
    
    async def _check_rate_limit(self, request: Request, token: LPRToken) -> bool:
        """レート制限チェック（ミドルウェアレベル）"""
        
        # トークンごとのウィンドウを取得
        window_key = token.jti
        now = time.time()
        
        if window_key not in self.rate_windows:
            self.rate_windows[window_key] = {
                "start": now,
                "count": 0,
                "requests": [],
            }
        
        window = self.rate_windows[window_key]
        
        # 1秒ウィンドウのリセット
        if now - window["start"] > 1.0:
            window["start"] = now
            window["count"] = 0
            window["requests"] = []
        
        # バースト制限チェック
        if window["count"] >= token.policy.rate_limit_burst:
            return False
        
        # RPS制限チェック
        recent_requests = [
            req_time for req_time in window["requests"]
            if now - req_time < 1.0
        ]
        
        if len(recent_requests) >= token.policy.rate_limit_rps:
            return False
        
        # カウント更新
        window["count"] += 1
        window["requests"].append(now)
        
        # 古いウィンドウのクリーンアップ
        self._cleanup_old_windows()
        
        return True
    
    def _cleanup_old_windows(self):
        """古いレート制限ウィンドウをクリーンアップ"""
        now = time.time()
        expired = [
            key for key, window in self.rate_windows.items()
            if now - window["start"] > 300  # 5分以上古い
        ]
        
        for key in expired:
            del self.rate_windows[key]
    
    async def _apply_human_speed_delay(self):
        """人間的な速度の遅延を適用"""
        import random
        import asyncio
        
        # 50-200msのランダムな遅延
        delay = random.uniform(0.05, 0.2)
        await asyncio.sleep(delay)
    
    async def _filter_response(self, response: Response, token: LPRToken) -> Response:
        """レスポンスフィルタリング（データ最小化）"""
        
        # JSONレスポンスの場合のみフィルタリング
        if response.headers.get("Content-Type", "").startswith("application/json"):
            try:
                # レスポンスボディを読み取り
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                
                # JSON解析
                data = json.loads(body.decode('utf-8'))
                
                # スコープに基づくフィルタリング
                filtered_data = await self._apply_scope_filter(data, token)
                
                # 新しいレスポンスを作成
                return JSONResponse(
                    content=filtered_data,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )
                
            except Exception as e:
                logger.warning("Response filtering failed", error=str(e))
        
        return response
    
    async def _apply_scope_filter(self, data: Any, token: LPRToken) -> Any:
        """スコープに基づくデータフィルタリング"""
        
        # スコープに基づいて機密フィールドを除去
        # ここでは簡略化された実装
        if isinstance(data, dict):
            # 機密フィールドのリスト
            sensitive_fields = [
                "password",
                "secret",
                "token",
                "api_key",
                "private_key",
                "ssn",
                "credit_card",
            ]
            
            filtered = {}
            for key, value in data.items():
                # 機密フィールドをマスク
                if any(sensitive in key.lower() for sensitive in sensitive_fields):
                    filtered[key] = "***FILTERED***"
                elif isinstance(value, (dict, list)):
                    filtered[key] = await self._apply_scope_filter(value, token)
                else:
                    filtered[key] = value
            
            return filtered
        
        elif isinstance(data, list):
            return [await self._apply_scope_filter(item, token) for item in data]
        
        return data
    
    async def _audit_log(
        self,
        request: Request,
        event: str,
        data: Dict[str, Any],
        correlation_id: str
    ):
        """監査ログ記録"""
        
        # クライアント情報
        client_info = {
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("User-Agent"),
        }
        
        # ログエントリ
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "correlation_id": correlation_id,
            "client": client_info,
            "data": data,
        }
        
        # 構造化ログ出力
        logger.info(
            f"AUDIT: {event}",
            correlation_id=correlation_id,
            **data
        )
        
        # TODO: 監査ログをデータベースやSIEMに送信

class LPRRateLimiter:
    """LPR用のカスタムレート制限"""
    
    def __init__(self):
        self.limits: Dict[str, Dict] = {}
    
    async def check_and_update(
        self,
        key: str,
        limit: float,
        window: float = 1.0
    ) -> bool:
        """レート制限をチェックして更新"""
        
        now = time.time()
        
        if key not in self.limits:
            self.limits[key] = {
                "tokens": limit,
                "last_update": now,
            }
        
        bucket = self.limits[key]
        
        # トークンバケットアルゴリズム
        elapsed = now - bucket["last_update"]
        bucket["tokens"] = min(
            limit,
            bucket["tokens"] + elapsed * limit
        )
        bucket["last_update"] = now
        
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        
        return False

# グローバルインスタンス
lpr_rate_limiter = LPRRateLimiter()