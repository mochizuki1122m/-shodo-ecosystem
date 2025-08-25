"""
包括的ヘルスチェックサービス
システムの各コンポーネントの健全性を監視
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import httpx
from sqlalchemy import text

from ..core.config import settings
from .database import get_db_engine, get_redis
from ..services.auth.lpr_service import get_lpr_service, LPRScope, DeviceFingerprint

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    response_time_ms: float
    details: Dict[str, Any]
    error: Optional[str] = None
    last_checked: float = 0

class HealthChecker:
    """システム全体のヘルスチェック管理"""
    
    def __init__(self):
        self.components: Dict[str, ComponentHealth] = {}
        self.check_timeout = 5.0  # 5秒タイムアウト
        
    async def check_database(self) -> ComponentHealth:
        """データベースのヘルスチェック"""
        start_time = time.time()
        
        try:
            engine = get_db_engine()
            if not engine:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=0,
                    details={"error": "Database engine not available"},
                    error="Database engine not available"
                )
            
            async with engine.begin() as conn:
                # 基本的な接続テスト
                result = await conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
                
                # データベース統計情報
                stats_result = await conn.execute(text("""
                    SELECT 
                        COUNT(*) as active_connections
                    FROM pg_stat_activity 
                    WHERE state = 'active'
                """))
                stats = stats_result.first()
                
                # テーブル存在確認
                tables_result = await conn.execute(text("""
                    SELECT COUNT(*) as table_count
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """))
                table_count = tables_result.scalar()
                
                response_time = (time.time() - start_time) * 1000
                
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    details={
                        "active_connections": stats[0] if stats else 0,
                        "table_count": table_count,
                        "database_url": settings.database_url.split('@')[1] if '@' in settings.database_url else "masked"
                    },
                    last_checked=time.time()
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Database health check failed: {e}")
            
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={"error": str(e)},
                error=str(e),
                last_checked=time.time()
            )
    
    async def check_redis(self) -> ComponentHealth:
        """Redisのヘルスチェック"""
        start_time = time.time()
        
        try:
            redis_client = get_redis()
            if not redis_client:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=0,
                    details={"status": "not_configured", "fallback": "memory_cache"},
                    last_checked=time.time()
                )
            
            # Redis ping テスト
            if hasattr(redis_client, 'ping'):
                if asyncio.iscoroutinefunction(redis_client.ping):
                    await redis_client.ping()
                else:
                    redis_client.ping()
            
            # Redis情報取得
            if hasattr(redis_client, 'info'):
                if asyncio.iscoroutinefunction(redis_client.info):
                    info = await redis_client.info()
                else:
                    info = redis_client.info()
                
                memory_usage = info.get('used_memory_human', 'unknown')
                connected_clients = info.get('connected_clients', 0)
            else:
                memory_usage = 'unknown'
                connected_clients = 0
            
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                details={
                    "memory_usage": memory_usage,
                    "connected_clients": connected_clients,
                    "redis_url": settings.redis_url
                },
                last_checked=time.time()
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.warning(f"Redis health check failed: {e}")
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                response_time_ms=response_time,
                details={
                    "error": str(e),
                    "fallback": "memory_cache"
                },
                error=str(e),
                last_checked=time.time()
            )
    
    async def check_ai_server(self) -> ComponentHealth:
        """AIサーバーのヘルスチェック"""
        start_time = time.time()
        
        try:
            headers = {}
            if settings.ai_internal_token:
                # バックエンド→AIサーバは内部トークンを自動付与
                headers["X-Internal-Token"] = settings.ai_internal_token
            async with httpx.AsyncClient(timeout=self.check_timeout, headers=headers) as client:
                response = await client.get(f"{settings.vllm_url}/health")
                response.raise_for_status()
                
                health_data = response.json()
                response_time = (time.time() - start_time) * 1000
                
                return ComponentHealth(
                    name="ai_server",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    details={
                        "url": settings.vllm_url,
                        "model": health_data.get("model", "unknown"),
                        "engine": health_data.get("engine", "unknown"),
                        "status": health_data.get("status", "unknown")
                    },
                    last_checked=time.time()
                )
                
        except httpx.TimeoutException:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="ai_server",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={"error": "Timeout", "url": settings.vllm_url},
                error="Request timeout",
                last_checked=time.time()
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.warning(f"AI server health check failed: {e}")
            
            return ComponentHealth(
                name="ai_server",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={
                    "error": str(e),
                    "url": settings.vllm_url
                },
                error=str(e),
                last_checked=time.time()
            )
    
    async def check_external_services(self) -> List[ComponentHealth]:
        """外部サービスのヘルスチェック"""
        results = []

        # 閉域/社内NW環境では外部到達性チェックを無効化可能
        if not settings.health_external_check_enabled:
            return results
        
        # インターネット接続テスト
        try:
            start_time = time.time()
            async with httpx.AsyncClient(timeout=self.check_timeout) as client:
                response = await client.get("https://httpbin.org/status/200")
                response.raise_for_status()
                
                response_time = (time.time() - start_time) * 1000
                results.append(ComponentHealth(
                    name="internet_connectivity",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    details={"test_url": "https://httpbin.org/status/200"},
                    last_checked=time.time()
                ))
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            results.append(ComponentHealth(
                name="internet_connectivity",
                status=HealthStatus.DEGRADED,
                response_time_ms=response_time,
                details={"error": str(e)},
                error=str(e),
                last_checked=time.time()
            ))
        
        return results
    
    async def check_system_resources(self) -> ComponentHealth:
        """システムリソースのチェック"""
        import psutil
        import os
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # メモリ使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # ディスク使用率
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # プロセス情報
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # ステータス判定
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 95:
                status = HealthStatus.UNHEALTHY
            elif cpu_percent > 70 or memory_percent > 80 or disk_percent > 85:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY
            
            return ComponentHealth(
                name="system_resources",
                status=status,
                response_time_ms=0,
                details={
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_percent": round(memory_percent, 2),
                    "disk_percent": round(disk_percent, 2),
                    "process_memory_mb": round(process_memory, 2),
                    "available_memory_gb": round(memory.available / 1024 / 1024 / 1024, 2)
                },
                last_checked=time.time()
            )
            
        except ImportError:
            # psutilが利用できない場合
            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                details={"error": "psutil not available"},
                last_checked=time.time()
            )
        except Exception as e:
            return ComponentHealth(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                details={"error": str(e)},
                error=str(e),
                last_checked=time.time()
            )
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """すべてのヘルスチェックを実行"""
        start_time = time.time()
        
        # 並列実行でパフォーマンス向上
        checks = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_ai_server(),
            self.check_lpr_system(),
            self.check_system_resources(),
            return_exceptions=True
        )
        
        # 外部サービスチェック（環境で無効化可能）
        external_checks = await self.check_external_services()
        
        # 結果の整理
        components = {}
        overall_status = HealthStatus.HEALTHY
        
        for check in checks:
            if isinstance(check, Exception):
                logger.error(f"Health check failed with exception: {check}")
                continue
                
            components[check.name] = {
                "status": check.status.value,
                "response_time_ms": check.response_time_ms,
                "details": check.details,
                "error": check.error,
                "last_checked": check.last_checked
            }
            
            # 全体ステータスの判定
            if check.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
            elif check.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED
        
        # 外部サービスの結果を追加
        for check in external_checks:
            components[check.name] = {
                "status": check.status.value,
                "response_time_ms": check.response_time_ms,
                "details": check.details,
                "error": check.error,
                "last_checked": check.last_checked
            }
        
        total_time = (time.time() - start_time) * 1000
        
        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "total_check_time_ms": round(total_time, 2),
            "components": components,
            "summary": self._generate_summary(components),
            "version": settings.app_version,
            "environment": settings.environment
        }

    async def check_lpr_system(self) -> ComponentHealth:
        """LPRシステムの実測ヘルスチェック"""
        start_time = time.time()
        try:
            svc = await get_lpr_service()
            # 軽量検証: 開発用のダミースコープで署名/検証ルートを通す
            fp = DeviceFingerprint(user_agent="health-check", accept_language="ja-JP")
            scope = LPRScope(method="GET", url_pattern="/health")
            # 署名→検証を最小限で通せるなら healthy とみなす
            # 注意: 本実装では issue/verify API を直接叩かず、サービス内部の基本関数を呼ぶ
            user_id = "system-health"
            issued = await svc.issue_token(
                service="health",
                purpose="liveness",
                scopes=[scope],
                device_fingerprint=fp,
                user_id=user_id,
                consent=True
            )
            token = issued.get("token")
            ok = False
            if token:
                result = await svc.verify_token(token, fp, scope)
                ok = bool(result.get("valid"))
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="lpr_system",
                status=HealthStatus.HEALTHY if ok else HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={"issue_ok": bool(token), "verify_ok": ok},
                last_checked=time.time()
            )
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="lpr_system",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                details={"error": str(e)},
                error=str(e),
                last_checked=time.time()
            )
    
    def _generate_summary(self, components: Dict[str, Any]) -> Dict[str, Any]:
        """ヘルスチェック結果のサマリーを生成"""
        total = len(components)
        healthy = sum(1 for c in components.values() if c["status"] == "healthy")
        degraded = sum(1 for c in components.values() if c["status"] == "degraded")
        unhealthy = sum(1 for c in components.values() if c["status"] == "unhealthy")
        
        return {
            "total_components": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "health_percentage": round((healthy / total) * 100, 2) if total > 0 else 0
        }

# グローバルインスタンス
health_checker = HealthChecker()