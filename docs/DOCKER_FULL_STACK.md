# Docker Full Stack Deployment Guide

Complete Docker deployment with database, web service, and worker service.

## Architecture

```
┌─────────────┐
│   Web UI    │ (Port 8000)
│  (FastAPI)  │
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
┌──────▼──────┐  ┌────▼──────┐  ┌───▼────────┐
│  PostgreSQL │  │  Worker   │  │ LocalStack │
│  Database   │  │  Service  │  │  (S3)      │
│  (Port 5432)│  │           │  │ (Port 4566)│
└─────────────┘  └───────────┘  └────────────┘
```

## Services

1. **localstack** - S3-compatible storage emulator (for development)
2. **db** - PostgreSQL 15 database
3. **web** - FastAPI web service (handles API requests)
4. **worker** - Background job processor (handles TTS generation)

## Quick Start

### CPU-only (Default)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### GPU-enabled

```bash
# Start all services with GPU support
docker-compose -f docker-compose.gpu.yml up -d

# View logs
docker-compose -f docker-compose.gpu.yml logs -f

# Stop services
docker-compose -f docker-compose.gpu.yml down
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Database
POSTGRES_PASSWORD=your_secure_password_here

# Web Service
WEB_PORT=8000

# TTS Configuration
TTS_GPU=false  # Set to true for GPU
TORCH_VERSION=cpu  # cpu, cuda118, cuda121, rocm
TTS_FINE_TUNED_MODEL=david_attenborough  # Optional

# Audio Output
AUDIO_OUTPUT_FORMAT=m4b
AUDIO_BITRATE=128k

# Worker Resources (optional)
WORKER_CPUS=2
WORKER_MEMORY=4G

# S3 Storage (LocalStack for dev, AWS S3 for prod)
S3_BUCKET_NAME=audiobook-data
S3_ENDPOINT_URL=http://localstack:4566  # Leave empty for real AWS S3
S3_USE_STORAGE=true  # Set to false to use local filesystem
AWS_ACCESS_KEY_ID=test  # Use real AWS credentials for production
AWS_SECRET_ACCESS_KEY=test  # Use real AWS credentials for production
AWS_DEFAULT_REGION=us-east-1
```

## Service Details

### LocalStack Service

- **Image:** `localstack/localstack:latest`
- **Port:** `4566` (S3 endpoint)
- **Purpose:** S3-compatible storage emulator for development
- **Volume:** `localstack_data` (persistent storage)
- **Health Check:** Automatic LocalStack health check

**Access LocalStack:**
```bash
# Health check
curl http://localhost:4566/_localstack/health

# List buckets (requires AWS CLI)
aws --endpoint-url=http://localhost:4566 s3 ls
```

**Note:** For production, configure real AWS S3 by setting `S3_ENDPOINT_URL` to empty and providing real AWS credentials. See [LocalStack S3 Guide](LOCALSTACK_S3.md) for details.

### Database Service

- **Image:** `postgres:15-alpine`
- **Port:** `5432`
- **Volume:** `postgres_data` (persistent storage)
- **Health Check:** Automatic PostgreSQL readiness check

**Access Database:**
```bash
# From host
psql -h localhost -p 5432 -U audiobook -d audiobook

# From container
docker-compose exec db psql -U audiobook -d audiobook
```

### Web Service

- **Port:** `8000` (configurable via `WEB_PORT`)
- **Health Check:** `/health` endpoint
- **Dependencies:** Database must be healthy before starting

**Access Web UI:**
- http://localhost:8000

**API Endpoints:**
- http://localhost:8000/api/books
- http://localhost:8000/api/chapters
- http://localhost:8000/health

### Worker Service

- **Purpose:** Processes background TTS jobs
- **Dependencies:** Database and web service must be healthy
- **Resources:** Configurable CPU/memory limits
- **Logs:** `logs/worker.log`

**View Worker Logs:**
```bash
docker-compose logs -f worker
```

## Scaling

### Multiple Workers

To run multiple worker instances:

```bash
# Scale workers
docker-compose up -d --scale worker=3

# Or in docker-compose.yml, add:
# worker:
#   deploy:
#     replicas: 3
```

### Resource Limits

Set resource limits in `docker-compose.yml`:

```yaml
worker:
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 8G
      reservations:
        cpus: '2'
        memory: 4G
```

## Data Persistence

### Volumes

- **postgres_data** - Database data (persistent)
- **localstack_data** - LocalStack S3 data (persistent)
- **./data** - Books, models, databases (mounted from host, optional if using S3)
- **./logs** - Application logs (mounted from host)

### Backup Database

```bash
# Backup
docker-compose exec db pg_dump -U audiobook audiobook > backup.sql

# Restore
docker-compose exec -T db psql -U audiobook audiobook < backup.sql
```

## Networking

All services are on the `audiobook-network` bridge network:

- **localstack:** `localstack:4566` (internal S3 endpoint)
- **db:** `db:5432` (internal)
- **web:** `web:8000` (internal)
- **worker:** Connects to `localstack`, `db`, and `web`

## Health Checks

### Database
```bash
docker-compose ps  # Check status
docker-compose exec db pg_isready -U audiobook
```

### Web Service
```bash
curl http://localhost:8000/health
```

### Worker
```bash
docker-compose logs worker | tail -20
```

### LocalStack
```bash
curl http://localhost:4566/_localstack/health
docker-compose logs localstack | tail -20
```

## Troubleshooting

### LocalStack S3 Issues

```bash
# Check LocalStack is running
docker-compose ps localstack

# Check LocalStack logs
docker-compose logs localstack

# Verify S3 endpoint is accessible
curl http://localhost:4566/_localstack/health

# Test S3 bucket creation (requires AWS CLI)
aws --endpoint-url=http://localhost:4566 s3 ls

# If bucket doesn't exist, create it manually
aws --endpoint-url=http://localhost:4566 \
    s3 mb s3://audiobook-data \
    --region us-east-1
```

**Common Issues:**
- **Bucket not found**: The bucket is auto-created on first use, but you can create it manually if needed
- **Connection refused**: Ensure LocalStack service is healthy before starting web/worker services
- **Permission denied**: LocalStack uses test credentials (`test`/`test`) by default

See [LocalStack S3 Guide](LOCALSTACK_S3.md) for detailed troubleshooting.

### Database Connection Issues

```bash
# Check database logs
docker-compose logs db

# Check database is running
docker-compose ps db

# Test connection
docker-compose exec web python -c "from src.data.database import get_engine; print(get_engine())"
```

### Worker Not Processing Jobs

```bash
# Check worker logs
docker-compose logs -f worker

# Check worker is running
docker-compose ps worker

# Restart worker
docker-compose restart worker
```

### GPU Not Detected

```bash
# Verify NVIDIA Docker runtime
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Check GPU in container
docker-compose exec worker python -c "import torch; print(torch.cuda.is_available())"
```

### Port Conflicts

If port 8000 or 5432 is already in use:

```bash
# Change ports in .env
WEB_PORT=8001
# Or in docker-compose.yml
ports:
  - "8001:8000"  # Host:Container
```

## Production Deployment

### Security

1. **Change default passwords:**
   ```bash
   POSTGRES_PASSWORD=strong_random_password
   ```

2. **Use secrets management:**
   ```yaml
   secrets:
     postgres_password:
       file: ./secrets/postgres_password.txt
   ```

3. **Limit network exposure:**
   ```yaml
   db:
     ports: []  # Remove port mapping, only internal access
   ```

### Monitoring

Add monitoring services:

```yaml
  prometheus:
    image: prom/prometheus
    # ... config

  grafana:
    image: grafana/grafana
    # ... config
```

### Reverse Proxy

Add nginx in front:

```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - web
```

## Migration from SQLite

If you have existing SQLite data:

1. **Export SQLite data:**
   ```bash
   sqlite3 data/databases/audiobook.db .dump > backup.sql
   ```

2. **Start PostgreSQL:**
   ```bash
   docker-compose up -d db
   ```

3. **Import data:**
   ```bash
   # Convert SQLite dump to PostgreSQL format (manual conversion may be needed)
   docker-compose exec -T db psql -U audiobook audiobook < backup.sql
   ```

## Cleanup

### Stop and Remove Containers

```bash
docker-compose down
```

### Remove Volumes (⚠️ Deletes Data)

```bash
docker-compose down -v
```

### Remove Images

```bash
docker-compose down --rmi all
```

## Environment-Specific Configs

### Development

```bash
# Use SQLite (no database service needed)
docker-compose -f docker-compose.yml up web worker
# Remove db service, set DATABASE_URL to empty
```

### Production

```bash
# Use full stack with PostgreSQL
docker-compose -f docker-compose.gpu.yml up -d

# Add monitoring, logging, backups
```

## References

- **Main Docker Guide:** `docs/DOCKER.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **API Documentation:** Available at http://localhost:8000/docs
