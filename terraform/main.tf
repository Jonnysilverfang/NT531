terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "Terraform"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# ==============================================================================
# IAM ROLE & INSTANCE PROFILE CHO AWS SYSTEMS MANAGER (SSM SESSION MANAGER)
# ==============================================================================
resource "aws_iam_role" "ssm_role" {
  name = "${var.project_name}-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ssm_policy_attach" {
  role       = aws_iam_role.ssm_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm_profile" {
  name = "${var.project_name}-ssm-profile"
  role = aws_iam_role.ssm_role.name
}

# ==============================================================================
# 1. VPC A: CLIENT / NGUỒN BENCHMARK (10.1.0.0/16)
# ==============================================================================
resource "aws_vpc" "vpc_a" {
  cidr_block           = "10.1.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "${var.project_name}-vpc-a" }
}

resource "aws_subnet" "subnet_a1" {
  vpc_id            = aws_vpc.vpc_a.id
  cidr_block        = "10.1.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "${var.project_name}-subnet-a1-az-a" }
}

resource "aws_subnet" "subnet_a2" {
  vpc_id            = aws_vpc.vpc_a.id
  cidr_block        = "10.1.2.0/24"
  availability_zone = "${var.aws_region}b"
  tags = { Name = "${var.project_name}-subnet-a2-az-b" }
}

resource "aws_internet_gateway" "igw_a" {
  vpc_id = aws_vpc.vpc_a.id
  tags   = { Name = "${var.project_name}-igw-a" }
}

resource "aws_route_table" "rt_a" {
  vpc_id = aws_vpc.vpc_a.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw_a.id
  }

  # Đường định tuyến 1: Tới Subnet B1 (10.2.1.0/24) qua VPC Peering
  route {
    cidr_block                = "10.2.1.0/24"
    vpc_peering_connection_id = aws_vpc_peering_connection.peer_a_b.id
  }

  # Đường định tuyến 2: Tới Subnet B2 (10.2.2.0/24) qua AWS Transit Gateway
  route {
    cidr_block         = "10.2.2.0/24"
    transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  }

  tags = { Name = "${var.project_name}-rt-a" }
}

resource "aws_route_table_association" "rta_a1" {
  subnet_id      = aws_subnet.subnet_a1.id
  route_table_id = aws_route_table.rt_a.id
}

resource "aws_route_table_association" "rta_a2" {
  subnet_id      = aws_subnet.subnet_a2.id
  route_table_id = aws_route_table.rt_a.id
}

# ==============================================================================
# 2. VPC B: TARGET SERVER / SPOKE (10.2.0.0/16)
# ==============================================================================
resource "aws_vpc" "vpc_b" {
  cidr_block           = "10.2.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "${var.project_name}-vpc-b" }
}

# Subnet B1 dành riêng cho đo đạc VPC Peering (AZ-a)
resource "aws_subnet" "subnet_b1" {
  vpc_id            = aws_vpc.vpc_b.id
  cidr_block        = "10.2.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "${var.project_name}-subnet-b1-peering-az-a" }
}

# Subnet B2 dành riêng cho đo đạc Transit Gateway (AZ-a - Cùng AZ với Subnet B1 để triệt tiêu Confounding)
resource "aws_subnet" "subnet_b2" {
  vpc_id            = aws_vpc.vpc_b.id
  cidr_block        = "10.2.2.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "${var.project_name}-subnet-b2-tgw-az-a" }
}

# Route Table B1: Hồi đáp traffic về VPC A qua VPC Peering
resource "aws_route_table" "rt_b_peering" {
  vpc_id = aws_vpc.vpc_b.id

  route {
    cidr_block                = "10.1.0.0/16"
    vpc_peering_connection_id = aws_vpc_peering_connection.peer_a_b.id
  }

  tags = { Name = "${var.project_name}-rt-b-peering" }
}

# Route Table B2: Hồi đáp traffic về VPC A qua Transit Gateway
resource "aws_route_table" "rt_b_tgw" {
  vpc_id = aws_vpc.vpc_b.id

  route {
    cidr_block         = "10.1.0.0/16"
    transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  }

  tags = { Name = "${var.project_name}-rt-b-tgw" }
}

resource "aws_route_table_association" "rta_b1" {
  subnet_id      = aws_subnet.subnet_b1.id
  route_table_id = aws_route_table.rt_b_peering.id
}

resource "aws_route_table_association" "rta_b2" {
  subnet_id      = aws_subnet.subnet_b2.id
  route_table_id = aws_route_table.rt_b_tgw.id
}

# ==============================================================================
# 3. VPC SHARED SERVICES (10.3.0.0/16) - PRIVATELINK PROVIDER
# ==============================================================================
resource "aws_vpc" "vpc_shared" {
  cidr_block           = "10.3.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "${var.project_name}-vpc-shared" }
}

resource "aws_subnet" "subnet_shared1" {
  vpc_id            = aws_vpc.vpc_shared.id
  cidr_block        = "10.3.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "${var.project_name}-subnet-shared-az-a" }
}

# ==============================================================================
# 4. PATH 1: VPC PEERING (VPC A <-> VPC B)
# ==============================================================================
resource "aws_vpc_peering_connection" "peer_a_b" {
  vpc_id      = aws_vpc.vpc_a.id
  peer_vpc_id = aws_vpc.vpc_b.id
  auto_accept = true
  tags        = { Name = "${var.project_name}-peering-a-to-b" }
}

# ==============================================================================
# 5. PATH 2: AWS TRANSIT GATEWAY (TGW)
# ==============================================================================
resource "aws_ec2_transit_gateway" "tgw" {
  description                     = "TGW Performance Lab Benchmark (Up to 100 Gbps burst)"
  amazon_side_asn                 = 64512
  auto_accept_shared_attachments = "enable"
  default_route_table_association = "enable"
  default_route_table_propagation = "enable"
  dns_support                     = "enable"
  tags                            = { Name = "${var.project_name}-tgw" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "tgw_attach_a" {
  transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  vpc_id             = aws_vpc.vpc_a.id
  subnet_ids         = [aws_subnet.subnet_a1.id, aws_subnet.subnet_a2.id]
  tags               = { Name = "${var.project_name}-tgw-attach-vpc-a" }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "tgw_attach_b" {
  transit_gateway_id = aws_ec2_transit_gateway.tgw.id
  vpc_id             = aws_vpc.vpc_b.id
  subnet_ids         = [aws_subnet.subnet_b1.id, aws_subnet.subnet_b2.id]
  tags               = { Name = "${var.project_name}-tgw-attach-vpc-b" }
}

# ==============================================================================
# 6. PATH 3: AWS PRIVATELINK (NLB + ENDPOINT SERVICE + INTERFACE ENDPOINT)
# ==============================================================================
resource "aws_lb" "nlb_privatelink" {
  name               = "${var.project_name}-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = [aws_subnet.subnet_shared1.id]
  tags               = { Name = "${var.project_name}-nlb-privatelink" }
}

resource "aws_lb_target_group" "tg_iperf3" {
  name        = "${var.project_name}-tg-iperf3"
  port        = 5201
  protocol    = "TCP"
  vpc_id      = aws_vpc.vpc_shared.id
  target_type = "instance"

  health_check {
    protocol = "TCP"
    port     = "5201"
  }
}

resource "aws_lb_listener" "listener_iperf3" {
  load_balancer_arn = aws_lb.nlb_privatelink.arn
  port              = 5201
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.tg_iperf3.arn
  }
}

resource "aws_lb_target_group_attachment" "tga_iperf3" {
  target_group_arn = aws_lb_target_group.tg_iperf3.arn
  target_id        = aws_instance.ec2_server_shared.id
  port             = 5201
}

resource "aws_vpc_endpoint_service" "privatelink_svc" {
  acceptance_required        = false
  network_load_balancer_arns = [aws_lb.nlb_privatelink.arn]
  tags                       = { Name = "${var.project_name}-endpoint-service" }
}

resource "aws_vpc_endpoint" "interface_endpoint_a" {
  vpc_id              = aws_vpc.vpc_a.id
  service_name        = aws_vpc_endpoint_service.privatelink_svc.service_name
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.subnet_a1.id]
  security_group_ids  = [aws_security_group.sg_lab.id]
  private_dns_enabled = false
  tags                = { Name = "${var.project_name}-privatelink-endpoint-a" }
}

# ==============================================================================
# 7. CLUSTER PLACEMENT GROUP (SAME-AZ HIGH-BISECTION BANDWIDTH)
# ==============================================================================
resource "aws_placement_group" "cluster_pg" {
  name     = "${var.project_name}-cluster-pg"
  strategy = "cluster"
  tags     = { Name = "${var.project_name}-cluster-pg" }
}

# ==============================================================================
# 8. SECURITY GROUPS (ENTERPRISE HARDENED)
# ==============================================================================
resource "aws_security_group" "sg_lab" {
  name        = "${var.project_name}-sg"
  description = "Allow all lab benchmarking traffic"
  vpc_id      = aws_vpc.vpc_a.id

  ingress {
    description = "SSH Access restricted to admin CIDR"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "Internal Lab Traffic (TCP/UDP/ICMP)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "sg_lab_b" {
  name        = "${var.project_name}-sg-b"
  description = "Allow internal traffic in VPC B"
  vpc_id      = aws_vpc.vpc_b.id

  ingress {
    description = "Internal Lab Traffic (TCP/UDP/ICMP)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "sg_lab_shared" {
  name        = "${var.project_name}-sg-shared"
  description = "Allow internal traffic in VPC Shared"
  vpc_id      = aws_vpc.vpc_shared.id

  ingress {
    description = "Internal Lab Traffic (TCP/UDP/ICMP)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ==============================================================================
# 8.1. VPC ENDPOINTS (SSM & S3 GATEWAY) CHO CÁC PRIVATE SUBNET KHÔNG CÓ NAT
# ==============================================================================
# Security Group cho VPC Interface Endpoints (HTTPS port 443)
resource "aws_security_group" "sg_vpc_endpoints" {
  name        = "${var.project_name}-sg-vpc-endpoints"
  description = "Allow TLS 443 for SSM and Service Endpoints"
  vpc_id      = aws_vpc.vpc_b.id

  ingress {
    description = "TLS from VPC B"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.vpc_b.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg-endpoints-vpc-b" }
}

# S3 Gateway Endpoint cho VPC B (để dnf/yum tải package từ Amazon Linux repository mà không cần NAT)
resource "aws_vpc_endpoint" "s3_endpoint_b" {
  vpc_id            = aws_vpc.vpc_b.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.rt_b_peering.id, aws_route_table.rt_b_tgw.id]
  tags              = { Name = "${var.project_name}-vpce-s3-b" }
}

# SSM Interface Endpoints cho VPC B (quản trị an toàn qua Session Manager)
resource "aws_vpc_endpoint" "ssm_endpoint_b" {
  vpc_id              = aws_vpc.vpc_b.id
  service_name        = "com.amazonaws.${var.aws_region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.subnet_b1.id]
  security_group_ids  = [aws_security_group.sg_vpc_endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-vpce-ssm-b" }
}

resource "aws_vpc_endpoint" "ssmmessages_endpoint_b" {
  vpc_id              = aws_vpc.vpc_b.id
  service_name        = "com.amazonaws.${var.aws_region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.subnet_b1.id]
  security_group_ids  = [aws_security_group.sg_vpc_endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-vpce-ssmmessages-b" }
}

resource "aws_vpc_endpoint" "ec2messages_endpoint_b" {
  vpc_id              = aws_vpc.vpc_b.id
  service_name        = "com.amazonaws.${var.aws_region}.ec2messages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.subnet_b1.id]
  security_group_ids  = [aws_security_group.sg_vpc_endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-vpce-ec2messages-b" }
}

# S3 Gateway Endpoint cho VPC Shared
resource "aws_vpc_endpoint" "s3_endpoint_shared" {
  vpc_id            = aws_vpc.vpc_shared.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.rt_shared.id]
  tags              = { Name = "${var.project_name}-vpce-s3-shared" }
}

# Security Group cho VPC Interface Endpoints trong VPC Shared
resource "aws_security_group" "sg_vpc_endpoints_shared" {
  name        = "${var.project_name}-sg-vpc-endpoints-shared"
  description = "Allow TLS 443 for SSM Endpoints in VPC Shared"
  vpc_id      = aws_vpc.vpc_shared.id

  ingress {
    description = "TLS from VPC Shared"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.vpc_shared.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-sg-endpoints-vpc-shared" }
}

# SSM Interface Endpoints cho VPC Shared (quản trị an toàn qua Session Manager)
resource "aws_vpc_endpoint" "ssm_endpoint_shared" {
  vpc_id              = aws_vpc.vpc_shared.id
  service_name        = "com.amazonaws.${var.aws_region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.subnet_shared1.id]
  security_group_ids  = [aws_security_group.sg_vpc_endpoints_shared.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-vpce-ssm-shared" }
}

resource "aws_vpc_endpoint" "ssmmessages_endpoint_shared" {
  vpc_id              = aws_vpc.vpc_shared.id
  service_name        = "com.amazonaws.${var.aws_region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.subnet_shared1.id]
  security_group_ids  = [aws_security_group.sg_vpc_endpoints_shared.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-vpce-ssmmessages-shared" }
}

resource "aws_vpc_endpoint" "ec2messages_endpoint_shared" {
  vpc_id              = aws_vpc.vpc_shared.id
  service_name        = "com.amazonaws.${var.aws_region}.ec2messages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.subnet_shared1.id]
  security_group_ids  = [aws_security_group.sg_vpc_endpoints_shared.id]
  private_dns_enabled = true
  tags                = { Name = "${var.project_name}-vpce-ec2messages-shared" }
}

# ==============================================================================
# 9. USER DATA SCRIPT (PROVISIONING BENCHMARK TOOLS)
# ==============================================================================
locals {
  user_data = <<-EOF
              #!/bin/bash
              set -e
              echo "[*] Bắt đầu khởi tạo EC2 Benchmark Instance..."
              # Thử cập nhật và cài đặt package (truy cập mirror qua S3 Gateway Endpoint không cần NAT)
              for i in {1..5}; do
                dnf update -y && dnf install -y iperf3 ethtool git gcc make bmon jq sysstat && break || sleep 5
              done
              # Khởi chạy iperf3 server daemon trên cả port 5201 và port 5202 (probe)
              iperf3 -s -p 5201 -D || true
              iperf3 -s -p 5202 -D || true
              echo "[✓] EC2 Benchmark daemons đã sẵn sàng."
              EOF
}

# ==============================================================================
# 10. EC2 BENCHMARK INSTANCES (CHUẨN HÓA ĐỐI CHỨNG KHÔNG CONFOUNDING)
# ==============================================================================
# 10.1. Cặp đối chứng đo TC-01 (Routing: VPC Peering vs Transit Gateway):
#       - Cả hai target đều nằm tại AZ-a (ap-southeast-2a)
#       - Cùng instance type c6i.large, cùng Security Group, KHÔNG dùng Placement Group
#       - BIẾN DUY NHẤT THAY ĐỔI: ĐƯỜNG ĐỊNH TUYẾN (PEERING VS TGW)

# Client A trong VPC A (AZ-a, Baseline không Placement Group)
resource "aws_instance" "ec2_client_a" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.subnet_a1.id
  vpc_security_group_ids      = [aws_security_group.sg_lab.id]
  iam_instance_profile        = aws_iam_instance_profile.ssm_profile.name
  associate_public_ip_address = true
  key_name                    = var.key_name != "" ? var.key_name : null
  user_data                   = local.user_data
  tags                        = { Name = "${var.project_name}-client-a1-baseline" }
}

# Target Server 1 trong VPC B (AZ-a, Baseline không Placement Group, Path: Peering)
resource "aws_instance" "ec2_server_b1" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.subnet_b1.id
  vpc_security_group_ids = [aws_security_group.sg_lab_b.id]
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name
  key_name               = var.key_name != "" ? var.key_name : null
  user_data              = local.user_data
  tags                   = { Name = "${var.project_name}-server-b1-peering-az-a" }
}

# Target Server 2 trong VPC B (AZ-a, Baseline không Placement Group, Path: Transit Gateway)
resource "aws_instance" "ec2_server_b2" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.subnet_b2.id
  vpc_security_group_ids = [aws_security_group.sg_lab_b.id]
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name
  key_name               = var.key_name != "" ? var.key_name : null
  user_data              = local.user_data
  tags                   = { Name = "${var.project_name}-server-b2-tgw-az-a" }
}

# 10.2. Cặp đối chứng đo TC-02 (Physical Topology: Cluster Placement Group vs Intra-AZ):
# Client & Server gắn cùng Cluster Placement Group trong AZ-a
resource "aws_instance" "ec2_client_a_pg" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.subnet_a1.id
  vpc_security_group_ids = [aws_security_group.sg_lab.id]
  placement_group        = aws_placement_group.cluster_pg.id
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name
  key_name               = var.key_name != "" ? var.key_name : null
  user_data              = local.user_data
  tags                   = { Name = "${var.project_name}-client-a-pg" }
}

resource "aws_instance" "ec2_server_b1_pg" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.subnet_b1.id
  vpc_security_group_ids = [aws_security_group.sg_lab_b.id]
  placement_group        = aws_placement_group.cluster_pg.id
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name
  key_name               = var.key_name != "" ? var.key_name : null
  user_data              = local.user_data
  tags                   = { Name = "${var.project_name}-server-b1-pg" }
}

# 10.3. Target Server in VPC Shared (Behind NLB & PrivateLink)
resource "aws_instance" "ec2_server_shared" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.subnet_shared1.id
  vpc_security_group_ids = [aws_security_group.sg_lab_shared.id]
  iam_instance_profile   = aws_iam_instance_profile.ssm_profile.name
  key_name               = var.key_name != "" ? var.key_name : null
  user_data              = local.user_data
  tags                   = { Name = "${var.project_name}-server-shared" }
}
