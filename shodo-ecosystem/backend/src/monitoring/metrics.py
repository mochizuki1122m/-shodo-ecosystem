"""
Prometheus メトリクス実装
「測れないものは改善できない」の原則に基づく包括的監視
"""

import time
from typing import Dict, Optional
from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST
)
import structlog
from functools import wraps

logger = structlog.get_logger()

# カスタムレジストリ（デフォルトメトリクスを除外）
registry = CollectorRegistry()

# === HTTP メトリクス ===
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=registry
)

# === 認証メトリクス ===
auth_attempts_total = Counter(
    'auth_attempts_total',
    'Total authentication attempts',
    ['method', 'status'],
    registry=registry
)

auth_tokens_issued_total = Counter(
    'auth_tokens_issued_total',
    'Total JWT tokens issued',
    ['type'],
    registry=registry
)

# === LPR メトリクス ===
lpr_tokens_issued_total = Counter(
    'lpr_tokens_issued_total',
    'Total LPR tokens issued',
    ['scope', 'user_type'],
    registry=registry
)

lpr_tokens_verified_total = Counter(
    'lpr_tokens_verified_total',
    'Total LPR token verifications',
    ['status'],
    registry=registry
)

lpr_tokens_revoked_total = Counter(
    'lpr_tokens_revoked_total',
    'Total LPR tokens revoked',
    ['reason'],
    registry=registry
)

lpr_active_tokens = Gauge(
    'lpr_active_tokens',
    'Currently active LPR tokens',
    registry=registry
)

# === NLP メトリクス ===
nlp_analyses_total = Counter(
    'nlp_analyses_total',
    'Total NLP analyses performed',
    ['engine', 'status'],
    registry=registry
)

nlp_processing_duration_seconds = Histogram(
    'nlp_processing_duration_seconds',
    'NLP processing time',
    ['engine'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

nlp_confidence_score = Histogram(
    'nlp_confidence_score',
    'NLP analysis confidence scores',
    ['engine'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    registry=registry
)

# === Preview メトリクス ===
preview_generations_total = Counter(
    'preview_generations_total',
    'Total preview generations',
    ['service', 'status'],
    registry=registry
)

preview_applications_total = Counter(
    'preview_applications_total',
    'Total preview applications to production',
    ['service', 'status'],
    registry=registry
)

preview_processing_duration_seconds = Histogram(
    'preview_processing_duration_seconds',
    'Preview generation time',
    ['service'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=registry
)

# === データベース/Redis メトリクス ===
db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections',
    ['database'],
    registry=registry
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=registry
)

redis_operations_total = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation', 'status'],
    registry=registry
)

# === システムメトリクス ===
system_info = Info(
    'system_info',
    'System information',
    registry=registry
)

rate_limit_hits_total = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint', 'client_type'],
    registry=registry
)

# === エラーメトリクス ===
errors_total = Counter(
    'errors_total',
    'Total errors by type',
    ['error_type', 'component'],
    registry=registry
)

# === 相関ID追跡 ===
correlation_requests_total = Counter(
    'correlation_requests_total',
    'Total requests with correlation tracking',
    ['component'],
    registry=registry
)

class MetricsCollector:
    """メトリクス収集ユーティリティクラス"""
    
    @staticmethod
    def record_http_request(method: str, endpoint: str, status_code: int, duration: float):
        """HTTP リクエストメトリクスを記録"""
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    @staticmethod
    def record_auth_attempt(method: str, success: bool):
        """認証試行を記録"""
        status = "success" if success else "failure"
        auth_attempts_total.labels(method=method, status=status).inc()
    
    @staticmethod
    def record_token_issued(token_type: str):
        """トークン発行を記録"""
        auth_tokens_issued_total.labels(type=token_type).inc()
    
    @staticmethod
    def record_lpr_issued(scope: str, user_type: str):
        """LPR トークン発行を記録"""
        lpr_tokens_issued_total.labels(scope=scope, user_type=user_type).inc()
        lpr_active_tokens.inc()
    
    @staticmethod
    def record_lpr_verified(success: bool):
        """LPR 検証を記録"""
        status = "success" if success else "failure"
        lpr_tokens_verified_total.labels(status=status).inc()
    
    @staticmethod
    def record_lpr_revoked(reason: str):
        """LPR 取り消しを記録"""
        lpr_tokens_revoked_total.labels(reason=reason).inc()
        lpr_active_tokens.dec()
    
    @staticmethod
    def record_nlp_analysis(engine: str, success: bool, duration: float, confidence: Optional[float] = None):
        """NLP 解析を記録"""
        status = "success" if success else "failure"
        nlp_analyses_total.labels(engine=engine, status=status).inc()
        nlp_processing_duration_seconds.labels(engine=engine).observe(duration)
        
        if confidence is not None:
            nlp_confidence_score.labels(engine=engine).observe(confidence)
    
    @staticmethod
    def record_preview_generation(service: str, success: bool, duration: float):
        """プレビュー生成を記録"""
        status = "success" if success else "failure"
        preview_generations_total.labels(service=service, status=status).inc()
        preview_processing_duration_seconds.labels(service=service).observe(duration)
    
    @staticmethod
    def record_preview_application(service: str, success: bool):
        """プレビュー適用を記録"""
        status = "success" if success else "failure"
        preview_applications_total.labels(service=service, status=status).inc()
    
    @staticmethod
    def record_db_query(operation: str, duration: float):
        """データベースクエリを記録"""
        db_query_duration_seconds.labels(operation=operation).observe(duration)
    
    @staticmethod
    def record_redis_operation(operation: str, success: bool):
        """Redis 操作を記録"""
        status = "success" if success else "failure"
        redis_operations_total.labels(operation=operation, status=status).inc()
    
    @staticmethod
    def record_rate_limit_hit(endpoint: str, client_type: str):
        """レート制限ヒットを記録"""
        rate_limit_hits_total.labels(endpoint=endpoint, client_type=client_type).inc()
    
    @staticmethod
    def record_error(error_type: str, component: str):
        """エラーを記録"""
        errors_total.labels(error_type=error_type, component=component).inc()
    
    @staticmethod
    def record_correlation_request(component: str):
        """相関ID付きリクエストを記録"""
        correlation_requests_total.labels(component=component).inc()
    
    @staticmethod
    def set_db_connections(database: str, count: int):
        """データベース接続数を設定"""
        db_connections_active.labels(database=database).set(count)
    
    @staticmethod
    def set_system_info(info: Dict[str, str]):
        """システム情報を設定"""
        system_info.info(info)

def metrics_middleware(request_handler):
    """HTTP リクエストメトリクス収集ミドルウェア"""
    @wraps(request_handler)
    async def wrapper(request, *args, **kwargs):
        start_time = time.time()
        status_code = 200
        
        try:
            response = await request_handler(request, *args, **kwargs)
            if hasattr(response, 'status_code'):
                status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            MetricsCollector.record_error(
                error_type=type(e).__name__,
                component="http"
            )
            raise
        finally:
            duration = time.time() - start_time
            MetricsCollector.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=status_code,
                duration=duration
            )
    
    return wrapper

def get_metrics() -> str:
    """Prometheus メトリクスを取得"""
    return generate_latest(registry)

def get_metrics_json() -> dict:
    """JSON形式のメトリクス（最小構成）"""
    return {
        "registered_metrics": list(registry._names_to_collectors.keys())
    }

def get_metrics_content_type() -> str:
    """Prometheus メトリクスのContent-Typeを取得"""
    return CONTENT_TYPE_LATEST

# 初期化時にシステム情報を設定
def init_system_metrics(version: str, environment: str):
    """システムメトリクスを初期化"""
    MetricsCollector.set_system_info({
        "version": version,
        "environment": environment,
        "service": "shodo-ecosystem"
    })
    
    logger.info(
        "Metrics system initialized",
        version=version,
        environment=environment
    )