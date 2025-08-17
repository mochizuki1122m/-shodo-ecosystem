"""
OpenAPI/Swagger ドキュメンテーション設定
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from typing import Dict, Any

def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """カスタムOpenAPIスキーマを生成"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Shodo Ecosystem API",
        version="1.0.0",
        description="""
# Shodo Ecosystem API Documentation

## 概要
Shodo Ecosystemは、非技術者でも自然な日本語でSaaSサービスを操作できるAI駆動の統合プラットフォームです。

## 主な機能

### 🔐 認証・認可
- JWT基盤の認証システム
- ロールベースアクセス制御（RBAC）
- 2要素認証（2FA）対応
- セッション管理

### 🔑 APIキー管理
- 自動取得・更新
- OAuth2.0フロー対応
- 暗号化保存
- 使用状況追跡
- 監査ログ

### 🤖 自然言語処理
- 日本語対応
- デュアルパス解析（ルールベース + AI）
- 曖昧性解消
- コンテキスト理解

### 👁️ プレビュー・反復修正
- サンドボックス環境
- リアルタイムプレビュー
- バージョン管理
- ロールバック機能

### 📊 ダッシュボード
- 統合管理画面
- リアルタイム統計
- 使用状況分析
- アラート通知

## 認証方法

### Bearer Token
```
Authorization: Bearer <access_token>
```

### APIキー
```
X-API-Key: <api_key>
```

## レート制限
- デフォルト: 100リクエスト/分
- 認証済み: 1000リクエスト/分
- エンタープライズ: カスタム

## エラーレスポンス
```json
{
    "detail": "エラーメッセージ",
    "code": "ERROR_CODE",
    "timestamp": "2024-01-20T10:00:00Z"
}
```

## サポート
- Email: support@shodo-ecosystem.com
- Documentation: https://docs.shodo-ecosystem.com
- Status: https://status.shodo-ecosystem.com
        """,
        routes=app.routes,
        tags_metadata=[
            {
                "name": "Authentication",
                "description": "認証・認可関連のエンドポイント",
                "externalDocs": {
                    "description": "認証ガイド",
                    "url": "https://docs.shodo-ecosystem.com/auth",
                },
            },
            {
                "name": "API Keys",
                "description": "APIキー管理エンドポイント",
                "externalDocs": {
                    "description": "APIキー管理ガイド",
                    "url": "https://docs.shodo-ecosystem.com/api-keys",
                },
            },
            {
                "name": "NLP",
                "description": "自然言語処理エンドポイント",
            },
            {
                "name": "Preview",
                "description": "プレビュー・反復修正エンドポイント",
            },
            {
                "name": "Dashboard",
                "description": "ダッシュボード関連エンドポイント",
            },
            {
                "name": "Connections",
                "description": "サービス接続管理エンドポイント",
            },
            {
                "name": "Health",
                "description": "ヘルスチェックエンドポイント",
            },
        ],
        servers=[
            {
                "url": "https://api.shodo-ecosystem.com",
                "description": "Production server"
            },
            {
                "url": "https://staging-api.shodo-ecosystem.com",
                "description": "Staging server"
            },
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ],
    )
    
    # セキュリティスキーマを追加
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT認証トークン"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "APIキー認証"
        },
        "OAuth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://api.shodo-ecosystem.com/oauth/authorize",
                    "tokenUrl": "https://api.shodo-ecosystem.com/oauth/token",
                    "scopes": {
                        "read": "読み取り権限",
                        "write": "書き込み権限",
                        "admin": "管理者権限"
                    }
                }
            }
        }
    }
    
    # レスポンス例を追加
    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "description": "エラーの詳細メッセージ"
            },
            "code": {
                "type": "string",
                "description": "エラーコード"
            },
            "timestamp": {
                "type": "string",
                "format": "date-time",
                "description": "エラー発生時刻"
            }
        },
        "required": ["detail"],
        "example": {
            "detail": "認証が必要です",
            "code": "AUTH_REQUIRED",
            "timestamp": "2024-01-20T10:00:00Z"
        }
    }
    
    openapi_schema["components"]["schemas"]["SuccessResponse"] = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "成功メッセージ"
            },
            "data": {
                "type": "object",
                "description": "レスポンスデータ"
            }
        },
        "example": {
            "message": "操作が正常に完了しました",
            "data": {}
        }
    }
    
    openapi_schema["components"]["schemas"]["PaginatedResponse"] = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {},
                "description": "データ配列"
            },
            "total": {
                "type": "integer",
                "description": "総件数"
            },
            "page": {
                "type": "integer",
                "description": "現在のページ"
            },
            "per_page": {
                "type": "integer",
                "description": "1ページあたりの件数"
            },
            "has_next": {
                "type": "boolean",
                "description": "次ページの有無"
            },
            "has_prev": {
                "type": "boolean",
                "description": "前ページの有無"
            }
        }
    }
    
    # グローバルセキュリティを設定
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []}
    ]
    
    # カスタムヘッダーを追加
    openapi_schema["components"]["parameters"] = {
        "X-Request-ID": {
            "name": "X-Request-ID",
            "in": "header",
            "description": "リクエスト追跡用ID",
            "required": False,
            "schema": {
                "type": "string",
                "format": "uuid"
            }
        },
        "X-Client-Version": {
            "name": "X-Client-Version",
            "in": "header",
            "description": "クライアントバージョン",
            "required": False,
            "schema": {
                "type": "string"
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# API例の追加
API_EXAMPLES = {
    "auth_login": {
        "summary": "ログイン成功例",
        "value": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer",
            "expires_in": 1800
        }
    },
    "api_key_list": {
        "summary": "APIキー一覧",
        "value": [
            {
                "id": "key_123",
                "key_id": "sk_live_abc123",
                "service": "stripe",
                "name": "Production Stripe Key",
                "status": "active",
                "created_at": "2024-01-20T10:00:00Z",
                "expires_at": "2025-01-20T10:00:00Z",
                "permissions": ["read:charges", "write:customers"],
                "auto_renew": True
            }
        ]
    },
    "nlp_analysis": {
        "summary": "NLP解析結果",
        "value": {
            "intent": "get_sales_data",
            "confidence": 0.95,
            "entities": {
                "service": "shopify",
                "period": "今月",
                "metric": "売上"
            },
            "suggested_action": {
                "type": "api_call",
                "endpoint": "/api/shopify/sales",
                "params": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-31"
                }
            },
            "processing_time_ms": 150
        }
    },
    "preview_result": {
        "summary": "プレビュー結果",
        "value": {
            "preview_id": "prev_456",
            "status": "ready",
            "preview_url": "https://preview.shodo-ecosystem.com/prev_456",
            "changes": [
                {
                    "type": "update",
                    "field": "product.price",
                    "old_value": 1000,
                    "new_value": 1200
                }
            ],
            "version": 3,
            "can_apply": True
        }
    }
}

# WebSocket メッセージ定義
WEBSOCKET_MESSAGES = {
    "connection": {
        "type": "connection",
        "status": "connected",
        "session_id": "ws_789",
        "timestamp": "2024-01-20T10:00:00Z"
    },
    "preview_update": {
        "type": "preview_update",
        "preview_id": "prev_456",
        "status": "processing",
        "progress": 75,
        "message": "変更を適用中..."
    },
    "notification": {
        "type": "notification",
        "level": "info",
        "title": "APIキー更新",
        "message": "Shopify APIキーが正常に更新されました",
        "timestamp": "2024-01-20T10:00:00Z"
    },
    "error": {
        "type": "error",
        "code": "WS_ERROR",
        "message": "WebSocket接続エラー",
        "reconnect": True,
        "retry_after": 5
    }
}