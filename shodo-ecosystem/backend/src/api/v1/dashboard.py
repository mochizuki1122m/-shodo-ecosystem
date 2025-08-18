"""
ダッシュボードAPIエンドポイント
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
import random
from .auth import get_current_user

router = APIRouter()

# サービス情報（モックデータ）
AVAILABLE_SERVICES = {
    "shopify": {
        "name": "Shopify",
        "icon": "🛍️",
        "description": "Eコマースプラットフォーム",
        "status": "connected",
        "endpoints": ["products", "orders", "customers", "inventory"]
    },
    "gmail": {
        "name": "Gmail",
        "icon": "📧",
        "description": "メールサービス",
        "status": "connected",
        "endpoints": ["send", "receive", "search", "labels"]
    },
    "stripe": {
        "name": "Stripe",
        "icon": "💳",
        "description": "決済プラットフォーム",
        "status": "connected",
        "endpoints": ["payments", "customers", "subscriptions", "invoices"]
    },
    "slack": {
        "name": "Slack",
        "icon": "💬",
        "description": "チームコミュニケーション",
        "status": "disconnected",
        "endpoints": ["messages", "channels", "users", "files"]
    },
    "notion": {
        "name": "Notion",
        "icon": "📝",
        "description": "ノート・ドキュメント管理",
        "status": "connected",
        "endpoints": ["pages", "databases", "blocks", "users"]
    }
}

class ServiceStatus(BaseModel):
    id: str
    name: str
    icon: str
    description: str
    status: str  # "connected", "disconnected", "error"
    last_sync: Optional[datetime]
    metrics: Dict[str, int]

class DashboardStats(BaseModel):
    total_services: int
    connected_services: int
    total_operations: int
    operations_today: int
    active_automations: int
    error_rate: float

class ActivityLog(BaseModel):
    id: str
    timestamp: datetime
    service: str
    action: str
    status: str
    details: Optional[Dict]

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """ダッシュボード統計情報の取得"""
    
    connected_count = sum(1 for s in AVAILABLE_SERVICES.values() if s["status"] == "connected")
    
    return DashboardStats(
        total_services=len(AVAILABLE_SERVICES),
        connected_services=connected_count,
        total_operations=random.randint(1000, 5000),
        operations_today=random.randint(50, 200),
        active_automations=random.randint(5, 20),
        error_rate=random.uniform(0.01, 0.05)
    )

@router.get("/services", response_model=List[ServiceStatus])
async def get_services(current_user: dict = Depends(get_current_user)):
    """接続済みサービス一覧の取得"""
    
    services = []
    for service_id, service_info in AVAILABLE_SERVICES.items():
        # メトリクスの生成（モック）
        metrics = {
            "requests_today": random.randint(10, 100),
            "avg_response_time": random.randint(50, 500),
            "success_rate": random.uniform(95, 99.9)
        }
        
        # 最終同期時刻（接続済みの場合）
        last_sync = None
        if service_info["status"] == "connected":
            last_sync = datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
        
        services.append(ServiceStatus(
            id=service_id,
            name=service_info["name"],
            icon=service_info["icon"],
            description=service_info["description"],
            status=service_info["status"],
            last_sync=last_sync,
            metrics=metrics
        ))
    
    return services

@router.get("/services/{service_id}/status", response_model=ServiceStatus)
async def get_service_status(
    service_id: str,
    current_user: dict = Depends(get_current_user)
):
    """特定サービスのステータス取得"""
    
    if service_id not in AVAILABLE_SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")
    
    service_info = AVAILABLE_SERVICES[service_id]
    
    # 詳細メトリクスの生成
    metrics = {
        "requests_today": random.randint(10, 100),
        "requests_week": random.randint(100, 1000),
        "requests_month": random.randint(1000, 10000),
        "avg_response_time": random.randint(50, 500),
        "p95_response_time": random.randint(100, 1000),
        "p99_response_time": random.randint(200, 2000),
        "success_rate": random.uniform(95, 99.9),
        "error_count": random.randint(0, 10)
    }
    
    last_sync = None
    if service_info["status"] == "connected":
        last_sync = datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
    
    return ServiceStatus(
        id=service_id,
        name=service_info["name"],
        icon=service_info["icon"],
        description=service_info["description"],
        status=service_info["status"],
        last_sync=last_sync,
        metrics=metrics
    )

@router.post("/services/{service_id}/connect")
async def connect_service(
    service_id: str,
    current_user: dict = Depends(get_current_user)
):
    """サービスの接続"""
    
    if service_id not in AVAILABLE_SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # 実際の実装では OAuth フローなどを実行
    AVAILABLE_SERVICES[service_id]["status"] = "connected"
    
    return {
        "message": f"Service {service_id} connected successfully",
        "service_id": service_id,
        "status": "connected"
    }

@router.post("/services/{service_id}/disconnect")
async def disconnect_service(
    service_id: str,
    current_user: dict = Depends(get_current_user)
):
    """サービスの切断"""
    
    if service_id not in AVAILABLE_SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")
    
    AVAILABLE_SERVICES[service_id]["status"] = "disconnected"
    
    return {
        "message": f"Service {service_id} disconnected successfully",
        "service_id": service_id,
        "status": "disconnected"
    }

@router.get("/activity", response_model=List[ActivityLog])
async def get_activity_logs(
    limit: int = 20,
    service: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """アクティビティログの取得"""
    
    logs = []
    actions = ["export", "import", "sync", "update", "create", "delete"]
    statuses = ["success", "success", "success", "warning", "error"]  # successが多め
    
    for i in range(limit):
        service_id = service if service else random.choice(list(AVAILABLE_SERVICES.keys()))
        
        if service and service not in AVAILABLE_SERVICES:
            continue
        
        log = ActivityLog(
            id=f"log_{i}",
            timestamp=datetime.utcnow() - timedelta(minutes=i * 5),
            service=service_id,
            action=random.choice(actions),
            status=random.choice(statuses),
            details={
                "items_processed": random.randint(1, 100),
                "duration_ms": random.randint(100, 5000)
            }
        )
        logs.append(log)
    
    return logs

@router.get("/metrics")
async def get_metrics(
    period: str = "day",  # "hour", "day", "week", "month"
    current_user: dict = Depends(get_current_user)
):
    """メトリクス情報の取得"""
    
    # 期間に応じたデータポイント数
    data_points = {
        "hour": 60,
        "day": 24,
        "week": 7,
        "month": 30
    }.get(period, 24)
    
    # 時系列データの生成
    now = datetime.utcnow()
    metrics_data = []
    
    for i in range(data_points):
        if period == "hour":
            timestamp = now - timedelta(minutes=i)
        elif period == "day":
            timestamp = now - timedelta(hours=i)
        elif period == "week":
            timestamp = now - timedelta(days=i)
        else:  # month
            timestamp = now - timedelta(days=i)
        
        metrics_data.append({
            "timestamp": timestamp,
            "requests": random.randint(50, 200),
            "errors": random.randint(0, 10),
            "response_time": random.uniform(50, 500),
            "active_users": random.randint(10, 50)
        })
    
    return {
        "period": period,
        "data": metrics_data[::-1],  # 古い順に並び替え
        "summary": {
            "total_requests": sum(m["requests"] for m in metrics_data),
            "total_errors": sum(m["errors"] for m in metrics_data),
            "avg_response_time": sum(m["response_time"] for m in metrics_data) / len(metrics_data),
            "peak_users": max(m["active_users"] for m in metrics_data)
        }
    }

@router.get("/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    """通知の取得"""
    
    notifications = [
        {
            "id": "notif_1",
            "type": "info",
            "title": "新機能のお知らせ",
            "message": "Notion連携が利用可能になりました",
            "timestamp": datetime.utcnow() - timedelta(hours=2),
            "read": False
        },
        {
            "id": "notif_2",
            "type": "warning",
            "title": "API制限の警告",
            "message": "Shopify APIの利用が制限に近づいています",
            "timestamp": datetime.utcnow() - timedelta(hours=5),
            "read": True
        },
        {
            "id": "notif_3",
            "type": "success",
            "title": "同期完了",
            "message": "すべてのサービスの同期が完了しました",
            "timestamp": datetime.utcnow() - timedelta(days=1),
            "read": True
        }
    ]
    
    return {"notifications": notifications, "unread_count": 1}

@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """通知を既読にする"""
    
    return {
        "message": "Notification marked as read",
        "notification_id": notification_id
    }