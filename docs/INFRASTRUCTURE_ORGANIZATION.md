# Infrastructure Organization Guide

How the infrastructure stack is organized for clarity, maintainability, and scalability.

## 📐 Organization Principles

1. **Separation of Concerns**: Each layer has its own modules
2. **Reusability**: Modules can be used across environments
3. **Clarity**: Easy to find and understand components
4. **Scalability**: Easy to add new modules or environments

## 🏗️ Structure Overview

```
terraform/
├── modules/                    # Reusable components
│   ├── networking/            # Network infrastructure
│   ├── compute/               # Compute resources
│   ├── data/                  # Data layer
│   ├── messaging/             # Messaging layer
│   ├── observability/         # Monitoring & logging
│   └── security/              # Security & IAM
│
└── environments/              # Environment configs
    ├── dev/                   # Development
    ├── staging/               # Staging
    └── prod/                  # Production
```

## 📦 Module Layers

### 1. Networking Layer (`modules/networking/`)

**Purpose**: Network infrastructure and connectivity

**Modules**:
- `vpc/`: VPC, subnets, NAT gateway, internet gateway
- `security-groups/`: Network security rules (future)
- `vpc-endpoints/`: VPC endpoints for AWS services (future)

**Dependencies**: None (foundation layer)

**Used By**: All other layers

### 2. Compute Layer (`modules/compute/`)

**Purpose**: Compute resources (containers, servers)

**Modules**:
- `eks/`: EKS cluster (future)
- `ec2/`: EC2 instances (if needed)
- `fargate/`: Fargate tasks (future)

**Dependencies**: Networking

**Used By**: Application deployment

### 3. Data Layer (`modules/data/`)

**Purpose**: Data storage and databases

**Modules**:
- `rds/`: PostgreSQL database
- `storage/`: S3 buckets
- `cache/`: ElastiCache (future)

**Dependencies**: Networking

**Used By**: Application services

### 4. Messaging Layer (`modules/messaging/`)

**Purpose**: Asynchronous messaging and notifications

**Modules**:
- `queue/`: SQS queues
- `notifications/`: SNS topics

**Dependencies**: None (uses AWS services)

**Used By**: Application services

### 5. Observability Layer (`modules/observability/`)

**Purpose**: Monitoring, logging, and tracing

**Modules**:
- `logging/`: CloudWatch Logs
- `monitoring/`: CloudWatch Alarms
- `tracing/`: X-Ray (future)

**Dependencies**: None (uses AWS services)

**Used By**: All layers (monitoring)

### 6. Security Layer (`modules/security/`)

**Purpose**: Security and access control

**Modules**:
- `iam/`: IAM roles and policies
- `secrets/`: Secrets Manager integration

**Dependencies**: None (uses AWS services)

**Used By**: All layers (security)

## 🌍 Environment Structure

Each environment follows the same structure:

```
environments/
└── {env}/
    ├── main.tf              # Main configuration
    ├── variables.tf         # Input variables
    ├── outputs.tf          # Output values
    ├── terraform.tfvars    # Variable values (gitignored)
    └── README.md           # Environment-specific docs
```

### Environment Differences

**Development**:
- Single AZ
- Smaller instance sizes
- No NAT gateway (cost savings)
- Shorter retention periods

**Staging**:
- Multi-AZ (2 zones)
- Medium instance sizes
- NAT gateway enabled
- Moderate retention periods

**Production**:
- Multi-AZ (3 zones)
- Larger instance sizes
- NAT gateway enabled
- Longer retention periods
- Enhanced monitoring
- Backup policies

## 🔄 Module Dependencies

```
networking (VPC)
    ↓
compute (EKS/EC2)
    ↓
data (RDS, S3)
    ↓
messaging (SQS, SNS)
    ↓
observability (CloudWatch)
    ↑
security (IAM, Secrets)
```

## 📝 Module Standards

### Module Structure

Each module should have:

```
module-name/
├── main.tf          # Resource definitions
├── variables.tf     # Input variables
├── outputs.tf       # Output values
├── README.md        # Documentation
└── versions.tf      # Provider versions (optional)
```

### Variable Naming

- Use descriptive names: `database_instance_class` not `db_class`
- Group related variables: `database_*`, `storage_*`
- Use consistent prefixes: `{resource}_{property}`

### Output Naming

- Match resource names: `vpc_id`, `database_endpoint`
- Use descriptive names: `s3_bucket_arn` not `bucket_arn`
- Group outputs logically

## 🎯 Usage Examples

### Basic Environment Setup

```hcl
# environments/prod/main.tf

# Networking
module "vpc" {
  source = "../../modules/networking/vpc"
  # ...
}

# Data Layer
module "database" {
  source = "../../modules/data/rds"
  subnet_ids = module.vpc.private_subnet_ids
  # ...
}

module "storage" {
  source = "../../modules/data/storage"
  # ...
}

# Messaging
module "queue" {
  source = "../../modules/messaging/queue"
  # ...
}

# Observability
module "logging" {
  source = "../../modules/observability/logging"
  # ...
}
```

### Module Composition

```hcl
# Create a "foundation" module that combines common modules
module "foundation" {
  source = "../../modules/foundation"
  
  # This module internally uses:
  # - networking/vpc
  # - data/rds
  # - data/storage
  # - observability/logging
}
```

## 🔍 Finding Modules

### By Purpose

- **Need networking?** → `modules/networking/`
- **Need storage?** → `modules/data/storage/`
- **Need monitoring?** → `modules/observability/`

### By Resource Type

- **VPC/Subnets** → `modules/networking/vpc/`
- **RDS Database** → `modules/data/rds/`
- **S3 Bucket** → `modules/data/storage/`
- **SQS Queue** → `modules/messaging/queue/`
- **CloudWatch** → `modules/observability/logging/`

## 🚀 Adding New Modules

1. **Choose Layer**: Determine which layer the module belongs to
2. **Create Structure**: Follow module standards
3. **Document**: Add README with examples
4. **Test**: Test in dev environment first
5. **Use**: Reference in environment configs

### Example: Adding Redis Cache

```bash
# Create module
mkdir -p terraform/modules/data/cache/redis

# Create files
touch terraform/modules/data/cache/redis/{main.tf,variables.tf,outputs.tf,README.md}

# Use in environment
# environments/prod/main.tf
module "cache" {
  source = "../../modules/data/cache/redis"
  # ...
}
```

## 📊 Module Relationships

```
┌─────────────┐
│  Networking │ (Foundation)
└──────┬──────┘
       │
       ├──────────────┬──────────────┐
       │              │              │
┌──────▼──────┐  ┌───▼──────┐  ┌───▼──────┐
│   Compute   │  │   Data   │  │ Messaging│
└──────┬──────┘  └────┬─────┘  └──────────┘
       │              │
       └──────┬───────┘
              │
       ┌──────▼──────┐
       │Observability│ (Cross-cutting)
       └─────────────┘
              │
       ┌──────▼──────┐
       │  Security   │ (Cross-cutting)
       └─────────────┘
```

## 🎓 Best Practices

1. **One Module Per Resource Type**: Don't mix concerns
2. **Clear Dependencies**: Document what modules depend on
3. **Consistent Naming**: Use same patterns across modules
4. **Version Modules**: Tag module versions for stability
5. **Document Everything**: README in every module
6. **Test Locally**: Test modules in dev before prod
7. **Review Changes**: Code review all infrastructure changes

## 🔗 Related Documentation

- [Terraform README](../terraform/README.md)
- [SRE Guide](SRE_GUIDE.md)
- [Production Deployment](PRODUCTION_DEPLOYMENT.md)
