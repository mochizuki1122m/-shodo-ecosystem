"""
分散トレーシングシステム
OpenTelemetryを使用したトレース収集
"""

import os
from typing import Optional, Dict, Any, Callable
from functools import wraps
import json

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# 環境変数から設定を読み込み
TRACING_ENABLED = os.getenv("TRACING_ENABLED", "true").lower() == "true"
JAEGER_ENDPOINT = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "localhost:4317")
SERVICE_NAME_ENV = os.getenv("SERVICE_NAME", "shodo-ecosystem")
SERVICE_VERSION_ENV = os.getenv("SERVICE_VERSION", "1.0.0")

class TracingConfig:
    """トレーシング設定"""
    
    @staticmethod
    def create_resource() -> Resource:
        """リソース情報の作成"""
        return Resource.create({
            SERVICE_NAME: SERVICE_NAME_ENV,
            SERVICE_VERSION: SERVICE_VERSION_ENV,
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            "host.name": os.getenv("HOSTNAME", "localhost"),
        })
    
    @staticmethod
    def setup_tracer_provider() -> TracerProvider:
        """TracerProviderの設定"""
        resource = TracingConfig.create_resource()
        provider = TracerProvider(resource=resource)
        
        if not TRACING_ENABLED:
            # トレーシング無効時はコンソール出力のみ
            provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )
        else:
            # Jaegerエクスポーター
            if JAEGER_ENDPOINT:
                jaeger_exporter = JaegerExporter(
                    agent_host_name=JAEGER_ENDPOINT.split("://")[1].split(":")[0],
                    agent_port=6831,
                    collector_endpoint=JAEGER_ENDPOINT,
                )
                provider.add_span_processor(
                    BatchSpanProcessor(jaeger_exporter)
                )
            
            # OTLPエクスポーター
            if OTLP_ENDPOINT:
                otlp_exporter = OTLPSpanExporter(
                    endpoint=OTLP_ENDPOINT,
                    insecure=True,
                )
                provider.add_span_processor(
                    BatchSpanProcessor(otlp_exporter)
                )
        
        trace.set_tracer_provider(provider)
        return provider
    
    @staticmethod
    def setup_meter_provider() -> MeterProvider:
        """MeterProviderの設定"""
        resource = TracingConfig.create_resource()
        
        # Prometheusメトリクスリーダー
        prometheus_reader = PrometheusMetricReader()
        
        # OTLPメトリクスエクスポーター
        if OTLP_ENDPOINT and TRACING_ENABLED:
            otlp_exporter = OTLPMetricExporter(
                endpoint=OTLP_ENDPOINT,
                insecure=True,
            )
            provider = MeterProvider(
                resource=resource,
                metric_readers=[prometheus_reader],
                metric_exporters=[otlp_exporter],
            )
        else:
            provider = MeterProvider(
                resource=resource,
                metric_readers=[prometheus_reader],
            )
        
        metrics.set_meter_provider(provider)
        return provider

class Tracer:
    """トレーサークラス"""
    
    def __init__(self, name: str = __name__):
        self.tracer = trace.get_tracer(name)
        self.meter = metrics.get_meter(name)
    
    def span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """スパンコンテキストマネージャー"""
        return self.tracer.start_as_current_span(
            name,
            kind=kind,
            attributes=attributes or {}
        )
    
    def trace(
        self,
        name: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """トレースデコレータ"""
        def decorator(func):
            span_name = name or f"{func.__module__}.{func.__name__}"
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.span(span_name, kind, attributes) as span:
                    try:
                        # 引数を属性として記録
                        span.set_attribute("function.args_count", len(args))
                        span.set_attribute("function.kwargs_count", len(kwargs))
                        
                        result = await func(*args, **kwargs)
                        
                        # 成功ステータス
                        span.set_status(Status(StatusCode.OK))
                        
                        return result
                    
                    except Exception as e:
                        # エラー情報を記録
                        span.record_exception(e)
                        span.set_status(
                            Status(StatusCode.ERROR, str(e))
                        )
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.span(span_name, kind, attributes) as span:
                    try:
                        # 引数を属性として記録
                        span.set_attribute("function.args_count", len(args))
                        span.set_attribute("function.kwargs_count", len(kwargs))
                        
                        result = func(*args, **kwargs)
                        
                        # 成功ステータス
                        span.set_status(Status(StatusCode.OK))
                        
                        return result
                    
                    except Exception as e:
                        # エラー情報を記録
                        span.record_exception(e)
                        span.set_status(
                            Status(StatusCode.ERROR, str(e))
                        )
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        raise
            
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """現在のスパンにイベントを追加"""
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes or {})
    
    def set_attribute(self, key: str, value: Any):
        """現在のスパンに属性を設定"""
        span = trace.get_current_span()
        if span:
            span.set_attribute(key, value)
    
    def set_attributes(self, attributes: Dict[str, Any]):
        """現在のスパンに複数の属性を設定"""
        span = trace.get_current_span()
        if span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
    
    def record_exception(self, exception: Exception):
        """現在のスパンに例外を記録"""
        span = trace.get_current_span()
        if span:
            span.record_exception(exception)
            span.set_status(Status(StatusCode.ERROR, str(exception)))

class DistributedTracing:
    """分散トレーシング管理"""
    
    @staticmethod
    def initialize(app=None):
        """トレーシングの初期化"""
        # TracerProviderの設定
        TracingConfig.setup_tracer_provider()
        
        # MeterProviderの設定
        TracingConfig.setup_meter_provider()
        
        # プロパゲーターの設定
        set_global_textmap(TraceContextTextMapPropagator())
        
        # 自動インストルメンテーション
        if app:
            # FastAPI
            FastAPIInstrumentor.instrument_app(app)
        
        # HTTPクライアント
        HTTPXClientInstrumentor().instrument()
        
        # データベース（SQLAlchemy）
        # SQLAlchemyInstrumentor().instrument()
        
        # Redis
        # RedisInstrumentor().instrument()
        
        # ロギング
        LoggingInstrumentor().instrument(set_logging_format=True)
    
    @staticmethod
    def extract_trace_context(headers: Dict[str, str]) -> Optional[Dict[str, str]]:
        """ヘッダーからトレースコンテキストを抽出"""
        propagator = TraceContextTextMapPropagator()
        context = {}
        propagator.extract(carrier=headers)
        
        span = trace.get_current_span()
        if span:
            span_context = span.get_span_context()
            context = {
                "trace_id": format(span_context.trace_id, "032x"),
                "span_id": format(span_context.span_id, "016x"),
                "trace_flags": format(span_context.trace_flags, "02x"),
            }
        
        return context if context else None
    
    @staticmethod
    def inject_trace_context(headers: Dict[str, str]) -> Dict[str, str]:
        """ヘッダーにトレースコンテキストを注入"""
        propagator = TraceContextTextMapPropagator()
        propagator.inject(carrier=headers)
        return headers

# カスタムスパンプロセッサー
class CustomSpanProcessor(BatchSpanProcessor):
    """カスタムスパンプロセッサー"""
    
    def on_end(self, span):
        """スパン終了時の処理"""
        # カスタムロジック（例：特定のスパンをフィルタリング）
        if span.name.startswith("internal."):
            return  # 内部スパンはスキップ
        
        super().on_end(span)

# === 特定用途のトレーサー ===

class DatabaseTracer:
    """データベース操作用トレーサー"""
    
    def __init__(self):
        self.tracer = Tracer("database")
    
    def trace_query(self, query: str, params: Optional[Dict] = None):
        """SQLクエリのトレース"""
        with self.tracer.span(
            "db.query",
            kind=SpanKind.CLIENT,
            attributes={
                "db.statement": query[:1000],  # 長いクエリは切り詰め
                "db.type": "sql",
            }
        ) as span:
            if params:
                span.set_attribute("db.params_count", len(params))
            return span

class HTTPTracer:
    """HTTP操作用トレーサー"""
    
    def __init__(self):
        self.tracer = Tracer("http")
    
    def trace_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict] = None
    ):
        """HTTPリクエストのトレース"""
        with self.tracer.span(
            f"http.{method.lower()}",
            kind=SpanKind.CLIENT,
            attributes={
                "http.method": method,
                "http.url": url,
                "http.scheme": url.split("://")[0] if "://" in url else "http",
            }
        ) as span:
            if headers:
                span.set_attribute("http.request.header_count", len(headers))
            return span

class CacheTracer:
    """キャッシュ操作用トレーサー"""
    
    def __init__(self):
        self.tracer = Tracer("cache")
    
    def trace_operation(
        self,
        operation: str,
        key: str,
        cache_type: str = "redis"
    ):
        """キャッシュ操作のトレース"""
        with self.tracer.span(
            f"cache.{operation}",
            kind=SpanKind.CLIENT,
            attributes={
                "cache.key": key,
                "cache.type": cache_type,
                "cache.operation": operation,
            }
        ) as span:
            return span

# グローバルトレーサーインスタンス
tracer = Tracer(__name__)
db_tracer = DatabaseTracer()
http_tracer = HTTPTracer()
cache_tracer = CacheTracer()

# エクスポート
__all__ = [
    'TracingConfig',
    'Tracer',
    'DistributedTracing',
    'DatabaseTracer',
    'HTTPTracer',
    'CacheTracer',
    'tracer',
    'db_tracer',
    'http_tracer',
    'cache_tracer',
]