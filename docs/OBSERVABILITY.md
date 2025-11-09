# Observability Guide

Complete observability stack for local development and production.

## 🎯 Overview

The observability stack provides:
- **Metrics**: Prometheus for metrics collection
- **Logs**: Loki for log aggregation
- **Traces**: Tempo for distributed tracing
- **Visualization**: Grafana for dashboards

All components work **locally** for validation and **production** for monitoring.

## 🏗️ Architecture

```
┌─────────────┐
│ Application │
│  (FastAPI)  │
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
┌──────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
│ Prometheus  │  │   Loki   │  │  Tempo   │
│ (Metrics)   │  │  (Logs)  │  │ (Traces) │
└──────┬──────┘  └────┬─────┘  └────┬─────┘
       │              │              │
       └──────────────┼──────────────┘
                      │
              ┌───────▼───────┐
              │    Grafana    │
              │ (Visualization)│
              └───────────────┘
```

## 🚀 Quick Start

### Local Development

```bash
# Start application + observability stack
docker-compose -f docker-compose.local.yml -f docker-compose.observability.yml up -d

# Access dashboards
# Grafana: http://localhost:3001 (admin/admin)
# Prometheus: http://localhost:9090
# Loki: http://localhost:3100
# Tempo: http://localhost:3200
```

### Production

Observability is automatically configured when deployed to Kubernetes.

## 📊 Components

### Prometheus (Metrics)

**Purpose**: Collect and store metrics

**Port**: `9090`

**Configuration**: `monitoring/prometheus/prometheus.yml`

**Metrics Endpoint**: Application exposes `/metrics` endpoint

**Access**: http://localhost:9090

### Grafana (Visualization)

**Purpose**: Visualize metrics, logs, and traces

**Port**: `3001` (local), `3000` (container)

**Credentials**: `admin/admin` (change in production!)

**Data Sources**:
- Prometheus: `http://prometheus:9090`
- Loki: `http://loki:3100`
- Tempo: `http://tempo:3200`

**Access**: http://localhost:3001

### Loki (Logs)

**Purpose**: Aggregate and query logs

**Port**: `3100`

**Configuration**: `monitoring/loki/loki-config.yml`

**Log Sources**:
- Application logs: `/var/log/audiobook/*.log`
- Docker container logs

**Access**: http://localhost:3100

### Promtail (Log Shipper)

**Purpose**: Ship logs to Loki

**Configuration**: `monitoring/promtail/promtail-config.yml`

**Sources**:
- Application log files
- Docker container logs

### Tempo (Traces)

**Purpose**: Store and query distributed traces

**Ports**:
- `3200`: HTTP API
- `4317`: OTLP gRPC
- `4318`: OTLP HTTP

**Configuration**: `monitoring/tempo/tempo-config.yml`

**Access**: http://localhost:3200

## 🔧 Application Integration

### Metrics

The application automatically exposes Prometheus metrics:

```python
# Metrics are automatically collected via middleware
# Access at: http://localhost:8000/metrics
```

**Available Metrics**:
- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request duration
- `job_queue_size`: Queue size by status
- `job_processing_duration_seconds`: Job processing time
- `tts_generation_duration_seconds`: TTS generation time
- `storage_operations_total`: Storage operations
- `database_queries_total`: Database queries

### Logging

Application logs are automatically shipped to Loki via Promtail:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Application started")
logger.error("Error occurred", exc_info=True)
```

**Log Levels**:
- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages
- `WARNING`: Warning messages
- `ERROR`: Error messages
- `CRITICAL`: Critical errors

### Tracing

Distributed tracing is enabled via OpenTelemetry:

```python
from src.monitoring.tracing import trace_function

@trace_function(span_name="process_chunk")
def process_chunk(chunk):
    # Function execution is automatically traced
    pass
```

**Enable Tracing**:
```bash
export TRACING_ENABLED=true
export TRACING_ENDPOINT=http://tempo:4317
```

## 📈 Grafana Dashboards

### Pre-configured Dashboards

1. **Application Metrics**: HTTP requests, response times, error rates
2. **Job Queue**: Queue depth, processing times, job status
3. **TTS Performance**: Generation times, audio durations
4. **Storage**: Operation counts, durations, bytes transferred
5. **Database**: Query counts, durations, connection pool
6. **System**: CPU, memory, disk usage

### Creating Custom Dashboards

1. Access Grafana: http://localhost:3001
2. Go to **Dashboards** → **New Dashboard**
3. Add panels with Prometheus queries
4. Save dashboard

**Example Queries**:
```promql
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# P95 latency
histogram_quantile(0.95, http_request_duration_seconds_bucket)
```

## 🔍 Querying Logs

### Via Grafana

1. Open Grafana: http://localhost:3001
2. Go to **Explore** → Select **Loki**
3. Enter LogQL query:

```logql
# All logs
{job="audiobook"}

# Error logs only
{job="audiobook"} |= "ERROR"

# Logs from specific service
{service="audiobook-web"}

# Logs with specific text
{job="audiobook"} |~ "database"
```

### Via Loki API

```bash
# Query logs
curl "http://localhost:3100/loki/api/v1/query_range?query={job=\"audiobook\"}&start=1h&limit=100"
```

## 🔗 Tracing

### View Traces in Grafana

1. Open Grafana: http://localhost:3001
2. Go to **Explore** → Select **Tempo**
3. Search for traces by:
   - Service name
   - Operation name
   - Tags
   - Duration

### Trace Context Propagation

Traces automatically propagate across services:

```python
# In web service
from opentelemetry import trace

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("process_request") as span:
    # Call worker service
    # Trace context is automatically propagated
    pass
```

## 🚨 Alerts

### Prometheus Alerts

Configure alerts in `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: application
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
```

### Grafana Alerts

1. Create alert in Grafana dashboard
2. Configure notification channels
3. Set thresholds and conditions

## 📊 Production Considerations

### Scaling

- **Prometheus**: Use Prometheus Operator in Kubernetes
- **Grafana**: Deploy as StatefulSet with persistent storage
- **Loki**: Use Loki Operator for scaling
- **Tempo**: Scale horizontally with object storage backend

### Retention

- **Metrics**: 30 days (Prometheus)
- **Logs**: 90 days (Loki)
- **Traces**: 7 days (Tempo)

### Cost Optimization

- Use S3 for long-term metric storage (Thanos)
- Compress logs in Loki
- Sample traces (keep 10% in production)

## 🔧 Configuration

### Environment Variables

```bash
# Enable tracing
TRACING_ENABLED=true
TRACING_ENDPOINT=http://tempo:4317

# Metrics endpoint (always enabled)
METRICS_ENABLED=true
```

### Application Configuration

Metrics and tracing are automatically configured when:
- `TRACING_ENABLED=true` is set
- Observability stack is running

## 📚 Resources

- **Prometheus**: https://prometheus.io/docs/
- **Grafana**: https://grafana.com/docs/
- **Loki**: https://grafana.com/docs/loki/
- **Tempo**: https://grafana.com/docs/tempo/
- **OpenTelemetry**: https://opentelemetry.io/docs/

## 🐛 Troubleshooting

### Metrics Not Appearing

1. Check `/metrics` endpoint: `curl http://localhost:8000/metrics`
2. Verify Prometheus is scraping: Check targets in Prometheus UI
3. Check Prometheus config: `monitoring/prometheus/prometheus.yml`

### Logs Not Appearing

1. Check Promtail logs: `docker-compose logs promtail`
2. Verify log files exist: `ls -la logs/`
3. Check Loki config: `monitoring/loki/loki-config.yml`

### Traces Not Appearing

1. Verify tracing is enabled: `echo $TRACING_ENABLED`
2. Check Tempo is running: `curl http://localhost:3200/ready`
3. Check application logs for tracing errors

### Grafana Not Loading

1. Check Grafana logs: `docker-compose logs grafana`
2. Verify data sources are configured
3. Check network connectivity between services
