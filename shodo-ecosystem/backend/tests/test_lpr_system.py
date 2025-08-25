def test_rate_limit_headers_present(client):
    # 何度か叩いてレートヘッダが付与されることを確認
    for _ in range(3):
        resp = client.get("/health")
        assert resp.status_code in (200, 503)
    assert any(h.startswith("X-RateLimit-") for h in resp.headers.keys())
"""
LPRシステムの包括的なテスト

ユニットテストとE2Eテストを含む。
"""

import pytest
import asyncio
import json
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
import jwt

from src.services.auth.lpr_service import (
    LPRService,
    LPRScope,
    LPRPolicy,
    DeviceFingerprint,
)
from src.services.auth.visible_login import (
    VisibleLoginDetector,
    SecureSessionStorage,
    LoginDetectionResult,
    LoginDetectionRule,
)
from src.services.audit.audit_logger import (
    AuditLogger,
    AuditEventType,
    AuditSeverity,
    AuditLogEntry,
)
from src.middleware.lpr_enforcer import (
    LPREnforcerMiddleware,
)

# ===== フィクスチャ =====

@pytest.fixture
async def lpr_service():
    """LPRサービスのフィクスチャ"""
    service = LPRService()
    # Redisモックを設定
    service.redis_client = AsyncMock()
    yield service

@pytest.fixture
def device_fingerprint():
    """デバイス指紋のフィクスチャ"""
    return DeviceFingerprint(
        user_agent="Mozilla/5.0 Test Browser",
        accept_language="ja-JP,ja;q=0.9,en;q=0.8",
        screen_resolution="1920x1080",
        timezone="Asia/Tokyo",
        platform="Win32",
        hardware_concurrency=8,
        memory=16,
        canvas_fp="test_canvas_fingerprint",
        webgl_fp="test_webgl_fingerprint",
        audio_fp="test_audio_fingerprint",
    )

@pytest.fixture
def lpr_scopes():
    """LPRスコープのフィクスチャ"""
    return [
        LPRScope(
            method="GET",
            url_pattern="https://api.example.com/users/*",
            description="ユーザー情報の取得",
        ),
        LPRScope(
            method="POST",
            url_pattern="https://api.example.com/orders",
            description="注文の作成",
        ),
    ]

@pytest.fixture
def lpr_policy():
    """LPRポリシーのフィクスチャ"""
    return LPRPolicy(
        rate_limit_rps=2.0,
        rate_limit_burst=20,
        human_speed_jitter=True,
        require_device_match=True,
        allow_concurrent=False,
        max_request_size=5242880,  # 5MB
    )

@pytest.fixture
async def audit_logger():
    """監査ログのフィクスチャ"""
    logger = AuditLogger()
    logger.redis_client = AsyncMock()
    yield logger

# ===== LPRトークンのテスト =====

class TestLPRToken:
    """LPRトークンのテスト"""
    
    @pytest.mark.asyncio
    async def test_token_issuance(self, lpr_service, device_fingerprint, lpr_scopes, lpr_policy):
        """トークン発行のテスト"""
        # トークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="test_user_123",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://app.example.com"],
            policy=lpr_policy,
            ttl_seconds=3600,
        )
        
        # 検証
        assert token is not None
        assert token_str is not None
        assert token.jti is not None
        assert token.subject_pseudonym != "test_user_123"  # 仮名化されている
        assert token.device_fingerprint_hash == device_fingerprint.calculate_hash()
        assert len(token.scope_allowlist) == 2
        assert token.expires_at > datetime.now(timezone.utc)
    
    @pytest.mark.asyncio
    async def test_token_verification_success(self, lpr_service, device_fingerprint, lpr_scopes):
        """トークン検証成功のテスト"""
        # トークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="test_user_123",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://app.example.com"],
            ttl_seconds=3600,
        )
        
        # Redisモックの設定
        lpr_service.redis_client.get.return_value = None  # 失効していない
        
        # 検証
        is_valid, verified_token, error = await lpr_service.verify_token(
            token_str=token_str,
            request_method="GET",
            request_url="https://api.example.com/users/123",
            request_origin="https://app.example.com",
            device_fingerprint=device_fingerprint,
        )
        
        assert is_valid is True
        assert verified_token is not None
        assert error is None
        assert verified_token.jti == token.jti
    
    @pytest.mark.asyncio
    async def test_token_verification_expired(self, lpr_service, device_fingerprint, lpr_scopes):
        """期限切れトークンの検証テスト"""
        # 期限切れトークンを作成
        token, token_str = await lpr_service.issue_token(
            user_id="test_user_123",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://app.example.com"],
            ttl_seconds=1,  # 1秒で期限切れ
        )
        
        # 2秒待機
        await asyncio.sleep(2)
        
        # 検証
        is_valid, verified_token, error = await lpr_service.verify_token(
            token_str=token_str,
            request_method="GET",
            request_url="https://api.example.com/users/123",
            request_origin="https://app.example.com",
            device_fingerprint=device_fingerprint,
        )
        
        assert is_valid is False
        assert verified_token is None
        assert "expired" in error.lower()
    
    @pytest.mark.asyncio
    async def test_token_verification_wrong_scope(self, lpr_service, device_fingerprint, lpr_scopes):
        """スコープ外アクセスの検証テスト"""
        # トークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="test_user_123",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://app.example.com"],
            ttl_seconds=3600,
        )
        
        # Redisモックの設定
        lpr_service.redis_client.get.return_value = None
        
        # スコープ外のURLで検証
        is_valid, verified_token, error = await lpr_service.verify_token(
            token_str=token_str,
            request_method="DELETE",  # DELETEは許可されていない
            request_url="https://api.example.com/users/123",
            request_origin="https://app.example.com",
            device_fingerprint=device_fingerprint,
        )
        
        assert is_valid is False
        assert "scope" in error.lower()
    
    @pytest.mark.asyncio
    async def test_token_verification_wrong_device(self, lpr_service, device_fingerprint, lpr_scopes):
        """異なるデバイスからのアクセステスト"""
        # トークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="test_user_123",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://app.example.com"],
            ttl_seconds=3600,
        )
        
        # 異なるデバイス指紋
        different_device = DeviceFingerprint(
            user_agent="Mozilla/5.0 Different Browser",
            accept_language="en-US",
            screen_resolution="1366x768",
            timezone="America/New_York",
            platform="Linux",
        )
        
        # Redisモックの設定
        lpr_service.redis_client.get.return_value = None
        
        # 検証
        is_valid, verified_token, error = await lpr_service.verify_token(
            token_str=token_str,
            request_method="GET",
            request_url="https://api.example.com/users/123",
            request_origin="https://app.example.com",
            device_fingerprint=different_device,
        )
        
        assert is_valid is False
        assert "device" in error.lower()
    
    @pytest.mark.asyncio
    async def test_token_revocation(self, lpr_service):
        """トークン失効のテスト"""
        jti = "test_jti_123"
        
        # 失効
        success = await lpr_service.revoke_token(
            jti=jti,
            reason="Test revocation",
            revoked_by="test_user",
        )
        
        assert success is True
        
        # Redisへの書き込みを確認
        lpr_service.redis_client.setex.assert_called()
        lpr_service.redis_client.publish.assert_called()

# ===== 可視ログイン検知のテスト =====

class TestVisibleLogin:
    """可視ログイン検知のテスト"""
    
    @pytest.mark.asyncio
    async def test_login_detection_rules(self):
        """ログイン検知ルールのテスト"""
        detector = VisibleLoginDetector()
        
        # デフォルトルールの確認
        assert "default" in detector.detection_rules
        default_rules = detector.detection_rules["default"]
        
        # ルールタイプの確認
        rule_types = {rule.type for rule in default_rules}
        assert "cookie" in rule_types
        assert "url" in rule_types
        assert "dom" in rule_types
    
    @pytest.mark.asyncio
    async def test_session_storage(self):
        """セッション保存のテスト"""
        storage = SecureSessionStorage()
        
        # セッション保存
        cookies = [
            {"name": "session", "value": "test_session_value"},
            {"name": "auth", "value": "test_auth_value"},
        ]
        
        session_id = await storage.store_session(
            user_id="test_user",
            cookies=cookies,
            ttl_seconds=300,
        )
        
        assert session_id is not None
        
        # セッション取得
        session = await storage.retrieve_session(session_id)
        assert session is not None
        assert session["user_id"] == "test_user"
        assert session["cookies"] == cookies
        
        # セッション削除
        deleted = await storage.delete_session(session_id)
        assert deleted is True
        
        # 削除後の取得
        session = await storage.retrieve_session(session_id)
        assert session is None

# ===== 監査ログのテスト =====

class TestAuditLogger:
    """監査ログのテスト"""
    
    @pytest.mark.asyncio
    async def test_audit_log_creation(self, audit_logger):
        """監査ログ作成のテスト"""
        # ログ記録
        entry = await audit_logger.log(
            event_type=AuditEventType.LPR_ISSUED,
            who="test_user",
            what="test_resource",
            where="test_endpoint",
            why="test_purpose",
            how="test_method",
            result="success",
            details={"test": "data"},
        )
        
        assert entry is not None
        assert entry.sequence_number is not None
        assert entry.entry_hash is not None
        assert entry.event_type == AuditEventType.LPR_ISSUED
        assert entry.who == "test_user"
    
    @pytest.mark.asyncio
    async def test_audit_log_hash_chain(self, audit_logger):
        """ハッシュチェーンのテスト"""
        # 複数のログを記録
        entries = []
        for i in range(3):
            entry = await audit_logger.log(
                event_type=AuditEventType.DATA_READ,
                who=f"user_{i}",
                what=f"resource_{i}",
                where="test",
                result="success",
            )
            entries.append(entry)
        
        # ハッシュチェーンの検証
        for i in range(1, len(entries)):
            assert entries[i].previous_hash == entries[i-1].entry_hash
    
    @pytest.mark.asyncio
    async def test_audit_log_severity(self, audit_logger):
        """重要度判定のテスト"""
        # エラーイベント
        entry = await audit_logger.log(
            event_type=AuditEventType.SECURITY_VIOLATION,
            who="attacker",
            what="protected_resource",
            where="api",
            result="failure",
        )
        
        assert entry.severity == AuditSeverity.CRITICAL

# ===== ミドルウェアのテスト =====

class TestLPREnforcerMiddleware:
    """LPRエンフォーサーミドルウェアのテスト"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        """レート制限のテスト"""
        limiter = LPRRateLimiter()
        
        # 初回リクエスト（成功）
        allowed = await limiter.check_and_update("test_key", limit=2.0, window=1.0)
        assert allowed is True
        
        # 2回目（成功）
        allowed = await limiter.check_and_update("test_key", limit=2.0, window=1.0)
        assert allowed is True
        
        # 3回目（制限）
        allowed = await limiter.check_and_update("test_key", limit=2.0, window=1.0)
        assert allowed is False
        
        # 1秒待機後（リセット）
        await asyncio.sleep(1.1)
        allowed = await limiter.check_and_update("test_key", limit=2.0, window=1.0)
        assert allowed is True

# ===== E2Eテスト =====

class TestLPREndToEnd:
    """LPRシステムのE2Eテスト"""
    
    @pytest.mark.asyncio
    async def test_full_lpr_flow(self, lpr_service, device_fingerprint, lpr_scopes, audit_logger):
        """完全なLPRフローのテスト"""
        
        # 1. トークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="e2e_user",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://e2e.example.com"],
            ttl_seconds=3600,
        )
        
        assert token is not None
        
        # 2. 監査ログ記録
        await audit_logger.log(
            event_type=AuditEventType.LPR_ISSUED,
            who="e2e_user",
            what=f"LPR:{token.jti}",
            where="e2e_test",
            result="success",
        )
        
        # 3. トークン検証（成功）
        lpr_service.redis_client.get.return_value = None
        is_valid, _, _ = await lpr_service.verify_token(
            token_str=token_str,
            request_method="GET",
            request_url="https://api.example.com/users/456",
            request_origin="https://e2e.example.com",
            device_fingerprint=device_fingerprint,
        )
        
        assert is_valid is True
        
        # 4. 監査ログ記録
        await audit_logger.log(
            event_type=AuditEventType.LPR_VERIFIED,
            who="e2e_user",
            what=f"LPR:{token.jti}",
            where="e2e_test",
            result="success",
        )
        
        # 5. トークン失効
        await lpr_service.revoke_token(
            jti=token.jti,
            reason="E2E test completion",
            revoked_by="e2e_user",
        )
        
        # 6. 監査ログ記録
        await audit_logger.log(
            event_type=AuditEventType.LPR_REVOKED,
            who="e2e_user",
            what=f"LPR:{token.jti}",
            where="e2e_test",
            result="success",
        )
        
        # 7. 失効後の検証（失敗）
        lpr_service.redis_client.get.return_value = json.dumps({
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "reason": "E2E test completion",
            "revoked_by": "e2e_user",
        })
        
        is_valid, _, error = await lpr_service.verify_token(
            token_str=token_str,
            request_method="GET",
            request_url="https://api.example.com/users/456",
            request_origin="https://e2e.example.com",
            device_fingerprint=device_fingerprint,
        )
        
        assert is_valid is False
        assert "revoked" in error.lower()

# ===== セキュリティテスト =====

class TestLPRSecurity:
    """LPRシステムのセキュリティテスト"""
    
    @pytest.mark.asyncio
    async def test_token_tampering(self, lpr_service, device_fingerprint, lpr_scopes):
        """トークン改竄のテスト"""
        # 正規のトークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="security_user",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://secure.example.com"],
            ttl_seconds=3600,
        )
        
        # トークンを改竄
        tampered_token = token_str[:-10] + "tamperedXX"
        
        # 検証（失敗するはず）
        with pytest.raises(Exception):
            await lpr_service.verify_token(
                token_str=tampered_token,
                request_method="GET",
                request_url="https://api.example.com/users/123",
                request_origin="https://secure.example.com",
                device_fingerprint=device_fingerprint,
            )
    
    @pytest.mark.asyncio
    async def test_replay_attack_prevention(self, lpr_service, device_fingerprint, lpr_scopes):
        """リプレイ攻撃防止のテスト"""
        # トークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="replay_user",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://replay.example.com"],
            ttl_seconds=3600,
        )
        
        # トークンを失効
        await lpr_service.revoke_token(
            jti=token.jti,
            reason="Replay test",
            revoked_by="test",
        )
        
        # 失効リストを設定
        lpr_service.redis_client.get.return_value = json.dumps({
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "reason": "Replay test",
        })
        
        # 同じトークンで再度アクセス（失敗するはず）
        is_valid, _, error = await lpr_service.verify_token(
            token_str=token_str,
            request_method="GET",
            request_url="https://api.example.com/users/123",
            request_origin="https://replay.example.com",
            device_fingerprint=device_fingerprint,
        )
        
        assert is_valid is False
        assert "revoked" in error.lower()
    
    @pytest.mark.asyncio
    async def test_origin_validation(self, lpr_service, device_fingerprint, lpr_scopes):
        """オリジン検証のテスト"""
        # 特定オリジンのみ許可するトークン
        token, token_str = await lpr_service.issue_token(
            user_id="origin_user",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://allowed.example.com"],
            ttl_seconds=3600,
        )
        
        lpr_service.redis_client.get.return_value = None
        
        # 許可されていないオリジンからのアクセス
        is_valid, _, error = await lpr_service.verify_token(
            token_str=token_str,
            request_method="GET",
            request_url="https://api.example.com/users/123",
            request_origin="https://evil.example.com",  # 許可されていない
            device_fingerprint=device_fingerprint,
        )
        
        assert is_valid is False
        assert "origin" in error.lower()

# ===== パフォーマンステスト =====

class TestLPRPerformance:
    """LPRシステムのパフォーマンステスト"""
    
    @pytest.mark.asyncio
    async def test_token_generation_performance(self, lpr_service, device_fingerprint, lpr_scopes):
        """トークン生成のパフォーマンステスト"""
        import time
        
        start_time = time.time()
        
        # 100個のトークンを生成
        for i in range(100):
            await lpr_service.issue_token(
                user_id=f"perf_user_{i}",
                device_fingerprint=device_fingerprint,
                scopes=lpr_scopes,
                origins=["https://perf.example.com"],
                ttl_seconds=3600,
            )
        
        elapsed_time = time.time() - start_time
        
        # 100個のトークン生成が10秒以内
        assert elapsed_time < 10.0
        
        # 平均生成時間
        avg_time = elapsed_time / 100
        print(f"Average token generation time: {avg_time:.3f} seconds")
    
    @pytest.mark.asyncio
    async def test_concurrent_verification(self, lpr_service, device_fingerprint, lpr_scopes):
        """並行検証のテスト"""
        # トークン発行
        token, token_str = await lpr_service.issue_token(
            user_id="concurrent_user",
            device_fingerprint=device_fingerprint,
            scopes=lpr_scopes,
            origins=["https://concurrent.example.com"],
            ttl_seconds=3600,
        )
        
        lpr_service.redis_client.get.return_value = None
        
        # 並行して10個の検証を実行
        tasks = []
        for i in range(10):
            task = lpr_service.verify_token(
                token_str=token_str,
                request_method="GET",
                request_url=f"https://api.example.com/users/{i}",
                request_origin="https://concurrent.example.com",
                device_fingerprint=device_fingerprint,
            )
            tasks.append(task)
        
        # すべての検証を待機
        results = await asyncio.gather(*tasks)
        
        # すべて成功するはず
        for is_valid, _, _ in results:
            assert is_valid is True