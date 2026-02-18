# Audiobook Generator

Production-ready audiobook generation system with full SRE infrastructure.

## 🚀 Quick Start

### Local Development

```bash
# One-command setup
make local-dev

# Or manually
docker-compose -f docker-compose.local.yml up -d
```

Access:
- **Web UI**: http://localhost:8000
- **Database**: localhost:5432
- **LocalStack**: http://localhost:4566

### With Observability Stack

```bash
# Start app + observability (Prometheus, Grafana, Loki, Tempo)
make local-dev-full

# Or start observability separately
make observability-up
```

Access:
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Metrics**: http://localhost:8000/metrics

### Production Deployment

See [SRE Guide](docs/SRE_GUIDE.md) for complete production deployment.

## 📋 Features

- ✅ **Text-to-Speech**: Multiple TTS engines (Coqui XTTSv2, fine-tuned models)
- ✅ **Ebook Processing**: EPUB, MOBI, PDF, TXT support
- ✅ **Audio Generation**: M4B with chapter markers
- ✅ **Scalable Architecture**: Kubernetes-ready
- ✅ **Infrastructure as Code**: Terraform modules
- ✅ **CI/CD**: GitHub Actions pipelines
- ✅ **Observability**: Prometheus, Grafana, Loki, Tempo (local + production)
- ✅ **Monitoring**: CloudWatch integration
- ✅ **Storage**: S3-compatible (LocalStack/AWS)

## 🏗️ Architecture

```
┌─────────────┐
│   Web UI    │
│  (FastAPI)  │
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
┌──────▼──────┐  ┌────▼──────┐  ┌───▼────────┐
│  PostgreSQL │  │  Worker   │  │ LocalStack │
│  Database   │  │  Service  │  │  (S3)      │
└─────────────┘  └───────────┘  └────────────┘
```

## 📁 Project Structure

```
.
├── backend/              # Python backend
│   ├── src/
│   │   ├── controllers/ # API controllers
│   │   ├── services/    # Business logic
│   │   ├── storage/     # S3 storage abstraction
│   │   ├── monitoring/  # CloudWatch, SNS, Secrets Manager
│   │   └── web/         # FastAPI application
│   └── tests/           # Test suite
├── frontend/            # React frontend
├── terraform/           # Infrastructure as Code
│   ├── modules/         # Reusable modules
│   └── environments/    # Environment configs
├── k8s/                 # Kubernetes manifests
├── helm/                # Helm chart
├── monitoring/          # Observability configs (Prometheus, Grafana, Loki, Tempo)
├── .github/workflows/   # CI/CD pipelines
└── docs/                # Documentation
```

## 🛠️ Development

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
- Terraform (for infrastructure)

### Setup

```bash
# Install dependencies
make setup

# Start local dev environment
make local-dev

# Run tests
make test

# Run linters
make lint
```

### Make Commands

```bash
make help                  # Show all commands
make local-dev             # Start local dev environment
make local-dev-full        # Start app + observability stack
make observability-up      # Start observability stack only
make observability-down    # Stop observability stack
make grafana               # Open Grafana dashboard
make test                  # Run tests
make lint                  # Run linters
make format                # Format code
```

## 🚢 Deployment

### Docker Compose

```bash
# Development (LocalStack)
docker-compose -f docker-compose.local.yml up -d

# Production (AWS)
docker-compose up -d
```

### Kubernetes

```bash
# Using Helm
helm install audiobook ./helm/audiobook \
  --namespace audiobook \
  --create-namespace

# Using raw manifests
kubectl apply -f k8s/
```

### Terraform

```bash
# Development
cd terraform/environments/dev
terraform init
terraform apply

# Production
cd terraform/environments/prod
terraform init
terraform apply -var="database_password=SECURE_PASSWORD"
```

## 📚 Documentation

- **[SRE Guide](docs/SRE_GUIDE.md)**: Complete production deployment guide
- **[Observability Guide](docs/OBSERVABILITY.md)**: Metrics, logs, and tracing setup
- **[Infrastructure Organization](docs/INFRASTRUCTURE_ORGANIZATION.md)**: Terraform module structure
- **[Production Deployment](docs/PRODUCTION_DEPLOYMENT.md)**: Deployment details
- **[LocalStack S3](docs/LOCALSTACK_S3.md)**: S3 storage guide
- **[Docker Full Stack](docs/DOCKER_FULL_STACK.md)**: Docker Compose guide
- **[Terraform](terraform/README.md)**: Infrastructure documentation
- **[Architecture](docs/ARCHITECTURE.md)**: System architecture

## 🔧 Configuration

### Environment Variables

See `.env.example` for all configuration options.

**Key Variables:**
- `DATABASE_URL`: PostgreSQL connection string
- `S3_BUCKET_NAME`: S3 bucket name
- `S3_ENDPOINT_URL`: S3 endpoint (empty for AWS, `http://localstack:4566` for LocalStack)
- `SQS_USE_QUEUE`: Enable SQS queue (true/false)
- `CLOUDWATCH_LOG_GROUP`: CloudWatch log group name

## 🧪 Testing

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

## 📊 Monitoring

- **CloudWatch Logs**: Centralized logging
- **CloudWatch Metrics**: Application metrics
- **Health Checks**: `/health` endpoint
- **Kubernetes**: Pod metrics and HPA

## 🔒 Security

- Secrets in Kubernetes Secrets / AWS Secrets Manager
- IAM roles for AWS access
- Network policies (Kubernetes)
- TLS/SSL encryption
- Database encryption at rest

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Run tests and linters
5. Submit a pull request

## 📝 License

[Your License Here]

## 🙏 Acknowledgments

- [Coqui TTS](https://github.com/coqui-ai/TTS)
- [LocalStack](https://localstack.cloud/)
- [FastAPI](https://fastapi.tiangolo.com/)
