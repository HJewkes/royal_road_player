# SRE Guide - Production Launch Readiness

Complete Site Reliability Engineering guide for production deployment.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Local Development](#local-development)
3. [Build & Deploy Pipeline](#build--deploy-pipeline)
4. [Infrastructure as Code](#infrastructure-as-code)
5. [Monitoring & Observability](#monitoring--observability)
6. [Incident Response](#incident-response)
7. [Runbooks](#runbooks)
8. [Launch Checklist](#launch-checklist)

## Architecture Overview

### Production Stack

```
┌─────────────────────────────────────────────────────────┐
│                     Internet                              │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   AWS Route53/ALB     │
         └───────────┬───────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼────┐    ┌──────▼──────┐  ┌─────▼─────┐
│  Web   │    │   Worker    │  │  Worker   │
│ (EKS)  │    │   (EKS)     │  │  (EKS)    │
└───┬────┘    └──────┬──────┘  └─────┬─────┘
    │                │                │
    └────────────────┼────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼────┐    ┌──────▼──────┐  ┌─────▼─────┐
│  RDS   │    │     S3       │  │    SQS    │
│  (PG)  │    │   (Storage)  │  │  (Queue)  │
└────────┘    └──────────────┘  └───────────┘
                     │
              ┌──────▼──────┐
              │ CloudWatch  │
              │   Logs      │
              └─────────────┘
```

### Components

- **Kubernetes (EKS)**: Container orchestration
- **RDS PostgreSQL**: Managed database
- **S3**: Object storage
- **SQS**: Job queue
- **SNS**: Notifications
- **CloudWatch**: Logging and monitoring
- **Terraform**: Infrastructure as Code
- **GitHub Actions**: CI/CD pipeline

## Local Development

### Quick Start

```bash
# One-command setup
./scripts/deploy/local-dev.sh

# Or manually
docker-compose -f docker-compose.local.yml up -d
```

### Local Stack

- **LocalStack**: S3, SQS, CloudWatch, SNS, Secrets Manager
- **PostgreSQL**: Local database
- **Web Service**: FastAPI with hot reload
- **Worker Service**: Background job processor

### Development Workflow

1. **Start services**: `docker-compose -f docker-compose.local.yml up`
2. **Make changes**: Code auto-reloads (web service)
3. **Run tests**: `make test`
4. **Check logs**: `docker-compose -f docker-compose.local.yml logs -f`
5. **Stop services**: `docker-compose -f docker-compose.local.yml down`

### Local Testing

```bash
# Backend tests
cd backend
pytest --cov=src

# Frontend tests
cd frontend
npm test

# Integration tests
docker-compose -f docker-compose.local.yml up -d
pytest tests/integration/
```

## Build & Deploy Pipeline

### CI Pipeline (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` or `develop`
- Pull requests

**Steps:**
1. **Lint**: Code quality checks
2. **Test**: Unit and integration tests
3. **Frontend Test**: React component tests
4. **Build**: Docker image build and push

### CD Pipeline (`.github/workflows/deploy.yml`)

**Triggers:**
- Push to `main` (staging)
- Tags `v*` (production)
- Manual workflow dispatch

**Steps:**
1. **Terraform Plan**: Infrastructure changes
2. **Terraform Apply**: Deploy infrastructure
3. **Kubernetes Deploy**: Helm chart deployment
4. **Health Check**: Verify deployment

### Deployment Environments

#### Development
- **Trigger**: Push to `develop`
- **Infrastructure**: LocalStack + Docker Compose
- **Database**: Local PostgreSQL
- **Storage**: LocalStack S3

#### Staging
- **Trigger**: Push to `main`
- **Infrastructure**: AWS (via Terraform)
- **Database**: RDS PostgreSQL (single AZ)
- **Storage**: S3 bucket
- **Kubernetes**: EKS cluster

#### Production
- **Trigger**: Git tags `v*`
- **Infrastructure**: AWS (via Terraform)
- **Database**: RDS PostgreSQL (multi-AZ)
- **Storage**: S3 bucket (versioned)
- **Kubernetes**: EKS cluster (multi-AZ)

## Infrastructure as Code

### Terraform Structure

```
terraform/
├── modules/          # Reusable modules
│   ├── vpc/         # VPC, subnets, NAT
│   ├── rds/         # PostgreSQL
│   ├── storage/     # S3 buckets
│   ├── queue/       # SQS queues
│   └── ...
└── environments/    # Environment configs
    ├── dev/
    ├── staging/
    └── prod/
```

### Deploy Infrastructure

```bash
# Development
cd terraform/environments/dev
terraform init
terraform plan
terraform apply

# Production
cd terraform/environments/prod
terraform init
terraform plan -var="database_password=SECURE_PASSWORD"
terraform apply -var="database_password=SECURE_PASSWORD"
```

### Infrastructure Updates

1. **Plan changes**: `terraform plan`
2. **Review changes**: Check output
3. **Apply changes**: `terraform apply`
4. **Verify**: Check AWS console

## Monitoring & Observability

### CloudWatch Metrics

**Database:**
- CPU utilization
- Storage space
- Connection count
- Read/Write IOPS

**Application:**
- Request count
- Error rate
- Response time
- Queue depth

**Infrastructure:**
- Pod CPU/Memory
- Network traffic
- S3 request count

### CloudWatch Alarms

**Critical:**
- Database CPU > 80%
- Database storage < 10GB
- Error rate > 5%
- Queue depth > 1000

**Warning:**
- CPU > 70%
- Memory > 80%
- Response time > 1s

### Logging

**CloudWatch Logs:**
- Application logs: `/audiobook/prod/app`
- Worker logs: `/audiobook/prod/worker`
- Database logs: RDS logs

**Log Levels:**
- `DEBUG`: Development only
- `INFO`: Normal operations
- `WARNING`: Recoverable issues
- `ERROR`: Failures
- `CRITICAL`: System failures

### Dashboards

**Grafana Dashboards:**
- Application metrics
- Infrastructure metrics
- Business metrics (jobs processed, etc.)

## Incident Response

### Severity Levels

**P0 - Critical:**
- Service completely down
- Data loss
- Security breach

**P1 - High:**
- Service degraded
- High error rate
- Performance issues

**P2 - Medium:**
- Non-critical feature broken
- Minor performance issues

**P3 - Low:**
- Cosmetic issues
- Documentation updates

### On-Call Rotation

- **Primary**: 24/7 coverage
- **Secondary**: Escalation
- **Escalation**: Engineering lead

### Incident Process

1. **Detect**: Alert triggered
2. **Acknowledge**: On-call responds
3. **Assess**: Determine severity
4. **Mitigate**: Stop the bleeding
5. **Resolve**: Fix root cause
6. **Post-mortem**: Document learnings

## Runbooks

### Database Issues

**Problem**: Database connection failures

**Steps:**
1. Check RDS status: `aws rds describe-db-instances`
2. Check security groups
3. Check connection pool settings
4. Scale up if needed: `terraform apply -var="instance_class=db.t3.large"`

### High Queue Depth

**Problem**: SQS queue backing up

**Steps:**
1. Check queue depth: `aws sqs get-queue-attributes`
2. Scale workers: `kubectl scale deployment audiobook-worker --replicas=10`
3. Check worker logs: `kubectl logs -f deployment/audiobook-worker`
4. Investigate slow jobs

### High Error Rate

**Problem**: Application errors increasing

**Steps:**
1. Check logs: `kubectl logs -f deployment/audiobook-web`
2. Check CloudWatch metrics
3. Check recent deployments
4. Rollback if needed: `helm rollback audiobook`

### Storage Issues

**Problem**: S3 errors or slow uploads

**Steps:**
1. Check S3 bucket: `aws s3 ls s3://bucket-name`
2. Check IAM permissions
3. Check network connectivity
4. Check storage class (may need to move to Standard)

## Launch Checklist

### Pre-Launch

- [ ] Infrastructure deployed via Terraform
- [ ] Kubernetes cluster configured
- [ ] Database backups enabled
- [ ] Monitoring and alerts configured
- [ ] Logging configured
- [ ] Secrets in Secrets Manager
- [ ] DNS configured
- [ ] SSL certificates issued
- [ ] Load testing completed
- [ ] Disaster recovery plan documented

### Launch Day

- [ ] Deploy to staging first
- [ ] Verify staging deployment
- [ ] Run smoke tests
- [ ] Deploy to production
- [ ] Monitor metrics closely
- [ ] Verify health checks
- [ ] Check error rates
- [ ] Monitor queue depth
- [ ] Verify database connections

### Post-Launch

- [ ] Monitor for 24 hours
- [ ] Review metrics and logs
- [ ] Address any issues
- [ ] Document learnings
- [ ] Update runbooks

## Best Practices

### Infrastructure

1. **Use Terraform**: All infrastructure in code
2. **Version state**: S3 versioning enabled
3. **Tag resources**: For cost tracking
4. **Multi-AZ**: For production HA
5. **Backups**: Automated daily backups

### Application

1. **Health checks**: Liveness and readiness probes
2. **Graceful shutdown**: Handle SIGTERM
3. **Retries**: Exponential backoff
4. **Circuit breakers**: Prevent cascading failures
5. **Rate limiting**: Protect APIs

### Monitoring

1. **Dashboards**: Key metrics visible
2. **Alerts**: Actionable alerts only
3. **Logging**: Structured logging
4. **Tracing**: Distributed tracing (optional)
5. **SLIs/SLOs**: Define and measure

### Security

1. **Secrets**: Never in code or Git
2. **IAM**: Least privilege
3. **Encryption**: At rest and in transit
4. **Network**: Security groups configured
5. **Updates**: Regular security patches

## Resources

- **Terraform Docs**: `terraform/README.md`
- **Kubernetes Docs**: `k8s/README.md`
- **Helm Chart**: `helm/audiobook/README.md`
- **API Docs**: `docs/API.md`
- **Architecture**: `docs/ARCHITECTURE.md`
