# Staging Environment

terraform {
  required_version = ">= 1.0"
  
  backend "s3" {
    bucket = "audiobook-terraform-state"
    key    = "staging/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = "staging"
      Project     = "audiobook"
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Name prefix"
  type        = string
  default     = "audiobook"
}

variable "database_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  name         = var.name
  environment  = "staging"
  cidr         = "10.1.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  enable_nat_gateway = true

  tags = {
    Environment = "staging"
  }
}

# RDS Database
module "database" {
  source = "../../modules/rds"

  name         = var.name
  environment  = "staging"
  subnet_ids   = module.vpc.private_subnet_ids
  vpc_id       = module.vpc.vpc_id

  instance_class         = "db.t3.small"
  allocated_storage      = 50
  max_allocated_storage  = 200
  database_password      = var.database_password

  multi_az            = false  # Single AZ for staging
  deletion_protection = false
  backup_retention_period = 7

  tags = {
    Environment = "staging"
  }
}

# S3 Storage
module "storage" {
  source = "../../modules/storage"

  name         = var.name
  environment  = "staging"
  bucket_name  = "${var.name}-staging-data-${data.aws_caller_identity.current.account_id}"

  versioning_enabled = true
}

# SQS Queue
module "queue" {
  source = "../../modules/queue"

  name         = var.name
  environment  = "staging"
  queue_name   = "${var.name}-staging-jobs"

  dead_letter_queue_enabled = true
  max_receive_count         = 3
}

# SNS Topic
module "notifications" {
  source = "../../modules/notifications"

  name         = var.name
  environment  = "staging"
  topic_name   = "${var.name}-staging-notifications"

  email_subscriptions = []
}

# CloudWatch Logs
module "logging" {
  source = "../../modules/logging"

  name         = var.name
  environment  = "staging"
  log_group_name = "/${var.name}/staging"

  retention_in_days = 30
}

# Data sources
data "aws_caller_identity" "current" {}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "database_endpoint" {
  value = module.database.db_endpoint
}

output "s3_bucket_name" {
  value = module.storage.bucket_id
}

output "sqs_queue_url" {
  value = module.queue.queue_url
}

output "sns_topic_arn" {
  value = module.notifications.topic_arn
}

output "cloudwatch_log_group" {
  value = module.logging.log_group_name
}
