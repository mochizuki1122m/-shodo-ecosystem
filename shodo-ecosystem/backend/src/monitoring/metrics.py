"""
Prometheus metrics collection
MUST: Complete observability with RED metrics
"""

from typing import Optional, Callable
import time
from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()

# Create a custom registry
registry = CollectorRegistry()

# ===== HTTP Metrics (RED: Rate, Errors, Duration) =====

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry
)

http_request_size_bytes = Summary(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

http_response_size_bytes = Summary(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# ===== LPR Metrics =====

lpr_tokens_issued_total = Counter(
    'lpr_tokens_issued_total',
    'Total LPR tokens issued',
    ['service', 'purpose'],
    registry=registry
)

lpr_tokens_verified_total = Counter(
    'lpr_tokens_verified_total',
    'Total LPR token verifications',
    ['service', 'result'],
    registry=registry
)

lpr_tokens_revoked_total = Counter(
    'lpr_tokens_revoked_total',
    'Total LPR tokens revoked',
    ['reason'],
    registry=registry
)

lpr_operations_total = Counter(
    'lpr_operations_total',
    'Total LPR operations',
    ['service', 'operation', 'status'],
    registry=registry
)

lpr_operation_duration_seconds = Histogram(
    'lpr_operation_duration_seconds',
    'LPR operation duration',
    ['service', 'operation'],
    registry=registry
)

# ===== NLP Metrics =====

nlp_analyze_requests_total = Counter(
    'nlp_analyze_requests_total',
    'Total NLP analysis requests',
    ['mode', 'status'],
    registry=registry
)

nlp_analyze_duration_seconds = Histogram(
    'nlp_analyze_duration_seconds',
    'NLP analysis duration',
    ['mode', 'processing_path'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0),
    registry=registry
)

nlp_confidence_score = Histogram(
    'nlp_confidence_score',
    'NLP confidence score distribution',
    ['intent', 'service'],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=registry
)

# ===== Preview Metrics =====

preview_generation_total = Counter(
    'preview_generation_total',
    'Total preview generations',
    ['service', 'status'],
    registry=registry
)

preview_refinement_total = Counter(
    'preview_refinement_total',
    'Total preview refinements',
    ['service'],
    registry=registry
)

preview_apply_total = Counter(
    'preview_apply_total',
    'Total preview applications to production',
    ['service', 'status'],
    registry=registry
)

# ===== Database Metrics =====

db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections',
    ['database'],
    registry=registry
)

db_connections_idle = Gauge(
    'db_connections_idle',
    'Idle database connections',
    ['database'],
    registry=registry
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    registry=registry
)

# ===== Redis Metrics =====

redis_operations_total = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation', 'status'],
    registry=registry
)

redis_operation_duration_seconds = Histogram(
    'redis_operation_duration_seconds',
    'Redis operation duration',
    ['operation'],
    registry=registry
)

redis_memory_usage_bytes = Gauge(
    'redis_memory_usage_bytes',
    'Redis memory usage',
    registry=registry
)

# ===== Celery Task Metrics =====

celery_tasks_total = Counter(
    'celery_tasks_total',
    'Total Celery tasks',
    ['task', 'status'],
    registry=registry
)

celery_task_duration_seconds = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration',
    ['task'],
    registry=registry
)

celery_queue_length = Gauge(
    'celery_queue_length',
    'Celery queue length',
    ['queue'],
    registry=registry
)

# ===== System Metrics =====

system_info = Gauge(
    'system_info',
    'System information',
    ['version', 'environment'],
    registry=registry
)

# ===== SLO Metrics =====

slo_availability_ratio = Gauge(
    'slo_availability_ratio',
    'SLO availability ratio',
    registry=registry
)

slo_latency_p95_seconds = Gauge(
    'slo_latency_p95_seconds',
    'SLO P95 latency',
    ['endpoint'],
    registry=registry
)

slo_error_rate_ratio = Gauge(
    'slo_error_rate_ratio',
    'SLO error rate ratio',
    registry=registry
)

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP metrics
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics for each request"""
        
        # Start timer
        start_time = time.time()
        
        # Get endpoint path
        endpoint = self._normalize_path(request.url.path)
        method = request.method
        
        # Record request size
        content_length = request.headers.get("content-length", 0)
        http_request_size_bytes.labels(
            method=method,
            endpoint=endpoint
        ).observe(int(content_length))
        
        try:
            # Process request
            response = await call_next(request)
            status = response.status_code
            
        except Exception as e:
            # Record error
            status = 500
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status
            ).inc()
            raise
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        # Record response size
        response_length = response.headers.get("content-length", 0)
        http_response_size_bytes.labels(
            method=method,
            endpoint=endpoint
        ).observe(int(response_length))
        
        # Update SLO metrics
        self._update_slo_metrics(endpoint, status, duration)
        
        return response
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (remove IDs)"""
        # Replace UUIDs
        import re
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{id}',
            path
        )
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        return path
    
    def _update_slo_metrics(self, endpoint: str, status: int, duration: float):
        """Update SLO tracking metrics"""
        # This would be calculated from aggregated data
        # Placeholder implementation
        pass

def track_lpr_issued(service: str, purpose: str):
    """Track LPR token issuance"""
    lpr_tokens_issued_total.labels(
        service=service,
        purpose=purpose
    ).inc()

def track_lpr_verified(service: str, valid: bool):
    """Track LPR token verification"""
    lpr_tokens_verified_total.labels(
        service=service,
        result="valid" if valid else "invalid"
    ).inc()

def track_lpr_revoked(reason: str):
    """Track LPR token revocation"""
    lpr_tokens_revoked_total.labels(reason=reason).inc()

def track_lpr_operation(service: str, operation: str, duration: float, success: bool):
    """Track LPR operation"""
    lpr_operations_total.labels(
        service=service,
        operation=operation,
        status="success" if success else "failure"
    ).inc()
    
    lpr_operation_duration_seconds.labels(
        service=service,
        operation=operation
    ).observe(duration)

def track_nlp_analysis(mode: str, processing_path: str, duration: float, confidence: float, intent: str, service: str, success: bool):
    """Track NLP analysis"""
    nlp_analyze_requests_total.labels(
        mode=mode,
        status="success" if success else "failure"
    ).inc()
    
    nlp_analyze_duration_seconds.labels(
        mode=mode,
        processing_path=processing_path
    ).observe(duration)
    
    nlp_confidence_score.labels(
        intent=intent,
        service=service or "unknown"
    ).observe(confidence)

def track_preview_generation(service: str, success: bool):
    """Track preview generation"""
    preview_generation_total.labels(
        service=service,
        status="success" if success else "failure"
    ).inc()

def track_preview_refinement(service: str):
    """Track preview refinement"""
    preview_refinement_total.labels(service=service).inc()

def track_preview_apply(service: str, success: bool):
    """Track preview application"""
    preview_apply_total.labels(
        service=service,
        status="success" if success else "failure"
    ).inc()

def track_db_query(operation: str, table: str, duration: float):
    """Track database query"""
    db_query_duration_seconds.labels(
        operation=operation,
        table=table
    ).observe(duration)

def update_db_connections(database: str, active: int, idle: int):
    """Update database connection metrics"""
    db_connections_active.labels(database=database).set(active)
    db_connections_idle.labels(database=database).set(idle)

def track_redis_operation(operation: str, duration: float, success: bool):
    """Track Redis operation"""
    redis_operations_total.labels(
        operation=operation,
        status="success" if success else "failure"
    ).inc()
    
    redis_operation_duration_seconds.labels(
        operation=operation
    ).observe(duration)

def update_redis_memory(bytes_used: int):
    """Update Redis memory usage"""
    redis_memory_usage_bytes.set(bytes_used)

def track_celery_task(task_name: str, duration: float, success: bool):
    """Track Celery task"""
    celery_tasks_total.labels(
        task=task_name,
        status="success" if success else "failure"
    ).inc()
    
    celery_task_duration_seconds.labels(task=task_name).observe(duration)

def update_celery_queue_length(queue_name: str, length: int):
    """Update Celery queue length"""
    celery_queue_length.labels(queue=queue_name).set(length)

def init_system_metrics(version: str, environment: str):
    """Initialize system metrics"""
    system_info.labels(
        version=version,
        environment=environment
    ).set(1)

async def get_metrics() -> bytes:
    """Generate Prometheus metrics"""
    return generate_latest(registry)