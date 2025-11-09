# Production Deployment Guide

Complete guide for deploying the Audiobook Generator to production using Docker Compose or Kubernetes.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Docker Compose Deployment](#docker-compose-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [AWS Services Integration](#aws-services-integration)
6. [Security Hardening](#security-hardening)
7. [Monitoring & Logging](#monitoring--logging)
8. [Scaling & Performance](#scaling--performance)
9. [Backup & Recovery](#backup--recovery)
10. [Troubleshooting](#troubleshooting)

## Architecture Overview

### Services

- **LocalStack** (Dev) / **AWS S3/SQS/SNS/CloudWatch** (Prod): Object storage, job queue, notifications, logging
- **PostgreSQL**: Database for metadata and job state
- **Web Service**: FastAPI application serving HTTP requests
- **Worker Service**: Background job processor for TTS generation

### Production-Ready Features

✅ **S3 Storage**: Scalable object storage (LocalStack for dev, AWS S3 for prod)  
✅ **SQS Queue**: Distributed job queue (optional, can use database queue)  
✅ **CloudWatch Logs**: Centralized logging  
✅ **SNS Notifications**: Job completion notifications  
✅ **Secrets Manager**: Secure credential management  
✅ **Auto-scaling**: Horizontal Pod Autoscaler (K8s)  
✅ **Health Checks**: Liveness and readiness probes  
✅ **TLS/SSL**: Ingress with Let's Encrypt certificates  
✅ **Resource Limits**: CPU and memory constraints  

## Prerequisites

### Docker Compose

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB+ RAM
- 20GB+ disk space

### Kubernetes

- Kubernetes cluster 1.24+
- kubectl configured
- Helm 3.0+ (for Helm chart)
- Ingress controller (nginx recommended)
- cert-manager (for TLS)
- Storage class configured

### AWS (Production)

- AWS account
- IAM user with permissions for S3, SQS, SNS, CloudWatch Logs, Secrets Manager
- S3 bucket created
- SQS queue created (optional)
- SNS topic created (optional)

## Docker Compose Deployment

### Quick Start

```bash
# Clone repository
git clone <repository-url>
cd audiobook-generator

# Copy environment file
cp .env.example .env

# Edit .env with production values
nano .env

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Production Configuration

Update `.env`:

```bash
# Database
POSTGRES_PASSWORD=strong_random_password_here

# AWS S3 (Production)
S3_BUCKET_NAME=your-production-bucket
S3_ENDPOINT_URL=  # Empty for real AWS
S3_USE_STORAGE=true
AWS_ACCESS_KEY_ID=your_real_access_key
AWS_SECRET_ACCESS_KEY=your_real_secret_key
AWS_DEFAULT_REGION=us-east-1

# SQS Queue (Optional)
SQS_USE_QUEUE=true
SQS_QUEUE_NAME=audiobook-jobs
SQS_ENDPOINT_URL=  # Empty for real AWS

# CloudWatch Logs (Optional)
CLOUDWATCH_LOG_GROUP=audiobook-logs
CLOUDWATCH_ENDPOINT_URL=  # Empty for real AWS

# SNS Notifications (Optional)
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:audiobook-notifications
SNS_ENDPOINT_URL=  # Empty for real AWS

# Secrets Manager (Optional)
USE_SECRETS_MANAGER=true
SECRETS_MANAGER_ENDPOINT_URL=  # Empty for real AWS
```

### Scaling Workers

```bash
# Scale workers
docker-compose up -d --scale worker=5

# Or edit docker-compose.yml
worker:
  deploy:
    replicas: 5
```

## Kubernetes Deployment

### Using Helm (Recommended)

```bash
# Add Helm repository (if using)
helm repo add audiobook ./helm/audiobook

# Install with default values
helm install audiobook ./helm/audiobook \
  --namespace audiobook \
  --create-namespace

# Install with custom values
helm install audiobook ./helm/audiobook \
  --namespace audiobook \
  --create-namespace \
  --set database.password=strong_password \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=audiobook.example.com

# Upgrade
helm upgrade audiobook ./helm/audiobook \
  --namespace audiobook \
  --set replicaCount.worker=5

# Uninstall
helm uninstall audiobook --namespace audiobook
```

### Using Raw Manifests

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets (edit first!)
kubectl apply -f k8s/secret.yaml

# Create configmap
kubectl apply -f k8s/configmap.yaml

# Deploy database
kubectl apply -f k8s/postgres-pvc.yaml
kubectl apply -f k8s/postgres-deployment.yaml

# Deploy LocalStack (dev) or configure AWS (prod)
kubectl apply -f k8s/localstack-pvc.yaml
kubectl apply -f k8s/localstack-deployment.yaml

# Deploy web service
kubectl apply -f k8s/web-deployment.yaml

# Deploy worker service
kubectl apply -f k8s/worker-deployment.yaml

# Deploy ingress
kubectl apply -f k8s/ingress.yaml

# Deploy autoscaling
kubectl apply -f k8s/hpa.yaml
```

### Production Values

Create `production-values.yaml`:

```yaml
# Production values
replicaCount:
  web: 3
  worker: 5

database:
  password: "CHANGE_ME_STRONG_PASSWORD"
  storage: 50Gi

localstack:
  enabled: false  # Use real AWS services

config:
  s3EndpointUrl: ""  # Empty for real AWS
  sqsEndpointUrl: ""  # Empty for real AWS
  cloudwatchEndpointUrl: ""  # Empty for real AWS
  snsEndpointUrl: ""  # Empty for real AWS
  cloudwatchLogGroup: "audiobook-logs"
  snsTopicArn: "arn:aws:sns:us-east-1:123456789012:audiobook-notifications"

secrets:
  postgresPassword: "CHANGE_ME_STRONG_PASSWORD"
  awsAccessKeyId: "YOUR_AWS_ACCESS_KEY"
  awsSecretAccessKey: "YOUR_AWS_SECRET_KEY"
  s3EndpointUrl: ""
  sqsEndpointUrl: ""
  cloudwatchEndpointUrl: ""
  snsEndpointUrl: ""

ingress:
  enabled: true
  hosts:
    - host: audiobook.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: audiobook-tls
      hosts:
        - audiobook.example.com

autoscaling:
  web:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
  worker:
    enabled: true
    minReplicas: 5
    maxReplicas: 20
```

Install:

```bash
helm install audiobook ./helm/audiobook \
  --namespace audiobook \
  --create-namespace \
  -f production-values.yaml
```

## AWS Services Integration

### S3 Setup

```bash
# Create bucket
aws s3 mb s3://audiobook-production --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket audiobook-production \
  --versioning-configuration Status=Enabled

# Set lifecycle policy (optional)
aws s3api put-bucket-lifecycle-configuration \
  --bucket audiobook-production \
  --lifecycle-configuration file://lifecycle.json
```

### SQS Setup

```bash
# Create queue
aws sqs create-queue \
  --queue-name audiobook-jobs \
  --attributes \
    VisibilityTimeout=300,MessageRetentionPeriod=1209600

# Get queue URL
aws sqs get-queue-url --queue-name audiobook-jobs
```

### CloudWatch Logs Setup

```bash
# Create log group
aws logs create-log-group --log-group-name audiobook-logs

# Set retention (optional)
aws logs put-retention-policy \
  --log-group-name audiobook-logs \
  --retention-in-days 30
```

### SNS Setup

```bash
# Create topic
aws sns create-topic --name audiobook-notifications

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:audiobook-notifications \
  --protocol email \
  --notification-endpoint admin@example.com
```

### Secrets Manager Setup

```bash
# Create secret for database password
aws secretsmanager create-secret \
  --name audiobook/database/password \
  --secret-string "strong_password_here"

# Create secret for AWS credentials (use IAM roles instead!)
aws secretsmanager create-secret \
  --name audiobook/aws/credentials \
  --secret-string '{"access_key_id":"...","secret_access_key":"..."}'
```

## Security Hardening

### 1. Use IAM Roles (Kubernetes)

Instead of access keys, use IAM roles:

```yaml
# Add service account with IAM role
apiVersion: v1
kind: ServiceAccount
metadata:
  name: audiobook-service-account
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/audiobook-role
```

### 2. Encrypt Secrets

```bash
# Use Kubernetes secrets
kubectl create secret generic audiobook-secrets \
  --from-literal=postgres-password='strong_password' \
  --from-literal=aws-access-key-id='key' \
  --from-literal=aws-secret-access-key='secret'

# Or use Sealed Secrets
kubectl apply -f sealed-secret.yaml
```

### 3. Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: audiobook-network-policy
spec:
  podSelector:
    matchLabels:
      app: audiobook
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: audiobook
    ports:
    - protocol: TCP
      port: 5432  # Database
  - to:
    - namespaceSelector:
        matchLabels:
          name: audiobook
    ports:
    - protocol: TCP
      port: 4566  # LocalStack
```

### 4. TLS/SSL

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

## Monitoring & Logging

### Prometheus Metrics

Add Prometheus annotations:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8000"
    prometheus.io/path: "/metrics"
```

### Grafana Dashboard

Import dashboard from `docs/grafana-dashboard.json`.

### CloudWatch Logs

Logs are automatically sent to CloudWatch when configured:

```bash
# View logs
aws logs tail audiobook-logs --follow

# Filter logs
aws logs filter-log-events \
  --log-group-name audiobook-logs \
  --filter-pattern "ERROR"
```

## Scaling & Performance

### Horizontal Pod Autoscaling

Already configured in `k8s/hpa.yaml`. Adjust thresholds:

```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70  # Scale at 70% CPU
```

### Vertical Scaling

Adjust resource limits in `values.yaml`:

```yaml
resources:
  worker:
    requests:
      memory: "4Gi"
      cpu: "2000m"
    limits:
      memory: "16Gi"
      cpu: "8000m"
```

### Database Connection Pooling

Configured in `database.py`. Adjust pool size:

```python
engine = create_engine(
    database_url,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)
```

## Backup & Recovery

### Database Backup

```bash
# Manual backup
kubectl exec -it audiobook-db-0 -- pg_dump -U audiobook audiobook > backup.sql

# Automated backup (CronJob)
kubectl apply -f k8s/backup-cronjob.yaml
```

### S3 Backup

```bash
# Sync to backup bucket
aws s3 sync s3://audiobook-production s3://audiobook-backup

# Enable versioning for automatic backups
aws s3api put-bucket-versioning \
  --bucket audiobook-production \
  --versioning-configuration Status=Enabled
```

### Disaster Recovery

1. **Database**: Restore from backup
2. **S3**: Data is already replicated (if configured)
3. **Kubernetes**: Recreate from Helm chart with backup data

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -n audiobook
kubectl describe pod <pod-name> -n audiobook
kubectl logs <pod-name> -n audiobook
```

### Check Services

```bash
kubectl get svc -n audiobook
kubectl get ingress -n audiobook
```

### Database Connection Issues

```bash
# Test database connection
kubectl exec -it audiobook-web-0 -- python -c "from src.data.database import get_engine; print(get_engine())"

# Check database logs
kubectl logs audiobook-db-0 -n audiobook
```

### S3 Connection Issues

```bash
# Test S3 connection
kubectl exec -it audiobook-web-0 -- aws --endpoint-url=http://localstack:4566 s3 ls

# Check LocalStack logs
kubectl logs localstack-0 -n audiobook
```

### Performance Issues

```bash
# Check resource usage
kubectl top pods -n audiobook

# Check HPA status
kubectl get hpa -n audiobook

# View metrics
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/audiobook/pods
```

## Next Steps

- Set up CI/CD pipeline
- Configure monitoring alerts
- Implement blue-green deployments
- Add database read replicas
- Set up multi-region deployment
