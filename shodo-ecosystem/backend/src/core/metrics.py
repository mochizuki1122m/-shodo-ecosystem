"""
メトリクス収集システム
Prometheus形式のメトリクス収集と公開
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime
import time
import asyncio
from functools import wraps
from dataclasses import dataclass, field
from collections import defaultdict
import json

from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    CollectorRegistry, generate_latest,
    CONTENT_TYPE_LATEST
)
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse

# メトリクスレジストリ
registry = CollectorRegistry()

# === 基本メトリクス定義 ===

# HTTPリクエストメトリクス
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

# アプリケーションメトリクス
active_users = Gauge(
    'active_users',
    'Number of active users',
    registry=registry
)

active_sessions = Gauge(
    'active_sessions',
    'Number of active sessions',
    registry=registry
)

# NLP処理メトリクス
nlp_analyses_total = Counter(
    'nlp_analyses_total',
    'Total NLP analyses',
    ['analysis_type', 'status'],
    registry=registry
)

nlp_analysis_duration_seconds = Histogram(
    'nlp_analysis_duration_seconds',
    'NLP analysis duration in seconds',
    ['analysis_type'],
    registry=registry
)

nlp_tokens_processed = Counter(
    'nlp_tokens_processed_total',
    'Total tokens processed',
    ['model'],
    registry=registry
)

# プレビューメトリクス
preview_generations_total = Counter(
    'preview_generations_total',
    'Total preview generations',
    ['source_type', 'status'],
    registry=registry
)

preview_applications_total = Counter(
    'preview_applications_total',
    'Total preview applications',
    ['environment', 'status'],
    registry=registry
)

preview_rollbacks_total = Counter(
    'preview_rollbacks_total',
    'Total preview rollbacks',
    ['reason'],
    registry=registry
)

# SaaSコネクタメトリクス
connector_api_calls_total = Counter(
    'connector_api_calls_total',
    'Total connector API calls',
    ['connector', 'operation', 'status'],
    registry=registry
)

connector_api_duration_seconds = Histogram(
    'connector_api_duration_seconds',
    'Connector API call duration',
    ['connector', 'operation'],
    registry=registry
)

connector_rate_limit_hits = Counter(
    'connector_rate_limit_hits_total',
    'Rate limit hits',
    ['connector'],
    registry=registry
)

# データベースメトリクス
db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections',
    registry=registry
)

db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table'],
    registry=registry
)

db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation', 'table'],
    registry=registry
)

# キャッシュメトリクス
cache_hits_total = Counter(
    'cache_hits_total',
    'Cache hits',
    ['cache_type'],
    registry=registry
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Cache misses',
    ['cache_type'],
    registry=registry
)

cache_evictions_total = Counter(
    'cache_evictions_total',
    'Cache evictions',
    ['cache_type', 'reason'],
    registry=registry
)

# エラーメトリクス
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'component'],
    registry=registry
)

# === カスタムメトリクスコレクター ===

@dataclass
class MetricPoint:
    """メトリクスポイント"""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

class MetricsCollector:
    """メトリクス収集クラス"""
    
    def __init__(self):
        self.custom_metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        self.aggregators: Dict[str, Callable] = {}
    
    def record(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """メトリクスの記録"""
        point = MetricPoint(
            name=name,
            value=value,
            labels=labels or {},
            timestamp=datetime.utcnow()
        )
        self.custom_metrics[name].append(point)
    
    def increment(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """カウンターのインクリメント"""
        if name in ['http_requests_total', 'nlp_analyses_total', 'errors_total']:
            # Prometheusカウンターを使用
            counter = globals().get(name)
            if counter and labels:
                counter.labels(**labels).inc(value)
        else:
            self.record(name, value, labels)
    
    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """ヒストグラム/サマリーの観測"""
        if name in ['http_request_duration_seconds', 'nlp_analysis_duration_seconds']:
            # Prometheusヒストグラムを使用
            histogram = globals().get(name)
            if histogram and labels:
                histogram.labels(**labels).observe(value)
        else:
            self.record(name, value, labels)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """ゲージの設定"""
        if name in ['active_users', 'active_sessions', 'db_connections_active']:
            # Prometheusゲージを使用
            gauge = globals().get(name)
            if gauge:
                gauge.set(value)
        else:
            self.record(name, value, labels)
    
    def get_metrics(self, name: Optional[str] = None) -> List[MetricPoint]:
        """メトリクスの取得"""
        if name:
            return self.custom_metrics.get(name, [])
        
        all_metrics = []
        for metrics in self.custom_metrics.values():
            all_metrics.extend(metrics)
        return all_metrics
    
    def clear_old_metrics(self, retention_hours: int = 24):
        """古いメトリクスのクリア"""
        cutoff = datetime.utcnow().timestamp() - (retention_hours * 3600)
        
        for name in list(self.custom_metrics.keys()):
            self.custom_metrics[name] = [
                m for m in self.custom_metrics[name]
                if m.timestamp.timestamp() > cutoff
            ]
    
    def aggregate(self, name: str, aggregator: str = 'avg') -> Optional[float]:
        """メトリクスの集計"""
        metrics = self.custom_metrics.get(name, [])
        if not metrics:
            return None
        
        values = [m.value for m in metrics]
        
        if aggregator == 'sum':
            return sum(values)
        elif aggregator == 'avg':
            return sum(values) / len(values)
        elif aggregator == 'min':
            return min(values)
        elif aggregator == 'max':
            return max(values)
        elif aggregator == 'count':
            return len(values)
        else:
            return None

# グローバルコレクターインスタンス
metrics_collector = MetricsCollector()

# === デコレーター ===

def track_time(metric_name: str = None, labels: Optional[Dict[str, str]] = None):
    """実行時間追跡デコレータ"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                name = metric_name or f"{func.__module__}.{func.__name__}_duration"
                metrics_collector.observe(name, duration, labels)
                
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                metrics_collector.observe(name, duration, {**(labels or {}), 'status': 'error'})
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                name = metric_name or f"{func.__module__}.{func.__name__}_duration"
                metrics_collector.observe(name, duration, labels)
                
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                metrics_collector.observe(name, duration, {**(labels or {}), 'status': 'error'})
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def count_calls(metric_name: str = None, labels: Optional[Dict[str, str]] = None):
    """呼び出し回数カウントデコレータ"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}_calls"
            
            try:
                result = await func(*args, **kwargs)
                metrics_collector.increment(name, 1, {**(labels or {}), 'status': 'success'})
                return result
            
            except Exception as e:
                metrics_collector.increment(name, 1, {**(labels or {}), 'status': 'error'})
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}_calls"
            
            try:
                result = func(*args, **kwargs)
                metrics_collector.increment(name, 1, {**(labels or {}), 'status': 'success'})
                return result
            
            except Exception as e:
                metrics_collector.increment(name, 1, {**(labels or {}), 'status': 'error'})
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# === FastAPIミドルウェア ===

async def metrics_middleware(request: Request, call_next):
    """メトリクス収集ミドルウェア"""
    start_time = time.time()
    
    # リクエストサイズの記録
    content_length = request.headers.get('content-length')
    if content_length:
        http_request_size_bytes.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(int(content_length))
    
    try:
        # リクエスト処理
        response = await call_next(request)
        
        # レスポンスメトリクスの記録
        duration = time.time() - start_time
        
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        # レスポンスサイズの記録
        if hasattr(response, 'body'):
            http_response_size_bytes.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(len(response.body))
        
        return response
    
    except Exception as e:
        # エラーメトリクスの記録
        duration = time.time() - start_time
        
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=500
        ).inc()
        
        errors_total.labels(
            error_type=type(e).__name__,
            component='http'
        ).inc()
        
        raise

# === メトリクスエンドポイント ===

async def metrics_endpoint(request: Request) -> Response:
    """Prometheusメトリクスエンドポイント"""
    # Prometheusフォーマットでメトリクスを生成
    metrics_data = generate_latest(registry)
    
    return PlainTextResponse(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )

async def custom_metrics_endpoint(request: Request) -> Response:
    """カスタムメトリクスエンドポイント"""
    # カスタムメトリクスをJSON形式で返す
    metrics = {}
    
    for name, points in metrics_collector.custom_metrics.items():
        metrics[name] = [
            {
                'value': p.value,
                'labels': p.labels,
                'timestamp': p.timestamp.isoformat()
            }
            for p in points[-100:]  # 最新100件のみ
        ]
    
    return Response(
        content=json.dumps(metrics, indent=2),
        media_type='application/json'
    )

# === ヘルスメトリクス ===

class HealthMetrics:
    """ヘルスチェック用メトリクス"""
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """システムメトリクスの取得"""
        import psutil
        
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'network_connections': len(psutil.net_connections()),
        }
    
    @staticmethod
    def get_application_metrics() -> Dict[str, Any]:
        """アプリケーションメトリクスの取得"""
        return {
            'active_users': active_users._value.get(),
            'active_sessions': active_sessions._value.get(),
            'db_connections': db_connections_active._value.get(),
            'total_requests': sum(
                http_requests_total._metrics.values()
            ) if hasattr(http_requests_total, '_metrics') else 0,
        }

# エクスポート
__all__ = [
    'metrics_collector',
    'track_time',
    'count_calls',
    'metrics_middleware',
    'metrics_endpoint',
    'custom_metrics_endpoint',
    'HealthMetrics',
]