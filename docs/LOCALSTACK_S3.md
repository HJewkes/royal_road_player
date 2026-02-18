# LocalStack S3 Storage Guide

This guide covers using LocalStack for S3-compatible storage in development, with easy migration to AWS S3 in production.

## Overview

LocalStack provides a local AWS cloud stack emulator, including S3. This allows us to:
- Develop and test with S3-compatible storage locally
- Use the same code for both development and production
- Easily migrate to real AWS S3 by changing configuration

## Architecture

```
┌─────────────┐
│   Web/Worker│
│   Services  │
└──────┬──────┘
       │
       │ S3 API
       │
┌──────▼──────┐
│  LocalStack │
│  (S3 Emulator)│
└─────────────┘
```

## Quick Start

### 1. Start Services

```bash
# Start all services including LocalStack
docker-compose up -d

# Verify LocalStack is running
curl http://localhost:4566/_localstack/health
```

### 2. Initialize S3 Bucket

The bucket is automatically created when the application starts, but you can also create it manually:

```bash
# Using AWS CLI (if installed)
aws --endpoint-url=http://localhost:4566 \
    s3 mb s3://audiobook-data \
    --region us-east-1

# Or using the init script
LOCALSTACK_ENDPOINT_URL=http://localhost:4566 \
    S3_BUCKET_NAME=audiobook-data \
    ./scripts/init_localstack.sh
```

### 3. Verify Storage

```bash
# List buckets
aws --endpoint-url=http://localhost:4566 s3 ls

# List objects in bucket
aws --endpoint-url=http://localhost:4566 s3 ls s3://audiobook-data/
```

## Configuration

### Environment Variables

**LocalStack (Development):**
```bash
S3_BUCKET_NAME=audiobook-data
S3_ENDPOINT_URL=http://localstack:4566
S3_USE_STORAGE=true
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
```

**AWS S3 (Production):**
```bash
S3_BUCKET_NAME=your-production-bucket
S3_ENDPOINT_URL=  # Leave empty for real AWS
S3_USE_STORAGE=true
AWS_ACCESS_KEY_ID=your_real_access_key
AWS_SECRET_ACCESS_KEY=your_real_secret_key
AWS_DEFAULT_REGION=us-east-1
```

**Local Filesystem (Fallback):**
```bash
S3_USE_STORAGE=false
```

## Storage Abstraction

The system uses a hybrid storage layer that automatically:
- Uses S3 when `S3_USE_STORAGE=true`
- Falls back to local filesystem when `S3_USE_STORAGE=false`
- Works seamlessly with both LocalStack and real AWS S3

### Code Usage

```python
from src.storage.file_storage import get_file_storage

storage = get_file_storage()

# Write file
storage.write_file(
    Path("books/book_123/chapter_01.txt"),
    b"Chapter content...",
    content_type="text/plain"
)

# Read file
data = storage.read_file(Path("books/book_123/chapter_01.txt"))

# Check if file exists
if storage.file_exists(Path("books/book_123/chapter_01.txt")):
    print("File exists!")

# Get file URL (presigned for S3, local path for filesystem)
url = storage.get_file_url(Path("books/book_123/chapter_01.txt"))
```

## Data Structure in S3

Files are stored with the same structure as local filesystem:

```
audiobook-data/
├── books/
│   ├── book_123/
│   │   ├── metadata.json
│   │   └── chapters/
│   │       ├── 01/
│   │       │   ├── text.txt
│   │       │   ├── chunks/
│   │       │   │   └── 1/
│   │       │   │       ├── text.txt
│   │       │   │       └── audio.wav
│   │       │   └── audio.m4b
│   │       └── 02/
│   └── book_456/
└── models/
    └── fine_tuned_models.yaml
```

## Migration to AWS S3

### Step 1: Create AWS S3 Bucket

```bash
# Create bucket in AWS
aws s3 mb s3://your-production-bucket --region us-east-1

# Enable versioning (optional)
aws s3api put-bucket-versioning \
    --bucket your-production-bucket \
    --versioning-configuration Status=Enabled
```

### Step 2: Update Configuration

Update `.env` or environment variables:

```bash
S3_BUCKET_NAME=your-production-bucket
S3_ENDPOINT_URL=  # Empty for real AWS
AWS_ACCESS_KEY_ID=your_real_access_key
AWS_SECRET_ACCESS_KEY=your_real_secret_key
```

### Step 3: Migrate Data

```bash
# Sync from LocalStack to AWS S3
aws --endpoint-url=http://localhost:4566 \
    s3 sync s3://audiobook-data \
    s3://your-production-bucket \
    --source-region us-east-1 \
    --region us-east-1
```

Or use the migration script:

```python
# scripts/migrate_to_s3.py
from src.storage.s3_storage import S3Storage

# Source: LocalStack
source = S3Storage(
    bucket_name="audiobook-data",
    endpoint_url="http://localhost:4566"
)

# Destination: AWS S3
dest = S3Storage(
    bucket_name="your-production-bucket",
    endpoint_url=None  # Real AWS
)

# Copy all objects
for key in source.list_objects():
    data = source.get_object(key)
    if data:
        dest.put_object(key, data)
        print(f"Migrated: {key}")
```

## LocalStack Features

### Persistence

LocalStack data persists in the `localstack_data` volume:

```bash
# View volume
docker volume inspect audiobook_localstack_data

# Backup data
docker run --rm -v audiobook_localstack_data:/data \
    -v $(pwd):/backup alpine tar czf /backup/localstack-backup.tar.gz /data
```

### Debugging

```bash
# View LocalStack logs
docker-compose logs -f localstack

# Access LocalStack dashboard (if enabled)
# http://localhost:4566/_localstack/health

# List all buckets
aws --endpoint-url=http://localhost:4566 s3 ls

# List objects with details
aws --endpoint-url=http://localhost:4566 s3 ls s3://audiobook-data --recursive
```

## Troubleshooting

### Bucket Not Found

```bash
# Check if bucket exists
aws --endpoint-url=http://localhost:4566 s3 ls

# Create bucket manually
aws --endpoint-url=http://localhost:4566 \
    s3 mb s3://audiobook-data
```

### Connection Errors

```bash
# Verify LocalStack is running
curl http://localhost:4566/_localstack/health

# Check service logs
docker-compose logs localstack

# Verify endpoint URL in environment
docker-compose exec web env | grep S3
```

### Permission Errors

LocalStack uses test credentials by default:
- `AWS_ACCESS_KEY_ID=test`
- `AWS_SECRET_ACCESS_KEY=test`

These work automatically with LocalStack.

### Performance

LocalStack is slower than real S3 for large files. For production workloads, use real AWS S3.

## Production Considerations

### Security

1. **Use IAM Roles** (recommended):
   ```python
   # No credentials needed when running on EC2 with IAM role
   s3_client = boto3.client('s3')
   ```

2. **Use Environment Variables**:
   ```bash
   # Never commit credentials
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   ```

3. **Use Secrets Management**:
   - AWS Secrets Manager
   - HashiCorp Vault
   - Docker secrets

### Cost Optimization

1. **Lifecycle Policies**:
   ```bash
   # Move old files to Glacier
   aws s3api put-bucket-lifecycle-configuration \
       --bucket your-bucket \
       --lifecycle-configuration file://lifecycle.json
   ```

2. **Storage Classes**:
   - Standard for frequently accessed files
   - Infrequent Access for older files
   - Glacier for archives

### Monitoring

```bash
# Enable S3 access logging
aws s3api put-bucket-logging \
    --bucket your-bucket \
    --bucket-logging-status file://logging.json

# Set up CloudWatch alarms
aws cloudwatch put-metric-alarm \
    --alarm-name s3-bucket-size \
    --metric-name BucketSizeBytes \
    --namespace AWS/S3
```

## References

- **LocalStack Docs:** https://docs.localstack.cloud/
- **AWS S3 Docs:** https://docs.aws.amazon.com/s3/
- **boto3 Docs:** https://boto3.amazonaws.com/v1/documentation/api/latest/index.html
- **Storage Code:** `backend/src/storage/`
