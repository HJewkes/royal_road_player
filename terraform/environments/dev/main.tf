# Development Environment

terraform {
  required_version = ">= 1.0"
  
  backend "s3" {
    bucket = "audiobook-terraform-state"
    key    = "dev/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = "dev"
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

# VPC Module
module "vpc" {
  source = "../../modules/vpc"

  name         = var.name
  environment  = "dev"
  cidr         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  enable_nat_gateway = false  # Save costs in dev

  tags = {
    Environment = "dev"
  }
}

# S3 Storage
module "storage" {
  source = "../../modules/storage"

  name         = var.name
  environment  = "dev"
  bucket_name = "${var.name}-dev-data-${data.aws_caller_identity.current.account_id}"

  versioning_enabled = false  # Save costs in dev
}

# SQS Queue
module "queue" {
  source = "../../modules/queue"

  name         = var.name
  environment  = "dev"
  queue_name   = "${var.name}-dev-jobs"

  dead_letter_queue_enabled = false  # Save costs in dev
}

# SNS Topic
module "notifications" {
  source = "../../modules/notifications"

  name         = var.name
  environment  = "dev"
  topic_name   = "${var.name}-dev-notifications"

  email_subscriptions = []  # Add emails as needed
}

# CloudWatch Logs
module "logging" {
  source = "../../modules/logging"

  name         = var.name
  environment  = "dev"
  log_group_name = "/${var.name}/dev"

  retention_in_days = 7  # Shorter retention in dev
}

# Data sources
data "aws_caller_identity" "current" {}

# Outputs
output "vpc_id" {
  value = module.vpc.vpc_id
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
