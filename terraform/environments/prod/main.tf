# Production Environment

terraform {
  required_version = ">= 1.0"
  
  backend "s3" {
    bucket = "audiobook-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = "prod"
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
  description = "Database password (use Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "notification_emails" {
  description = "Email addresses for notifications"
  type        = list(string)
  default     = []
}

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  name         = var.name
  environment  = "prod"
  cidr         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  enable_nat_gateway = true

  tags = {
    Environment = "prod"
  }
}

# RDS Database
module "database" {
  source = "../../modules/rds"

  name         = var.name
  environment  = "prod"
  subnet_ids   = module.vpc.private_subnet_ids
  vpc_id       = module.vpc.vpc_id

  instance_class         = "db.t3.medium"
  allocated_storage      = 100
  max_allocated_storage  = 500
  database_password      = var.database_password

  multi_az            = true
  deletion_protection = true
  backup_retention_period = 30

  tags = {
    Environment = "prod"
  }
}

# S3 Storage
module "storage" {
  source = "../../modules/storage"

  name         = var.name
  environment  = "prod"
  bucket_name  = "${var.name}-prod-data-${data.aws_caller_identity.current.account_id}"

  versioning_enabled = true

  lifecycle_rules = [
    {
      id     = "transition-to-ia"
      status = "Enabled"
      transitions = [
        {
          days          = 30
          storage_class = "STANDARD_IA"
        },
        {
          days          = 90
          storage_class = "GLACIER"
        }
      ]
    }
  ]
}

# SQS Queue
module "queue" {
  source = "../../modules/queue"

  name         = var.name
  environment  = "prod"
  queue_name   = "${var.name}-prod-jobs"

  dead_letter_queue_enabled = true
  max_receive_count         = 3
}

# SNS Topic
module "notifications" {
  source = "../../modules/notifications"

  name         = var.name
  environment  = "prod"
  topic_name   = "${var.name}-prod-notifications"

  email_subscriptions = var.notification_emails
}

# CloudWatch Logs
module "logging" {
  source = "../../modules/logging"

  name         = var.name
  environment  = "prod"
  log_group_name = "/${var.name}/prod"

  retention_in_days = 90
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "database_cpu" {
  alarm_name          = "${var.name}-prod-db-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Database CPU utilization is high"
  alarm_actions       = [module.notifications.topic_arn]

  dimensions = {
    DBInstanceIdentifier = module.database.db_instance_id
  }
}

resource "aws_cloudwatch_metric_alarm" "database_storage" {
  alarm_name          = "${var.name}-prod-db-storage"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "10000000000"  # 10GB
  alarm_description   = "Database storage is low"
  alarm_actions       = [module.notifications.topic_arn]

  dimensions = {
    DBInstanceIdentifier = module.database.db_instance_id
  }
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
