from ..core.config import settings
from ..schemas.base import BaseResponse
from ..services.database import check_database_health, check_redis_health
from ..core.config import settings as _settings

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
    
    async def _check_secrets(self) -> ComponentHealth:
        """Check if critical secrets are loaded (production gate)."""
        try:
            if _settings.is_production():
                ok = bool(getattr(_settings, 'jwt_private_key', None)) and bool(getattr(_settings, 'jwt_public_key', None))
                ok = ok and bool(getattr(_settings, 'encryption_key', None))
                if ok:
                    return ComponentHealth(name="secrets", status=HealthStatus.HEALTHY)
                return ComponentHealth(name="secrets", status=HealthStatus.UNHEALTHY, message="Critical secrets not loaded")
            # Non-production is lenient
            return ComponentHealth(name="secrets", status=HealthStatus.HEALTHY)
        except Exception as e:
            return ComponentHealth(name="secrets", status=HealthStatus.UNHEALTHY, message=str(e))

        checks = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
            self._check_ai_server(),
            self._check_secrets(),
            self._check_celery(),
            self._check_disk_space(),
            self._check_memory(),
            self._check_slo_compliance(),
            return_exceptions=True
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
        health_checker._check_secrets(),
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