# SNS Topic Module

terraform {
  required_version = ">= 1.0"
}

variable "name" {
  description = "Name prefix for resources"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "topic_name" {
  description = "SNS topic name"
  type        = string
}

variable "email_subscriptions" {
  description = "List of email addresses to subscribe"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

# SNS Topic
resource "aws_sns_topic" "main" {
  name = var.topic_name

  tags = merge(
    var.tags,
    {
      Name        = "${var.name}-${var.environment}-${var.topic_name}"
      Environment = var.environment
    }
  )
}

# Email Subscriptions
resource "aws_sns_topic_subscription" "email" {
  count     = length(var.email_subscriptions)
  topic_arn = aws_sns_topic.main.arn
  protocol  = "email"
  endpoint  = var.email_subscriptions[count.index]
}

# Outputs
output "topic_arn" {
  description = "SNS topic ARN"
  value       = aws_sns_topic.main.arn
}

output "topic_name" {
  description = "SNS topic name"
  value       = aws_sns_topic.main.name
}
