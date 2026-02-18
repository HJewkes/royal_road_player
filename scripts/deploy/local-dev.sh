#!/bin/bash
# Local Development Setup Script

set -e

echo "🚀 Setting up local development environment..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting." >&2; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed. Aborting." >&2; exit 1; }

# Create directories
echo "📁 Creating directories..."
mkdir -p data/{books,databases,models,exports,checkpoints}
mkdir -p logs

# Initialize LocalStack resources
echo "🔧 Initializing LocalStack resources..."
docker-compose -f docker-compose.local.yml up -d localstack

# Wait for LocalStack
echo "⏳ Waiting for LocalStack to be ready..."
until curl -s http://localhost:4566/_localstack/health | grep -q '"s3": "available"'; do
    echo "Waiting for LocalStack..."
    sleep 2
done

# Create S3 bucket
echo "🪣 Creating S3 bucket..."
docker run --rm --network audiobook-network \
    -e AWS_ACCESS_KEY_ID=test \
    -e AWS_SECRET_ACCESS_KEY=test \
    -e AWS_DEFAULT_REGION=us-east-1 \
    amazon/aws-cli:latest \
    --endpoint-url=http://localstack:4566 \
    s3 mb s3://audiobook-dev-data || echo "Bucket may already exist"

# Create SQS queue
echo "📬 Creating SQS queue..."
docker run --rm --network audiobook-network \
    -e AWS_ACCESS_KEY_ID=test \
    -e AWS_SECRET_ACCESS_KEY=test \
    -e AWS_DEFAULT_REGION=us-east-1 \
    amazon/aws-cli:latest \
    --endpoint-url=http://localstack:4566 \
    sqs create-queue --queue-name audiobook-dev-jobs || echo "Queue may already exist"

# Start all services
echo "🐳 Starting all services..."
docker-compose -f docker-compose.local.yml up -d

# Wait for services
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
curl -f http://localhost:8000/health || echo "⚠️  Web service not ready yet"

echo "✅ Local development environment is ready!"
echo ""
echo "📝 Services:"
echo "  - Web UI: http://localhost:8000"
echo "  - Database: localhost:5432"
echo "  - LocalStack: http://localhost:4566"
echo ""
echo "📊 View logs:"
echo "  docker-compose -f docker-compose.local.yml logs -f"
echo ""
echo "🛑 Stop services:"
echo "  docker-compose -f docker-compose.local.yml down"
