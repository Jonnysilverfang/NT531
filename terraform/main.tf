terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = [var.allowed_account_id]
  default_tags {
    tags = {
      Project     = var.project_name
      ManagedBy   = "Terraform"
      Environment = "performance-experiment"
      DataMode    = "mode-b"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64"
}

locals {
  benchmark_ami_id = coalesce(var.benchmark_ami_id, data.aws_ssm_parameter.al2023_ami.value)
  bootstrap_b64    = base64encode(file("${path.module}/../scripts/bootstrap_al2023.sh"))
  user_data        = <<-EOF
    #!/bin/bash
    set -euo pipefail
    echo '${local.bootstrap_b64}' | base64 -d > /tmp/bootstrap_al2023.sh
    chmod 0700 /tmp/bootstrap_al2023.sh
    /tmp/bootstrap_al2023.sh
    rm -f /tmp/bootstrap_al2023.sh
  EOF
}

# -----------------------------------------------------------------------------
# Encrypted evidence storage and network flow logs
# -----------------------------------------------------------------------------
resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_kms_key" "experiment" {
  description             = "NT531 experiment artifacts, flow logs, and EBS"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountAdministration"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "CloudWatchLogsUse"
        Effect    = "Allow"
        Principal = { Service = "logs.${var.aws_region}.amazonaws.com" }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/nt531/${var.project_name}/flow-logs"
          }
        }
      }
    ]
  })
}

resource "aws_kms_alias" "experiment" {
  name          = "alias/${var.project_name}-experiment"
  target_key_id = aws_kms_key.experiment.key_id
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = "${var.project_name}-${data.aws_caller_identity.current.account_id}-${random_id.suffix.hex}"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.experiment.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = "/nt531/${var.project_name}/flow-logs"
  retention_in_days = var.flow_log_retention_days
  kms_key_id        = aws_kms_key.experiment.arn
}

resource "aws_iam_role" "flow_logs" {
  name = "${var.project_name}-flow-logs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "flow_logs" {
  name = "publish-encrypted-flow-logs"
  role = aws_iam_role.flow_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogGroups", "logs:DescribeLogStreams"]
      Resource = "${aws_cloudwatch_log_group.flow_logs.arn}:*"
    }]
  })
}

# -----------------------------------------------------------------------------
# VPC A and VPC B. Workloads and TGW attachment ENIs stay in us-east-1a.
# -----------------------------------------------------------------------------
resource "aws_vpc" "a" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.project_name}-vpc-a" }
}

resource "aws_vpc" "b" {
  cidr_block           = "10.2.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.project_name}-vpc-b" }
}

resource "aws_subnet" "a_client" {
  vpc_id                  = aws_vpc.a.id
  cidr_block              = "10.1.1.0/24"
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project_name}-a-client" }
}

resource "aws_subnet" "b_peering" {
  vpc_id                  = aws_vpc.b.id
  cidr_block              = "10.2.1.0/24"
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project_name}-b-peering" }
}

resource "aws_subnet" "b_tgw" {
  vpc_id                  = aws_vpc.b.id
  cidr_block              = "10.2.2.0/24"
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project_name}-b-tgw" }
}

resource "aws_subnet" "a_tgw_attachment" {
  vpc_id            = aws_vpc.a.id
  cidr_block        = "10.1.255.0/28"
  availability_zone = var.availability_zone
  tags              = { Name = "${var.project_name}-a-tgw-attachment" }
}

resource "aws_subnet" "b_tgw_attachment" {
  vpc_id            = aws_vpc.b.id
  cidr_block        = "10.2.255.0/28"
  availability_zone = var.availability_zone
  tags              = { Name = "${var.project_name}-b-tgw-attachment" }
}

resource "aws_internet_gateway" "a" {
  vpc_id = aws_vpc.a.id
  tags   = { Name = "${var.project_name}-igw-a" }
}

resource "aws_internet_gateway" "b" {
  vpc_id = aws_vpc.b.id
  tags   = { Name = "${var.project_name}-igw-b" }
}

resource "aws_vpc_peering_connection" "a_b" {
  vpc_id      = aws_vpc.a.id
  peer_vpc_id = aws_vpc.b.id
  auto_accept = true
  tags        = { Name = "${var.project_name}-peering-a-b" }
}

resource "aws_ec2_transit_gateway" "experiment" {
  description                     = "Dedicated two-spoke NT531 performance experiment"
  amazon_side_asn                 = 64512
  auto_accept_shared_attachments  = "disable"
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  dns_support                     = "enable"
  tags                            = { Name = "${var.project_name}-tgw", Segmentation = "flat-two-spoke-only" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "a" {
  transit_gateway_id = aws_ec2_transit_gateway.experiment.id
  vpc_id             = aws_vpc.a.id
  subnet_ids         = [aws_subnet.a_tgw_attachment.id]
  tags               = { Name = "${var.project_name}-attach-a" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "b" {
  transit_gateway_id = aws_ec2_transit_gateway.experiment.id
  vpc_id             = aws_vpc.b.id
  subnet_ids         = [aws_subnet.b_tgw_attachment.id]
  tags               = { Name = "${var.project_name}-attach-b" }
}

resource "aws_ec2_transit_gateway_route_table" "experiment" {
  transit_gateway_id = aws_ec2_transit_gateway.experiment.id
  tags               = { Name = "${var.project_name}-tgw-rt-flat-two-spoke" }
}

resource "aws_ec2_transit_gateway_route_table_association" "a" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.a.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.experiment.id
}

resource "aws_ec2_transit_gateway_route_table_association" "b" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.b.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.experiment.id
}

resource "aws_ec2_transit_gateway_route" "to_a" {
  destination_cidr_block         = aws_vpc.a.cidr_block
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.a.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.experiment.id
}

resource "aws_ec2_transit_gateway_route" "to_b" {
  destination_cidr_block         = aws_vpc.b.cidr_block
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.b.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.experiment.id
}

resource "aws_route_table" "a_client" {
  vpc_id = aws_vpc.a.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.a.id
  }
  route {
    cidr_block                = "10.2.1.0/24"
    vpc_peering_connection_id = aws_vpc_peering_connection.a_b.id
  }
  route {
    cidr_block         = "10.2.2.0/24"
    transit_gateway_id = aws_ec2_transit_gateway.experiment.id
  }
  tags = { Name = "${var.project_name}-rt-a-client" }
}

resource "aws_route_table" "b_peering" {
  vpc_id = aws_vpc.b.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.b.id
  }
  route {
    cidr_block                = aws_vpc.a.cidr_block
    vpc_peering_connection_id = aws_vpc_peering_connection.a_b.id
  }
  tags = { Name = "${var.project_name}-rt-b-peering" }
}

resource "aws_route_table" "b_tgw" {
  vpc_id = aws_vpc.b.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.b.id
  }
  route {
    cidr_block         = aws_vpc.a.cidr_block
    transit_gateway_id = aws_ec2_transit_gateway.experiment.id
  }
  tags = { Name = "${var.project_name}-rt-b-tgw" }
}

resource "aws_route_table" "a_tgw_attachment" {
  vpc_id = aws_vpc.a.id
  route {
    cidr_block         = aws_vpc.b.cidr_block
    transit_gateway_id = aws_ec2_transit_gateway.experiment.id
  }
  tags = { Name = "${var.project_name}-rt-a-tgw-attachment" }
}

resource "aws_route_table" "b_tgw_attachment" {
  vpc_id = aws_vpc.b.id
  route {
    cidr_block         = aws_vpc.a.cidr_block
    transit_gateway_id = aws_ec2_transit_gateway.experiment.id
  }
  tags = { Name = "${var.project_name}-rt-b-tgw-attachment" }
}

resource "aws_route_table_association" "a_client" {
  subnet_id      = aws_subnet.a_client.id
  route_table_id = aws_route_table.a_client.id
}
resource "aws_route_table_association" "b_peering" {
  subnet_id      = aws_subnet.b_peering.id
  route_table_id = aws_route_table.b_peering.id
}
resource "aws_route_table_association" "b_tgw" {
  subnet_id      = aws_subnet.b_tgw.id
  route_table_id = aws_route_table.b_tgw.id
}
resource "aws_route_table_association" "a_tgw_attachment" {
  subnet_id      = aws_subnet.a_tgw_attachment.id
  route_table_id = aws_route_table.a_tgw_attachment.id
}
resource "aws_route_table_association" "b_tgw_attachment" {
  subnet_id      = aws_subnet.b_tgw_attachment.id
  route_table_id = aws_route_table.b_tgw_attachment.id
}

# -----------------------------------------------------------------------------
# Least-privilege network policy: no SSH ingress, benchmark ports from client only.
# -----------------------------------------------------------------------------
resource "aws_security_group" "client" {
  name        = "${var.project_name}-client"
  description = "No inbound administration; SSM agent uses outbound TLS"
  vpc_id      = aws_vpc.a.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.project_name}-client" }
}

resource "aws_security_group" "servers" {
  name        = "${var.project_name}-servers"
  description = "Only registered benchmark traffic from VPC A client subnet"
  vpc_id      = aws_vpc.b.id
  ingress {
    description = "iperf3 TCP"
    from_port   = 5201
    to_port     = 5201
    protocol    = "tcp"
    cidr_blocks = [aws_subnet.a_client.cidr_block]
  }
  ingress {
    description = "iperf3 UDP"
    from_port   = 5201
    to_port     = 5201
    protocol    = "udp"
    cidr_blocks = [aws_subnet.a_client.cidr_block]
  }
  ingress {
    description = "sockperf TCP"
    from_port   = 5202
    to_port     = 5202
    protocol    = "tcp"
    cidr_blocks = [aws_subnet.a_client.cidr_block]
  }
  ingress {
    description = "path and loss probes"
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = [aws_subnet.a_client.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.project_name}-servers" }
}

# -----------------------------------------------------------------------------
# Split instance roles. Only the client can invoke the allowlisted SSM document.
# -----------------------------------------------------------------------------
resource "aws_iam_role" "client" {
  name = "${var.project_name}-client"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role" "server" {
  name = "${var.project_name}-server"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "client_ssm_core" {
  role       = aws_iam_role.client.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_role_policy_attachment" "server_ssm_core" {
  role       = aws_iam_role.server.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "client" {
  name = "${var.project_name}-client"
  role = aws_iam_role.client.name
}
resource "aws_iam_instance_profile" "server" {
  name = "${var.project_name}-server"
  role = aws_iam_role.server.name
}

resource "aws_iam_role_policy" "artifact_access_client" {
  name = "experiment-artifact-read-write"
  role = aws_iam_role.client.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.artifacts.arn },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.artifacts.arn}/*" },
      { Effect = "Allow", Action = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"], Resource = aws_kms_key.experiment.arn }
    ]
  })
}

resource "aws_iam_role_policy" "artifact_access_server" {
  name = "experiment-bundle-read"
  role = aws_iam_role.server.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.artifacts.arn },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.artifacts.arn}/bundles/*" },
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = aws_kms_key.experiment.arn }
    ]
  })
}

# -----------------------------------------------------------------------------
# Three identical AL2023/c6i.large benchmark instances.
# -----------------------------------------------------------------------------
resource "aws_instance" "client" {
  ami                         = local.benchmark_ami_id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.a_client.id
  private_ip                  = "10.1.1.10"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.client.id]
  iam_instance_profile        = aws_iam_instance_profile.client.name
  user_data                   = local.user_data
  user_data_replace_on_change = true
  monitoring                  = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    encrypted             = true
    kms_key_id            = aws_kms_key.experiment.arn
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
  }
  tags = { Name = "${var.project_name}-client-a", Role = "benchmark-client" }
}

resource "aws_instance" "server_b1" {
  ami                         = local.benchmark_ami_id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.b_peering.id
  private_ip                  = "10.2.1.10"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.servers.id]
  iam_instance_profile        = aws_iam_instance_profile.server.name
  user_data                   = local.user_data
  user_data_replace_on_change = true
  monitoring                  = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    encrypted             = true
    kms_key_id            = aws_kms_key.experiment.arn
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
  }
  tags = { Name = "${var.project_name}-server-b1-peering", Role = "benchmark-dut", Path = "peering" }
}

resource "aws_instance" "server_b2" {
  ami                         = local.benchmark_ami_id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.b_tgw.id
  private_ip                  = "10.2.2.10"
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.servers.id]
  iam_instance_profile        = aws_iam_instance_profile.server.name
  user_data                   = local.user_data
  user_data_replace_on_change = true
  monitoring                  = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  root_block_device {
    encrypted             = true
    kms_key_id            = aws_kms_key.experiment.arn
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
  }
  tags = { Name = "${var.project_name}-server-b2-tgw", Role = "benchmark-target", Path = "tgw" }
}

resource "aws_iam_role_policy" "client_dut_control" {
  name = "ssm-control-experiment-duts"
  role = aws_iam_role.client.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "ssm:SendCommand"
        Resource = [
          "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
          aws_instance.server_b1.arn,
          aws_instance.server_b2.arn
        ]
      },
      { Effect = "Allow", Action = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:DescribeInstanceInformation"], Resource = "*" }
    ]
  })
}

resource "aws_flow_log" "vpc_a" {
  iam_role_arn         = aws_iam_role.flow_logs.arn
  log_destination      = aws_cloudwatch_log_group.flow_logs.arn
  log_destination_type = "cloud-watch-logs"
  traffic_type         = "ALL"
  vpc_id               = aws_vpc.a.id
}

resource "aws_flow_log" "vpc_b" {
  iam_role_arn         = aws_iam_role.flow_logs.arn
  log_destination      = aws_cloudwatch_log_group.flow_logs.arn
  log_destination_type = "cloud-watch-logs"
  traffic_type         = "ALL"
  vpc_id               = aws_vpc.b.id
}

resource "aws_flow_log" "tgw" {
  iam_role_arn         = aws_iam_role.flow_logs.arn
  log_destination      = aws_cloudwatch_log_group.flow_logs.arn
  log_destination_type = "cloud-watch-logs"
  traffic_type         = "ALL"
  transit_gateway_id   = aws_ec2_transit_gateway.experiment.id
}
