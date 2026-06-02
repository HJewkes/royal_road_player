"""OpenTelemetry tracing for distributed observability."""

import logging
from typing import Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry, but don't fail if not installed
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry not installed. Tracing will be disabled.")


def setup_tracing(
    service_name: str = "audiobook",
    endpoint: Optional[str] = None,
    enabled: bool = True,
) -> bool:
    """
    Set up OpenTelemetry tracing.
    
    Args:
        service_name: Service name for traces
        endpoint: OTLP endpoint (e.g., http://tempo:4317)
        enabled: Enable tracing
        
    Returns:
        True if tracing is enabled, False otherwise
    """
    if not enabled:
        logger.info("Tracing disabled")
        return False
    
    if not OPENTELEMETRY_AVAILABLE:
        logger.warning("OpenTelemetry not available. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation")
        return False
    
    try:
        # Create resource
        resource = Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
        })
        
        # Set up tracer provider
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        
        # Set up exporter
        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(f"✅ Tracing enabled: {service_name} -> {endpoint}")
        else:
            # Use console exporter for local development
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info(f"✅ Tracing enabled (console): {service_name}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to setup tracing: {e}")
        return False


def instrument_fastapi(app):
    """Instrument FastAPI application with OpenTelemetry."""
    if OPENTELEMETRY_AVAILABLE:
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("✅ FastAPI instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")


def instrument_sqlalchemy():
    """Instrument SQLAlchemy for database tracing."""
    if OPENTELEMETRY_AVAILABLE:
        try:
            SQLAlchemyInstrumentor().instrument()
            logger.info("✅ SQLAlchemy instrumented for tracing")
        except Exception as e:
            logger.error(f"Failed to instrument SQLAlchemy: {e}")


def trace_function(span_name: Optional[str] = None):
    """Decorator to trace function execution."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not OPENTELEMETRY_AVAILABLE:
                return func(*args, **kwargs)
            
            tracer = trace.get_tracer(__name__)
            name = span_name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise
        
        return wrapper
    return decorator
