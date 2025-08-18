"""
OpenTelemetry tracing configuration
MUST: Distributed tracing across all services
"""

import logging
from typing import Optional, Dict, Any

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.trace import Status, StatusCode
from contextvars import ContextVar

from ..core.config import settings

logger = logging.getLogger(__name__)

# Context variable for current span
current_span_var: ContextVar[Optional[trace.Span]] = ContextVar(
    "current_span",
    default=None
)

class TracingConfig:
    """OpenTelemetry tracing configuration"""
    
    def __init__(self):
        self.tracer_provider = None
        self.meter_provider = None
        self.tracer = None
        self.meter = None
    
    def init_tracing(self, app=None):
        """
        Initialize OpenTelemetry tracing
        
        MUST: Configure for production with OTLP exporter
        """
        
        if not settings.tracing_enabled:
            logger.info("Tracing disabled")
            return
        
        # Create resource
        resource = Resource.create({
            SERVICE_NAME: settings.service_name,
            SERVICE_VERSION: settings.app_version,
            "environment": settings.environment,
            "deployment.environment": settings.environment,
        })
        
        # Initialize tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter
        if settings.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otlp_endpoint,
                insecure=not settings.is_production()
            )
            
            # Add batch processor
            span_processor = BatchSpanProcessor(
                otlp_exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                max_export_timeout_millis=30000,
            )
            self.tracer_provider.add_span_processor(span_processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer(
            settings.service_name,
            settings.app_version
        )
        
        # Set B3 propagator for compatibility
        set_global_textmap(B3MultiFormat())
        
        # Initialize metrics
        self._init_metrics()
        
        # Instrument libraries
        self._instrument_libraries(app)
        
        logger.info(
            "OpenTelemetry tracing initialized",
            endpoint=settings.otlp_endpoint,
            service=settings.service_name
        )
    
    def _init_metrics(self):
        """Initialize OpenTelemetry metrics"""
        
        if not settings.metrics_enabled:
            return
        
        # Create metric reader
        if settings.otlp_endpoint:
            metric_exporter = OTLPMetricExporter(
                endpoint=settings.otlp_endpoint,
                insecure=not settings.is_production()
            )
            
            metric_reader = PeriodicExportingMetricReader(
                exporter=metric_exporter,
                export_interval_millis=60000,  # 1 minute
            )
            
            # Create meter provider
            self.meter_provider = MeterProvider(
                resource=Resource.create({
                    SERVICE_NAME: settings.service_name,
                    SERVICE_VERSION: settings.app_version,
                }),
                metric_readers=[metric_reader]
            )
            
            # Set global meter provider
            metrics.set_meter_provider(self.meter_provider)
            
            # Get meter
            self.meter = metrics.get_meter(
                settings.service_name,
                settings.app_version
            )
    
    def _instrument_libraries(self, app=None):
        """Instrument libraries for automatic tracing"""
        
        # FastAPI
        if app:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=self.tracer_provider,
                excluded_urls="/health,/metrics"
            )
        
        # HTTP client (httpx)
        HTTPXClientInstrumentor().instrument(
            tracer_provider=self.tracer_provider
        )
        
        # SQLAlchemy
        # Note: Pass engine instance when available
        # SQLAlchemyInstrumentor().instrument(
        #     engine=engine,
        #     tracer_provider=self.tracer_provider
        # )
        
        # Redis
        RedisInstrumentor().instrument(
            tracer_provider=self.tracer_provider
        )
        
        # Celery
        CeleryInstrumentor().instrument(
            tracer_provider=self.tracer_provider
        )
        
        # Logging
        LoggingInstrumentor().instrument(
            tracer_provider=self.tracer_provider,
            set_logging_format=True
        )

# Global tracing configuration
tracing_config = TracingConfig()

def init_tracing(app=None):
    """Initialize tracing for the application"""
    tracing_config.init_tracing(app)

def get_tracer() -> trace.Tracer:
    """Get the configured tracer"""
    if tracing_config.tracer:
        return tracing_config.tracer
    return trace.get_tracer(__name__)

def get_current_span() -> Optional[trace.Span]:
    """Get the current active span"""
    span = current_span_var.get()
    if span:
        return span
    return trace.get_current_span()

def create_span(
    name: str,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None
) -> trace.Span:
    """
    Create a new span
    
    Args:
        name: Span name
        kind: Span kind
        attributes: Initial attributes
    
    Returns:
        New span
    """
    tracer = get_tracer()
    span = tracer.start_span(
        name,
        kind=kind,
        attributes=attributes or {}
    )
    current_span_var.set(span)
    return span

def add_span_attributes(attributes: Dict[str, Any]):
    """Add attributes to current span"""
    span = get_current_span()
    if span:
        for key, value in attributes.items():
            span.set_attribute(key, value)

def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add event to current span"""
    span = get_current_span()
    if span:
        span.add_event(name, attributes=attributes or {})

def set_span_status(code: StatusCode, description: Optional[str] = None):
    """Set status of current span"""
    span = get_current_span()
    if span:
        span.set_status(Status(code, description))

def record_exception(exception: Exception):
    """Record exception in current span"""
    span = get_current_span()
    if span:
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))

# Decorators for tracing
def trace_function(name: Optional[str] = None, kind: trace.SpanKind = trace.SpanKind.INTERNAL):
    """Decorator to trace a function"""
    def decorator(func):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        async def async_wrapper(*args, **kwargs):
            with get_tracer().start_as_current_span(span_name, kind=kind) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        def sync_wrapper(*args, **kwargs):
            with get_tracer().start_as_current_span(span_name, kind=kind) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Metrics helpers
def get_meter() -> metrics.Meter:
    """Get the configured meter"""
    if tracing_config.meter:
        return tracing_config.meter
    return metrics.get_meter(__name__)

def create_counter(name: str, unit: str = "", description: str = "") -> metrics.Counter:
    """Create a counter metric"""
    meter = get_meter()
    return meter.create_counter(name, unit=unit, description=description)

def create_histogram(name: str, unit: str = "", description: str = "") -> metrics.Histogram:
    """Create a histogram metric"""
    meter = get_meter()
    return meter.create_histogram(name, unit=unit, description=description)

def create_gauge(name: str, unit: str = "", description: str = ""):
    """Create a gauge metric"""
    meter = get_meter()
    return meter.create_observable_gauge(
        name,
        callbacks=[],
        unit=unit,
        description=description
    )