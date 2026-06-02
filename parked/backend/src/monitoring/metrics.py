"""Prometheus metrics for application observability."""

import time
from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Job Queue Metrics
job_queue_size = Gauge(
    'job_queue_size',
    'Number of jobs in queue',
    ['status']  # pending, running, completed, failed
)

job_processing_duration_seconds = Histogram(
    'job_processing_duration_seconds',
    'Job processing duration in seconds',
    ['job_type', 'status'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0)
)

jobs_processed_total = Counter(
    'jobs_processed_total',
    'Total jobs processed',
    ['job_type', 'status']
)

# TTS Metrics
tts_generation_duration_seconds = Histogram(
    'tts_generation_duration_seconds',
    'TTS audio generation duration in seconds',
    ['model', 'status'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0)
)

tts_generation_total = Counter(
    'tts_generation_total',
    'Total TTS generations',
    ['model', 'status']
)

tts_audio_duration_seconds = Histogram(
    'tts_audio_duration_seconds',
    'Generated audio duration in seconds',
    ['model']
)

# Storage Metrics
storage_operations_total = Counter(
    'storage_operations_total',
    'Total storage operations',
    ['operation', 'status']  # read, write, delete
)

storage_operation_duration_seconds = Histogram(
    'storage_operation_duration_seconds',
    'Storage operation duration in seconds',
    ['operation'],
    buckets=(0.01, 0.1, 0.5, 1.0, 2.0, 5.0)
)

storage_bytes_total = Counter(
    'storage_bytes_total',
    'Total bytes transferred',
    ['operation']  # read, write
)

# Database Metrics
database_connections_active = Gauge(
    'database_connections_active',
    'Active database connections'
)

database_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=(0.01, 0.1, 0.5, 1.0, 2.0, 5.0)
)

database_queries_total = Counter(
    'database_queries_total',
    'Total database queries',
    ['query_type', 'status']
)

# System Metrics
system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'CPU usage percentage'
)

system_memory_usage_bytes = Gauge(
    'system_memory_usage_bytes',
    'Memory usage in bytes'
)

system_disk_usage_bytes = Gauge(
    'system_disk_usage_bytes',
    'Disk usage in bytes',
    ['path']
)


class MetricsMiddleware:
    """FastAPI middleware for Prometheus metrics."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        method = scope["method"]
        path = scope["path"]
        
        # Normalize path (remove IDs for better cardinality)
        endpoint = self._normalize_path(path)
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.time() - start_time
            
            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing IDs with placeholders."""
        import re
        # Replace UUIDs
        path = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '{id}', path)
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        return path


def get_metrics():
    """Get Prometheus metrics in OpenMetrics format."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
