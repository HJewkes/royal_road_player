# Terraform Infrastructure

Infrastructure as Code for Audiobook Generator deployment on AWS.

## 📁 Structure

```
terraform/
├── modules/                    # Reusable Terraform modules
│   ├── networking/             # VPC, subnets, NAT, IGW
│   │   └── vpc/
│   ├── compute/                # EKS, EC2 (if needed)
│   │   └── eks/                # EKS cluster (future)
│   ├── data/                   # Data layer
│   │   ├── rds/                # PostgreSQL database
│   │   ├── storage/            # S3 buckets
│   │   └── cache/              # ElastiCache (future)
│   ├── messaging/              # Messaging layer
│   │   ├── queue/              # SQS queues
│   │   └── notifications/      # SNS topics
│   ├── observability/          # Observability stack
│   │   ├── logging/            # CloudWatch Logs
│   │   ├── monitoring/         # CloudWatch Alarms
│   │   └── tracing/            # X-Ray (future)
│   └── security/               # Security layer
│       ├── iam/                # IAM roles and policies
│       └── secrets/            # Secrets Manager
│
└── environments/               # Environment-specific configurations
    ├── dev/                    # Development environment
    │   ├── main.tf             # Main configuration
    │   ├── variables.tf        # Input variables
    │   ├── outputs.tf          # Output values
    │   └── terraform.tfvars    # Variable values (gitignored)
    ├── staging/                 # Staging environment
    │   └── ...
    └── prod/                    # Production environment
        └── ...
```

## 🏗️ Module Organization

### Networking (`modules/networking/`)
- **VPC**: Virtual Private Cloud with public/private subnets
- **NAT Gateway**: For private subnet internet access
- **Internet Gateway**: For public subnet internet access
- **Route Tables**: Routing configuration
- **Security Groups**: Network security rules

### Data (`modules/data/`)
- **RDS**: Managed PostgreSQL database
- **Storage**: S3 buckets with versioning and lifecycle policies
- **Cache**: ElastiCache (Redis/Memcached) - future

### Messaging (`modules/messaging/`)
- **Queue**: SQS queues with dead letter queues
- **Notifications**: SNS topics with subscriptions

### Observability (`modules/observability/`)
- **Logging**: CloudWatch Log Groups
- **Monitoring**: CloudWatch Alarms and Dashboards
- **Tracing**: X-Ray (future)

### Security (`modules/security/`)
- **IAM**: Roles, policies, and service accounts
- **Secrets**: Secrets Manager integration

## 🚀 Quick Start

### Prerequisites

1. **AWS CLI** configured
2. **Terraform** >= 1.0
3. **S3 bucket** for state storage (create manually)

### Initialize State Bucket

```bash
aws s3 mb s3://audiobook-terraform-state --region us-east-1
aws s3api put-bucket-versioning \
  --bucket audiobook-terraform-state \
  --versioning-configuration Status=Enabled
```

### Deploy Development Environment

```bash
cd terraform/environments/dev
terraform init
terraform plan
terraform apply
```

### Deploy Production Environment

```bash
cd terraform/environments/prod
terraform init
terraform plan -var="database_password=SECURE_PASSWORD"
terraform apply -var="database_password=SECURE_PASSWORD"
```

## 📋 Module Usage

### VPC Module

```hcl
module "vpc" {
  source = "../../modules/networking/vpc"
  
  name         = "audiobook"
  environment  = "prod"
  cidr         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  enable_nat_gateway = true
}
```

### RDS Module

```hcl
module "database" {
  source = "../../modules/data/rds"
  
  name         = "audiobook"
  environment  = "prod"
  subnet_ids   = module.vpc.private_subnet_ids
  vpc_id       = module.vpc.vpc_id
  
  instance_class = "db.t3.medium"
  multi_az       = true
  database_password = var.database_password
}
```

### Storage Module

```hcl
module "storage" {
  source = "../../modules/data/storage"
  
  name         = "audiobook"
  environment  = "prod"
  bucket_name  = "audiobook-prod-data-${data.aws_caller_identity.current.account_id}"
  
  versioning_enabled = true
}
```

## 🔐 Secrets Management

**Never commit secrets to Git!**

### Using Variables

```bash
# Via environment variable
export TF_VAR_database_password="secure_password"

# Via file (add to .gitignore)
terraform apply -var-file=secrets.tfvars
```

### Using AWS Secrets Manager

```hcl
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "audiobook/database/password"
}

locals {
  db_password = jsondecode(
    data.aws_secretsmanager_secret_version.db_password.secret_string
  )["password"]
}
```

## 📊 Outputs

Get infrastructure outputs:

```bash
terraform output
```

Use outputs in Kubernetes/application:

```bash
export S3_BUCKET=$(terraform output -raw s3_bucket_name)
export DATABASE_ENDPOINT=$(terraform output -raw database_endpoint)
```

## 🔄 State Management

### Remote State

State is stored in S3 with versioning:

```hcl
backend "s3" {
  bucket = "audiobook-terraform-state"
  key    = "prod/terraform.tfstate"
  region = "us-east-1"
  encrypt = true
}
```

### State Locking

Use DynamoDB for state locking:

```bash
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

Then update backend:

```hcl
backend "s3" {
  # ... existing config ...
  dynamodb_table = "terraform-state-lock"
}
```

## 🧹 Best Practices

1. **Use Modules**: Don't duplicate code
2. **Version State**: Enable S3 versioning
3. **Lock State**: Use DynamoDB for team collaboration
4. **Tag Resources**: For cost tracking
5. **Review Plans**: Always review before apply
6. **Separate Environments**: Use separate state files
7. **Document Changes**: Update README with changes
8. **Use Variables**: Don't hardcode values

## 🚨 Destroying Infrastructure

**⚠️ WARNING: This will delete all resources!**

```bash
terraform destroy
```

For production, require confirmation:

```bash
terraform destroy -var="database_password=..." -auto-approve=false
```

## 📚 Module Documentation

Each module includes:
- **README.md**: Usage and examples
- **variables.tf**: Input variables
- **outputs.tf**: Output values
- **main.tf**: Resource definitions

## 🔍 Troubleshooting

### State Locked

```bash
# Force unlock (use with caution!)
terraform force-unlock <LOCK_ID>
```

### State Out of Sync

```bash
# Refresh state
terraform refresh

# Import existing resource
terraform import aws_s3_bucket.main bucket-name
```

### Module Not Found

```bash
# Reinitialize modules
terraform init -upgrade
```

## 🔗 Related Documentation

- [SRE Guide](../docs/SRE_GUIDE.md)
- [Production Deployment](../docs/PRODUCTION_DEPLOYMENT.md)
- [Infrastructure Organization](../docs/INFRASTRUCTURE_ORGANIZATION.md)
