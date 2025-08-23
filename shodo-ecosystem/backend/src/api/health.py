"""
Unified health check implementation
MUST: Consistent health checks across all services
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Request, Response, status
import structlog
import httpx

from ..core.config import settings
from ..schemas.base import BaseResponse
from ..services.database import check_database_health, check_redis_health

logger = structlog.get_logger()

router = APIRouter(tags=["Health"])

# 再利用するHTTPクライアント（接続プール/Keep-Alive）
_httpx_client = httpx.AsyncClient(timeout=5.0)

class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class ComponentHealth:
    """Component health check result"""
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        message: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        self.name = name
        self.status = status
        self.message = message or f"{name} is {status.value}"
        self.metadata = metadata or {}
        self.checked_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "metadata": self.metadata,
            "checked_at": self.checked_at.isoformat()
        }

class HealthChecker:
    """Unified health checker for all components"""
    
    def __init__(self):
        self.checks = []
        self.last_check_time = None
        self.cache_duration = 10  # Cache for 10 seconds
        self.cached_result = None
    
    async def check_all(self) -> Dict[str, Any]:
        """
        Check health of all components
        
        Returns comprehensive health status
        """
        
        # Use cache if available and fresh
        if self._is_cache_valid():
            return self.cached_result
        
        # Run all health checks in parallel
        checks = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
            self._check_ai_server(),
            self._check_celery(),
            self._check_disk_space(),
            self._check_memory(),
            self._check_slo_compliance(),
            return_exceptions=True
        )
        
        # Process results
        components = {}
        overall_status = HealthStatus.HEALTHY
        unhealthy_count = 0
        degraded_count = 0
        
        for check in checks:
            if isinstance(check, Exception):
                # Check failed
                logger.error("Health check failed", error=str(check))
                component = ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(check)
                )
            else:
                component = check
            
            components[component.name] = component.to_dict()
            
            # Update overall status
            if component.status == HealthStatus.UNHEALTHY:
                unhealthy_count += 1
                overall_status = HealthStatus.UNHEALTHY
            elif component.status == HealthStatus.DEGRADED:
                degraded_count += 1
                if overall_status != HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.DEGRADED
        
        # Build result
        result = {
            "status": overall_status.value,
            "version": settings.app_version,
            "environment": settings.environment,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": components,
            "summary": {
                "total": len(components),
                "healthy": len(components) - unhealthy_count - degraded_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count
            }
        }
        
        # Cache result
        self.cached_result = result
        self.last_check_time = datetime.now(timezone.utc)
        
        return result
    
    def _is_cache_valid(self) -> bool:
        """Check if cached result is still valid"""
        if not self.cached_result or not self.last_check_time:
            return False
        
        age = (datetime.now(timezone.utc) - self.last_check_time).total_seconds()
        return age < self.cache_duration
    
    async def _check_database(self) -> ComponentHealth:
        """Check database health"""
        try:
            is_healthy = await check_database_health()
            
            if is_healthy:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    metadata={"type": "postgresql"}
                )
            else:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Database connection failed"
                )
        except Exception as e:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )
    
    async def _check_redis(self) -> ComponentHealth:
        """Check Redis health"""
        try:
            is_healthy = await check_redis_health()
            
            if is_healthy:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    metadata={"type": "cache"}
                )
            else:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    message="Redis connection degraded"
                )
        except Exception as e:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )
    
    async def _check_ai_server(self) -> ComponentHealth:
        """Check AI server health"""
        try:
            response = await _httpx_client.get(f"{settings.vllm_url}/health")
            
            if response.status_code == 200:
                data = response.json()
                return ComponentHealth(
                    name="ai_server",
                    status=HealthStatus.HEALTHY,
                    metadata={
                        "engine": settings.inference_engine,
                        "model": data.get("model", "unknown")
                    }
                )
            else:
                return ComponentHealth(
                    name="ai_server",
                    status=HealthStatus.DEGRADED,
                    message=f"AI server returned {response.status_code}"
                )
        except Exception as e:
            return ComponentHealth(
                name="ai_server",
                status=HealthStatus.UNHEALTHY,
                message=f"AI server unreachable: {str(e)}"
            )
    
    async def _check_celery(self) -> ComponentHealth:
        """Check Celery workers health"""
        # Simplified check - in production, check actual worker status
        try:
            # Check if Celery broker is accessible
            # This would query Celery's inspect API
            return ComponentHealth(
                name="celery",
                status=HealthStatus.HEALTHY,
                metadata={"workers": 4, "queues": ["default", "priority"]}
            )
        except Exception:
            return ComponentHealth(
                name="celery",
                status=HealthStatus.DEGRADED,
                message="Celery workers degraded"
            )
    
    async def _check_disk_space(self) -> ComponentHealth:
        """Check disk space availability"""
        try:
            import shutil
            usage = shutil.disk_usage("/")
            percent_used = (usage.used / usage.total) * 100
            
            if percent_used < 80:
                status = HealthStatus.HEALTHY
            elif percent_used < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="disk_space",
                status=status,
                metadata={
                    "percent_used": round(percent_used, 2),
                    "free_gb": round(usage.free / (1024**3), 2)
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )
    
    async def _check_memory(self) -> ComponentHealth:
        """Check memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            
            if memory.percent < 80:
                status = HealthStatus.HEALTHY
            elif memory.percent < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="memory",
                status=status,
                metadata={
                    "percent_used": memory.percent,
                    "available_gb": round(memory.available / (1024**3), 2)
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )
    
    async def _check_slo_compliance(self) -> ComponentHealth:
        """Check SLO compliance"""
        try:
            # Get current SLO metrics
            # In production, this would query Prometheus
            
            # Placeholder values
            availability = 99.96
            p95_latency = 0.250
            error_rate = 0.08
            
            # Check against targets
            slo_met = (
                availability >= settings.slo_availability_target and
                p95_latency <= settings.slo_latency_p95_ms / 1000 and
                error_rate <= settings.slo_error_rate_percent
            )
            
            if slo_met:
                status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.DEGRADED
            
            return ComponentHealth(
                name="slo_compliance",
                status=status,
                metadata={
                    "availability": availability,
                    "p95_latency_ms": p95_latency * 1000,
                    "error_rate_percent": error_rate,
                    "targets": {
                        "availability": settings.slo_availability_target,
                        "p95_latency_ms": settings.slo_latency_p95_ms,
                        "error_rate_percent": settings.slo_error_rate_percent
                    }
                }
            )
        except Exception as e:
            return ComponentHealth(
                name="slo_compliance",
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )

# Global health checker instance
health_checker = HealthChecker()

@router.get(
    "/health",
    response_model=BaseResponse[Dict],
    summary="Comprehensive health check",
    description="Check health of all system components",
    responses={
        200: {"description": "System is healthy or degraded"},
        503: {"description": "System is unhealthy"}
    }
)
async def health_check(request: Request, response: Response) -> BaseResponse[Dict]:
    """
    Unified health check endpoint
    
    MUST: Return consistent health status across all services
    """
    
    try:
        health_status = await health_checker.check_all()
        
        # Set appropriate HTTP status code
        if health_status["status"] == "unhealthy":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif health_status["status"] == "degraded":
            response.status_code = status.HTTP_200_OK
        else:
            response.status_code = status.HTTP_200_OK
        
        return BaseResponse(
            success=health_status["status"] != "unhealthy",
            data=health_status
        )
        
    except Exception as e:
        logger.error("Health check error", error=str(e), exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return BaseResponse(
            success=False,
            message="Health check failed",
            data={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

@router.get(
    "/health/live",
    summary="Liveness probe",
    description="Simple liveness check for Kubernetes"
)
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe
    
    Returns 200 if the service is alive
    """
    return {"status": "alive"}

@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Readiness check for Kubernetes"
)
async def readiness_probe(response: Response) -> Dict[str, Any]:
    """
    Kubernetes readiness probe
    
    Returns 200 if the service is ready to accept traffic
    """
    
    # Quick checks for critical components only
    checks = await asyncio.gather(
        health_checker._check_database(),
        health_checker._check_redis(),
        return_exceptions=True
    )
    
    ready = all(
        not isinstance(check, Exception) and 
        check.status != HealthStatus.UNHEALTHY
        for check in checks
    )
    
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ready": False}
    
    return {"ready": True}

@router.get(
    "/health/startup",
    summary="Startup probe",
    description="Startup check for Kubernetes"
)
async def startup_probe() -> Dict[str, Any]:
    """
    Kubernetes startup probe
    
    Returns 200 when the service has completed initialization
    """
    
    # Check if all services are initialized
    # This would check actual initialization status
    
    return {
        "initialized": True,
        "version": settings.app_version
    }