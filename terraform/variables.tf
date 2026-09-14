variable "aws_region" {
  description = "AWS Region deploy lab (Sydney per guidelines)"
  type        = string
  default     = "ap-southeast-2"
}

variable "project_name" {
  description = "Tên dự án thực nghiệm hiệu năng"
  type        = string
  default     = "network-performance-capstone"
}

variable "instance_type" {
  description = "EC2 Instance type (hỗ trợ ENA và tối thiểu 12.5 Gbps burst)"
  type        = string
  default     = "c6i.large"
}

variable "benchmark_ami_id" {
  description = "AMI đã bake và pin đủ sockperf/iperf3/clang/bpftool cho toàn bộ experiment"
  type        = string

  validation {
    condition     = can(regex("^ami-[0-9a-f]+$", var.benchmark_ami_id))
    error_message = "benchmark_ami_id phải là một AMI ID đã pin, ví dụ ami-0123456789abcdef0."
  }
}

variable "key_name" {
  description = "SSH Key Pair name (để trống nếu dùng SSM)"
  type        = string
  default     = ""
}

variable "admin_cidr" {
  description = "Dải IP an toàn cho truy cập quản trị SSH (chuẩn bảo mật doanh nghiệp thay vì 0.0.0.0/0)"
  type        = string
  default     = "10.0.0.0/8"
}
