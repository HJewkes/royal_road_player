#!/bin/bash
# Initialize LocalStack S3 bucket

set -e

ENDPOINT_URL="${LOCALSTACK_ENDPOINT_URL:-http://localhost:4566}"
BUCKET_NAME="${S3_BUCKET_NAME:-audiobook-data}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

echo "Initializing LocalStack S3 bucket: $BUCKET_NAME"
echo "Endpoint: $ENDPOINT_URL"

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
until curl -s "$ENDPOINT_URL/_localstack/health" | grep -q '"s3": "available"'; do
    echo "Waiting for LocalStack..."
    sleep 2
done

echo "LocalStack is ready!"

# Create bucket using AWS CLI
aws --endpoint-url="$ENDPOINT_URL" \
    s3 mb "s3://$BUCKET_NAME" \
    --region "$AWS_DEFAULT_REGION" || echo "Bucket may already exist"

echo "✅ Bucket '$BUCKET_NAME' is ready!"

# List buckets to verify
echo "Available buckets:"
aws --endpoint-url="$ENDPOINT_URL" s3 ls
