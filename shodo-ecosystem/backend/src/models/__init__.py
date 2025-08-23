"""
データベースモデル定義
"""

import os

__all__ = []

if os.getenv("LIGHT_TESTS") != "1":
    from .base import Base, get_db, init_db
    from .api_key import APIKey, APIKeyAuditLog, APIKeyUsage
    from .user import User, UserSession
    from .service_connection import ServiceConnection

    __all__ = [
        'Base',
        'get_db',
        'init_db',
        'APIKey',
        'APIKeyAuditLog',
        'APIKeyUsage',
        'User',
        'UserSession',
        'ServiceConnection',
    ]