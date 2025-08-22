import pytest

from src.services.auth.lpr_service import LPRService, LPRScope


@pytest.mark.asyncio
async def test_check_scope_authorization_prefix_match(monkeypatch):
    service = LPRService(redis_client=None)
    required = LPRScope(method="GET", url_pattern="/api/v1/nlp/analyze")
    granted = [
        LPRScope(method="GET", url_pattern="/api/v1/nlp/")
    ]
    assert service._check_scope_authorization(required, granted) is True


@pytest.mark.asyncio
async def test_check_scope_authorization_method_mismatch(monkeypatch):
    service = LPRService(redis_client=None)
    required = LPRScope(method="POST", url_pattern="/api/v1/nlp/analyze")
    granted = [
        LPRScope(method="GET", url_pattern="/api/v1/nlp/")
    ]
    assert service._check_scope_authorization(required, granted) is False