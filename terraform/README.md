# Terraform Infrastructure

Infrastructure as Code for Audiobook Generator deployment on AWS.

## Structure

```
terraform/
├── modules/           # Reusable modules
│   ├── vpc/          # VPC, subnets, NAT gateway
│   ├── rds/          # PostgreSQL database
│   ├── storage/      # S3 buckets
│   ├── queue/        # SQS queues
│   ├── notifications/# SNS topics
│   └── logging/      # CloudWatch Logs
└── environments/     # Environment-specific configs
    ├── dev/          # Development
    ├── staging/      # Staging
    └── prod/         # Production
```

## Prerequisites

1. **AWS CLI** configured with credentials
2. **Terraform** >= 1.0
3. **S3 bucket** for Terraform state (create manually first)

## Quick Start

### 1. Create State Bucket

```bash
aws s3 mb s3://audiobook-terraform-state --region us-east-1
aws s3api put-bucket-versioning \
  --bucket audiobook-terraform-state \
  --versioning-configuration Status=Enabled
```

### 2. Initialize Terraform

```bash
cd terraform/environments/dev
terraform init
```

### 3. Plan Changes

```bash
terraform plan -out=tfplan
```

### 4. Apply Changes

```bash
terraform apply tfplan
```

## Environments

### Development

```bash
cd terraform/environments/dev
terraform init
terraform plan
terraform apply
```

**Features:**
- Single AZ deployment
- No NAT gateway (cost savings)
- Shorter log retention (7 days)
- No DLQ (cost savings)

### Production

```bash
cd terraform/environments/prod
terraform init
terraform plan -var="database_password=SECURE_PASSWORD"
terraform apply -var="database_password=SECURE_PASSWORD"
```

**Features:**
- Multi-AZ deployment
- NAT gateway enabled
- RDS with multi-AZ
- CloudWatch alarms
- Longer log retention (90 days)
- DLQ enabled
- Lifecycle policies for S3

## Modules

### VPC Module

Creates VPC with public and private subnets, NAT gateway, and internet gateway.

```hcl
module "vpc" {
  source = "../../modules/vpc"
  
  name         = "audiobook"
  environment  = "prod"
  cidr         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
}
```

### RDS Module

Creates PostgreSQL database with encryption, backups, and monitoring.

```hcl
module "database" {
  source = "../../modules/rds"
  
  name         = "audiobook"
  environment  = "prod"
  subnet_ids   = module.vpc.private_subnet_ids
  vpc_id       = module.vpc.vpc_id
  
  instance_class = "db.t3.medium"
  multi_az       = true
}
```

### Storage Module

Creates S3 bucket with versioning, encryption, and lifecycle policies.

```hcl
module "storage" {
  source = "../../modules/storage"
  
  name         = "audiobook"
  environment  = "prod"
  bucket_name  = "audiobook-prod-data"
  
  versioning_enabled = true
}
```

### Queue Module

Creates SQS queue with dead letter queue.

```hcl
module "queue" {
  source = "../../modules/queue"
  
  name         = "audiobook"
  environment  = "prod"
  queue_name   = "audiobook-prod-jobs"
  
  dead_letter_queue_enabled = true
}
```

## State Management

Terraform state is stored in S3 with versioning enabled. Use remote state locking with DynamoDB for team collaboration:

```bash
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

Then update backend configuration:

```hcl
backend "s3" {
  bucket         = "audiobook-terraform-state"
  key            = "prod/terraform.tfstate"
  region         = "us-east-1"
  encrypt        = true
  dynamodb_table = "terraform-state-lock"
}
```

## Outputs

After applying, get outputs:

```bash
terraform output
```

Use outputs in Kubernetes/application configuration:

```bash
export S3_BUCKET=$(terraform output -raw s3_bucket_name)
export SQS_QUEUE_URL=$(terraform output -raw sqs_queue_url)
export DATABASE_ENDPOINT=$(terraform output -raw database_endpoint)
```

## Secrets Management

**Never commit secrets to Git!**

Use Terraform variables or AWS Secrets Manager:

```bash
# Via environment variable
export TF_VAR_database_password="secure_password"

# Via file (add to .gitignore)
terraform apply -var-file=secrets.tfvars
```

For production, use AWS Secrets Manager:

```hcl
data "aws_secretsmanager_secret_version" "db_password" {
  secret_id = "audiobook/database/password"
}

locals {
  db_password = jsondecode(data.aws_secretsmanager_secret_version.db_password.secret_string)["password"]
}
```

## Cost Optimization

### Development
- Single AZ
- No NAT gateway
- Smaller instance sizes
- Shorter retention periods

### Production
- Multi-AZ for HA
- Reserved instances for RDS
- S3 lifecycle policies
- CloudWatch log retention limits

## Destroying Infrastructure

**⚠️ WARNING: This will delete all resources!**

```bash
terraform destroy
```

For production, add confirmation:

```bash
terraform destroy -var="database_password=..." -auto-approve=false
```

## Best Practices

1. **Always use modules** - Don't duplicate code
2. **Version state backend** - Enable S3 versioning
3. **Use workspaces** - Separate state per environment
4. **Tag resources** - For cost tracking
5. **Review plans** - Always review before apply
6. **Backup state** - Keep state backups
7. **Use variables** - Don't hardcode values
8. **Document changes** - Update README with changes

## Troubleshooting

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

## CI/CD Integration

See `.github/workflows/terraform.yml` for automated Terraform runs.
