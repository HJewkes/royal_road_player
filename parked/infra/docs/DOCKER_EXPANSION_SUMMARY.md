# Docker Expansion Summary

**Date:** 2025-01-27  
**Feature:** Expanded Docker deployment to include database, web service, and worker service

---

## What Was Added

### 1. Database Service (PostgreSQL)

- **Service:** `db` - PostgreSQL 15 Alpine
- **Port:** `5432`
- **Volume:** Persistent `postgres_data` volume
- **Health Checks:** Automatic readiness checks
- **Configuration:** Environment variables for credentials

**Benefits:**
- ✅ Production-ready database
- ✅ Better concurrency than SQLite
- ✅ Persistent data storage
- ✅ Supports multiple workers

### 2. Web Service (FastAPI)

- **Service:** `web` - FastAPI application
- **Port:** `8000` (configurable)
- **Health Check:** `/health` endpoint
- **Dependencies:** Waits for database to be healthy

**Changes:**
- Background processor disabled (handled by worker)
- Added `WORKER_MODE` environment variable
- Health check endpoint for Docker

### 3. Worker Service (Background Processor)

- **Service:** `worker` - Background job processor
- **Purpose:** Processes TTS generation jobs
- **Dependencies:** Database and web service
- **Resources:** Configurable CPU/memory limits
- **Logs:** Separate worker logs

**New File:** `backend/src/web/worker.py` - Worker entrypoint

**Benefits:**
- ✅ Separate scaling for workers
- ✅ Better resource management
- ✅ Independent restart/recovery
- ✅ Multiple worker instances possible

---

## Architecture

```
┌─────────────┐
│   Web UI    │ (Port 8000)
│  (FastAPI)  │
└──────┬──────┘
       │
       ├──────────────┐
       │              │
┌──────▼──────┐  ┌────▼──────┐
│  PostgreSQL │  │  Worker   │
│  Database   │  │  Service  │
│  (Port 5432)│  │           │
└─────────────┘  └───────────┘
```

---

## Files Created/Modified

### New Files
- `backend/src/web/worker.py` - Worker entrypoint
- `docker-compose.yml` - Full stack (CPU)
- `docker-compose.gpu.yml` - Full stack (GPU)
- `docker-compose.full.yml` - Alternative full stack config
- `docs/DOCKER_FULL_STACK.md` - Complete deployment guide
- `.env.example` - Environment variable template

### Modified Files
- `backend/src/data/database.py` - PostgreSQL support
- `backend/src/web/app.py` - Worker mode detection, health endpoint
- `backend/requirements.txt` - Added `psycopg2-binary`
- `Dockerfile` - Added curl for health checks

---

## Usage

### Start Full Stack (CPU)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# Then start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Start Full Stack (GPU)

```bash
docker-compose -f docker-compose.gpu.yml up -d
```

### Scale Workers

```bash
# Run 3 worker instances
docker-compose up -d --scale worker=3
```

---

## Configuration

### Environment Variables

**Database:**
- `POSTGRES_PASSWORD` - Database password (default: `audiobook_password`)

**Web Service:**
- `WEB_PORT` - Web service port (default: `8000`)
- `WORKER_MODE` - Set to `false` for web service

**Worker Service:**
- `WORKER_MODE` - Set to `true` for worker service
- `WORKER_CPUS` - CPU limit (default: `2`)
- `WORKER_MEMORY` - Memory limit (default: `4G`)

**Database Connection:**
- `DATABASE_URL` - PostgreSQL connection string (auto-generated from db service)

---

## Migration from Single Container

### Before (Single Container)
```bash
docker run -p 8000:8000 audiobook:latest
```

### After (Full Stack)
```bash
docker-compose up -d
```

**Benefits:**
- ✅ Separate database (persistent, scalable)
- ✅ Separate worker (scalable, independent)
- ✅ Better resource management
- ✅ Production-ready architecture

---

## Database Migration

### From SQLite to PostgreSQL

1. **Export SQLite data:**
   ```bash
   sqlite3 data/databases/audiobook.db .dump > backup.sql
   ```

2. **Start PostgreSQL:**
   ```bash
   docker-compose up -d db
   ```

3. **Import data** (manual conversion may be needed):
   ```bash
   docker-compose exec -T db psql -U audiobook audiobook < backup.sql
   ```

### Fallback to SQLite

If `DATABASE_URL` is not set, the system falls back to SQLite automatically.

---

## Service Communication

All services communicate via Docker network:

- **Web → Database:** `postgresql://audiobook:password@db:5432/audiobook`
- **Worker → Database:** Same connection string
- **Worker → Web:** Not required (both read from database)

---

## Health Checks

### Database
```bash
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

---

## Troubleshooting

### Database Connection Failed

```bash
# Check database logs
docker-compose logs db

# Verify database is healthy
docker-compose ps db

# Test connection
docker-compose exec web python -c "from src.data.database import get_engine; print(get_engine())"
```

### Worker Not Processing

```bash
# Check worker logs
docker-compose logs -f worker

# Restart worker
docker-compose restart worker

# Check worker is connected to database
docker-compose exec worker python -c "from src.data.database import init_db; init_db()"
```

### Port Conflicts

Change ports in `.env`:
```bash
WEB_PORT=8001
```

Or modify `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"
```

---

## Production Considerations

1. **Security:**
   - Change default `POSTGRES_PASSWORD`
   - Use Docker secrets for passwords
   - Limit network exposure

2. **Scaling:**
   - Scale workers: `docker-compose up -d --scale worker=3`
   - Add load balancer for multiple web instances
   - Use PostgreSQL connection pooling

3. **Monitoring:**
   - Add Prometheus/Grafana
   - Monitor worker queue depth
   - Track database performance

4. **Backups:**
   - Regular PostgreSQL backups
   - Volume snapshots
   - Export/import scripts

---

## Next Steps

1. **Test deployment** - Verify all services work together
2. **Add monitoring** - Prometheus/Grafana integration
3. **Add logging** - Centralized logging (ELK stack)
4. **Add backups** - Automated backup scripts
5. **Add CI/CD** - Automated deployment pipeline

---

## References

- **Full Stack Guide:** `docs/DOCKER_FULL_STACK.md`
- **Original Docker Guide:** `docs/DOCKER.md`
- **Architecture:** `docs/ARCHITECTURE.md`
