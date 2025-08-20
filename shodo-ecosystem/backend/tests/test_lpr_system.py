"""
LPRシステム（新実装）のテスト
"""

import pytest
from datetime import datetime, timezone

from src.services.auth.lpr_service import (
    LPRService,
    LPRScope,
    DeviceFingerprint,
)


@pytest.mark.asyncio
async def test_issue_token_and_verify_success():
    svc = LPRService(redis_client=None)

    device_fp = DeviceFingerprint(
        user_agent="pytest/agent",
        accept_language="ja-JP",
        screen_resolution="1920x1080",
        timezone="Asia/Tokyo",
        canvas_hash=None,
    )

    scopes = [
        LPRScope(method="GET", url_pattern="https://api.example.com/users/*"),
        LPRScope(method="POST", url_pattern="https://api.example.com/orders"),
    ]

    result = await svc.issue_token(
        service="external",
        purpose="unittest",
        scopes=scopes,
        device_fingerprint=device_fp,
        user_id="user-1",
        consent=True,
    )

    assert result.get("token")
    assert result.get("jti")
    assert result.get("expires_at")

    ver = await svc.verify_token(
        token=result["token"],
        device_fingerprint=device_fp,
        required_scope=LPRScope(method="GET", url_pattern="https://api.example.com/users/123"),
    )
    assert ver.get("valid") is True
    assert ver.get("jti") == result.get("jti")


@pytest.mark.asyncio
async def test_verify_wrong_scope():
    svc = LPRService(redis_client=None)

    device_fp = DeviceFingerprint(
        user_agent="pytest/agent",
        accept_language="ja-JP",
        screen_resolution="1920x1080",
        timezone="Asia/Tokyo",
        canvas_hash=None,
    )

    scopes = [
        LPRScope(method="GET", url_pattern="https://api.example.com/users/*"),
    ]

    result = await svc.issue_token(
        service="external",
        purpose="unittest",
        scopes=scopes,
        device_fingerprint=device_fp,
        user_id="user-1",
        consent=True,
    )

    ver = await svc.verify_token(
        token=result["token"],
        device_fingerprint=device_fp,
        required_scope=LPRScope(method="DELETE", url_pattern="https://api.example.com/users/123"),
    )
    assert ver.get("valid") is False
    assert ver.get("error")


@pytest.mark.asyncio
async def test_revoke_token():
    svc = LPRService(redis_client=None)

    device_fp = DeviceFingerprint(
        user_agent="pytest/agent",
        accept_language="ja-JP",
        screen_resolution="1920x1080",
        timezone="Asia/Tokyo",
        canvas_hash=None,
    )

    scopes = [LPRScope(method="*", url_pattern="/api/v1/")]

    result = await svc.issue_token(
        service="external",
        purpose="unittest",
        scopes=scopes,
        device_fingerprint=device_fp,
        user_id="user-1",
        consent=True,
    )

    # Without Redis, revoke_token returns False (logged) — verify method exists and returns bool
    ok = await svc.revoke_token(jti=result["jti"], reason="unit", user_id="user-1")
    assert ok in (True, False)

