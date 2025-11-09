# CloudWatch Logs Module

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

variable "log_group_name" {
  description = "CloudWatch log group name"
  type        = string
}

variable "retention_in_days" {
  description = "Log retention in days"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "main" {
  name              = var.log_group_name
  retention_in_days = var.retention_in_days

  tags = merge(
    var.tags,
    {
      Name        = "${var.name}-${var.environment}-logs"
      Environment = var.environment
    }
  )
}

# Outputs
output "log_group_name" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.main.name
}

output "log_group_arn" {
  description = "CloudWatch log group ARN"
  value       = aws_cloudwatch_log_group.main.arn
}
