"""
MCP (Model Context Protocol) APIエンドポイント
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
import json
from .auth import get_current_user

router = APIRouter()

# 利用可能なツール定義
AVAILABLE_TOOLS = {
    "shopify_export": {
        "id": "shopify_export",
        "name": "Shopify データエクスポート",
        "description": "Shopifyから商品、注文、顧客データをエクスポート",
        "category": "export",
        "service": "shopify",
        "parameters": {
            "type": "object",
            "properties": {
                "data_type": {
                    "type": "string",
                    "enum": ["products", "orders", "customers", "inventory"],
                    "description": "エクスポートするデータタイプ"
                },
                "format": {
                    "type": "string",
                    "enum": ["csv", "json", "xlsx"],
                    "description": "出力フォーマット"
                },
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "format": "date"},
                        "end": {"type": "string", "format": "date"}
                    }
                }
            },
            "required": ["data_type", "format"]
        }
    },
    "gmail_send": {
        "id": "gmail_send",
        "name": "Gmail メール送信",
        "description": "Gmailを使用してメールを送信",
        "category": "communication",
        "service": "gmail",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "送信先メールアドレス"
                },
                "subject": {
                    "type": "string",
                    "description": "件名"
                },
                "body": {
                    "type": "string",
                    "description": "本文"
                },
                "attachments": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "添付ファイルのパス"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    "stripe_create_invoice": {
        "id": "stripe_create_invoice",
        "name": "Stripe 請求書作成",
        "description": "Stripeで請求書を作成",
        "category": "billing",
        "service": "stripe",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "顧客ID"
                },
                "amount": {
                    "type": "number",
                    "description": "金額（円）"
                },
                "description": {
                    "type": "string",
                    "description": "請求内容の説明"
                },
                "due_date": {
                    "type": "string",
                    "format": "date",
                    "description": "支払期限"
                }
            },
            "required": ["customer_id", "amount"]
        }
    },
    "slack_post_message": {
        "id": "slack_post_message",
        "name": "Slack メッセージ投稿",
        "description": "Slackチャンネルにメッセージを投稿",
        "category": "communication",
        "service": "slack",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "チャンネル名またはID"
                },
                "text": {
                    "type": "string",
                    "description": "メッセージテキスト"
                },
                "attachments": {
                    "type": "array",
                    "description": "添付情報"
                }
            },
            "required": ["channel", "text"]
        }
    },
    "notion_create_page": {
        "id": "notion_create_page",
        "name": "Notion ページ作成",
        "description": "Notionに新しいページを作成",
        "category": "documentation",
        "service": "notion",
        "parameters": {
            "type": "object",
            "properties": {
                "parent_id": {
                    "type": "string",
                    "description": "親ページまたはデータベースのID"
                },
                "title": {
                    "type": "string",
                    "description": "ページタイトル"
                },
                "content": {
                    "type": "string",
                    "description": "ページコンテンツ（Markdown形式）"
                },
                "properties": {
                    "type": "object",
                    "description": "データベースプロパティ"
                }
            },
            "required": ["title"]
        }
    }
}

# ツール実行履歴
tool_execution_history = {}

class ToolInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    service: str
    parameters: Dict[str, Any]

class ToolInvocation(BaseModel):
    tool_id: str
    parameters: Dict[str, Any]
    async_execution: bool = False

class ToolExecutionResult(BaseModel):
    execution_id: str
    tool_id: str
    status: str  # "success", "error", "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

@router.get("/tools", response_model=List[ToolInfo])
async def get_available_tools(
    category: Optional[str] = None,
    service: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """利用可能なツール一覧の取得"""
    
    tools = []
    for tool_id, tool_data in AVAILABLE_TOOLS.items():
        # フィルタリング
        if category and tool_data["category"] != category:
            continue
        if service and tool_data["service"] != service:
            continue
        
        tools.append(ToolInfo(**tool_data))
    
    return tools

@router.get("/tools/{tool_id}", response_model=ToolInfo)
async def get_tool_info(
    tool_id: str,
    current_user: dict = Depends(get_current_user)
):
    """特定ツールの詳細情報取得"""
    
    if tool_id not in AVAILABLE_TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return ToolInfo(**AVAILABLE_TOOLS[tool_id])

@router.post("/tools/{tool_id}/invoke", response_model=ToolExecutionResult)
async def invoke_tool(
    tool_id: str,
    invocation: ToolInvocation,
    current_user: dict = Depends(get_current_user)
):
    """ツールの実行"""
    
    if tool_id not in AVAILABLE_TOOLS:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    tool = AVAILABLE_TOOLS[tool_id]
    
    # パラメータ検証
    required_params = tool["parameters"].get("required", [])
    for param in required_params:
        if param not in invocation.parameters:
            raise HTTPException(
                status_code=400,
                detail=f"Required parameter '{param}' is missing"
            )
    
    # 実行ID生成
    execution_id = f"exec_{tool_id}_{datetime.utcnow().timestamp()}"
    
    # 実行開始
    execution_result = {
        "execution_id": execution_id,
        "tool_id": tool_id,
        "status": "pending" if invocation.async_execution else "success",
        "result": None,
        "error": None,
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "user_id": current_user["id"],
        "parameters": invocation.parameters
    }
    
    try:
        # ツール実行のモック
        result = await execute_tool(tool_id, invocation.parameters)
        
        execution_result["result"] = result
        execution_result["status"] = "success"
        execution_result["completed_at"] = datetime.utcnow()
        
    except Exception as e:
        execution_result["status"] = "error"
        execution_result["error"] = str(e)
        execution_result["completed_at"] = datetime.utcnow()
    
    # 履歴に保存
    user_email = current_user["email"]
    if user_email not in tool_execution_history:
        tool_execution_history[user_email] = []
    tool_execution_history[user_email].append(execution_result)
    
    return ToolExecutionResult(**execution_result)

@router.get("/executions/{execution_id}", response_model=ToolExecutionResult)
async def get_execution_status(
    execution_id: str,
    current_user: dict = Depends(get_current_user)
):
    """ツール実行状態の取得"""
    
    user_email = current_user["email"]
    user_history = tool_execution_history.get(user_email, [])
    
    for execution in user_history:
        if execution["execution_id"] == execution_id:
            return ToolExecutionResult(**execution)
    
    raise HTTPException(status_code=404, detail="Execution not found")

@router.get("/executions", response_model=List[ToolExecutionResult])
async def get_execution_history(
    limit: int = 20,
    tool_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """ツール実行履歴の取得"""
    
    user_email = current_user["email"]
    user_history = tool_execution_history.get(user_email, [])
    
    # フィルタリング
    filtered_history = []
    for execution in user_history:
        if tool_id and execution["tool_id"] != tool_id:
            continue
        if status and execution["status"] != status:
            continue
        filtered_history.append(ToolExecutionResult(**execution))
    
    # 最新のものから返す
    return filtered_history[-limit:][::-1]

@router.get("/categories")
async def get_tool_categories(current_user: dict = Depends(get_current_user)):
    """ツールカテゴリ一覧の取得"""
    
    categories = set()
    for tool in AVAILABLE_TOOLS.values():
        categories.add(tool["category"])
    
    return {
        "categories": [
            {
                "id": cat,
                "name": cat.replace("_", " ").title(),
                "tool_count": sum(1 for t in AVAILABLE_TOOLS.values() if t["category"] == cat)
            }
            for cat in sorted(categories)
        ]
    }

@router.post("/batch")
async def batch_invoke_tools(
    invocations: List[ToolInvocation],
    current_user: dict = Depends(get_current_user)
):
    """複数ツールのバッチ実行"""
    
    results = []
    for invocation in invocations:
        try:
            result = await invoke_tool(
                invocation.tool_id,
                invocation,
                current_user
            )
            results.append(result)
        except Exception as e:
            results.append({
                "tool_id": invocation.tool_id,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "total": len(invocations),
        "successful": sum(1 for r in results if r.get("status") == "success"),
        "failed": sum(1 for r in results if r.get("status") == "error"),
        "results": results
    }

async def execute_tool(tool_id: str, parameters: Dict[str, Any]) -> Dict:
    """ツールの実行（モック実装）"""
    
    # 各ツールのモック実装
    if tool_id == "shopify_export":
        return {
            "file_url": f"/exports/shopify_{parameters['data_type']}.{parameters['format']}",
            "row_count": 150,
            "file_size": "2.5MB"
        }
    
    elif tool_id == "gmail_send":
        return {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "status": "sent",
            "recipients": parameters["to"]
        }
    
    elif tool_id == "stripe_create_invoice":
        return {
            "invoice_id": f"inv_{datetime.utcnow().timestamp()}",
            "amount": parameters["amount"],
            "status": "pending",
            "url": f"https://stripe.com/invoices/inv_xxx"
        }
    
    elif tool_id == "slack_post_message":
        return {
            "message_id": f"msg_{datetime.utcnow().timestamp()}",
            "channel": parameters["channel"],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    elif tool_id == "notion_create_page":
        return {
            "page_id": f"page_{datetime.utcnow().timestamp()}",
            "url": f"https://notion.so/page_xxx",
            "title": parameters["title"]
        }
    
    else:
        raise ValueError(f"Unknown tool: {tool_id}")