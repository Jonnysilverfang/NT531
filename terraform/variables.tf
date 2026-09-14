variable "aws_region" {
  description = "Fixed Region for the registered experiment"
  type        = string
  default     = "us-east-1"
  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "This experiment is registered only for us-east-1."
  }
}

variable "availability_zone" {
  description = "Fixed single AZ for all benchmark workloads and TGW attachments"
  type        = string
  default     = "us-east-1a"
  validation {
    condition     = var.availability_zone == "us-east-1a"
    error_message = "This experiment is registered only for us-east-1a."
  }
}

variable "allowed_account_id" {
  description = "Fail-closed AWS account allowlist"
  type        = string
  default     = "411509276671"
  validation {
    condition     = can(regex("^[0-9]{12}$", var.allowed_account_id))
    error_message = "allowed_account_id must be a 12-digit AWS account ID."
  }
}

variable "project_name" {
  description = "Resource prefix"
  type        = string
  default     = "nt531-netperf"
}

variable "instance_type" {
  description = "Identical EC2 type for client and both servers"
  type        = string
  default     = "c6i.large"
  validation {
    condition     = var.instance_type == "c6i.large"
    error_message = "The registered experiment requires c6i.large."
  }
}

variable "benchmark_ami_id" {
  description = "Optional pinned AL2023 x86_64 AMI. Null resolves the official kernel-6.1 public parameter and outputs the exact resolved ID."
  type        = string
  default     = null
  nullable    = true
  validation {
    condition     = var.benchmark_ami_id == null || can(regex("^ami-[0-9a-f]{8,17}$", var.benchmark_ami_id))
    error_message = "benchmark_ami_id must be null or a valid AMI ID."
  }
}

variable "flow_log_retention_days" {
  description = "CloudWatch retention for encrypted VPC/TGW flow logs"
  type        = number
  default     = 7
}
