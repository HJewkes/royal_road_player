# SQS Queue Module

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

variable "queue_name" {
  description = "SQS queue name"
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "Visibility timeout in seconds"
  type        = number
  default     = 300
}

variable "message_retention_seconds" {
  description = "Message retention period in seconds"
  type        = number
  default     = 1209600  # 14 days
}

variable "receive_wait_time_seconds" {
  description = "Long polling wait time in seconds"
  type        = number
  default     = 20
}

variable "dead_letter_queue_enabled" {
  description = "Enable dead letter queue"
  type        = bool
  default     = true
}

variable "max_receive_count" {
  description = "Maximum receive count before moving to DLQ"
  type        = number
  default     = 3
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

# Dead Letter Queue
resource "aws_sqs_queue" "dlq" {
  count = var.dead_letter_queue_enabled ? 1 : 0

  name                      = "${var.queue_name}-dlq"
  message_retention_seconds = var.message_retention_seconds

  tags = merge(
    var.tags,
    {
      Name        = "${var.name}-${var.environment}-${var.queue_name}-dlq"
      Environment = var.environment
    }
  )
}

# Main Queue
resource "aws_sqs_queue" "main" {
  name                      = var.queue_name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds = var.message_retention_seconds
  receive_wait_time_seconds = var.receive_wait_time_seconds

  redrive_policy = var.dead_letter_queue_enabled ? jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[0].arn
    maxReceiveCount     = var.max_receive_count
  }) : null

  tags = merge(
    var.tags,
    {
      Name        = "${var.name}-${var.environment}-${var.queue_name}"
      Environment = var.environment
    }
  )
}

# Outputs
output "queue_url" {
  description = "SQS queue URL"
  value       = aws_sqs_queue.main.url
}

output "queue_arn" {
  description = "SQS queue ARN"
  value       = aws_sqs_queue.main.arn
}

output "dlq_url" {
  description = "Dead letter queue URL"
  value       = var.dead_letter_queue_enabled ? aws_sqs_queue.dlq[0].url : null
}

output "dlq_arn" {
  description = "Dead letter queue ARN"
  value       = var.dead_letter_queue_enabled ? aws_sqs_queue.dlq[0].arn : null
}
