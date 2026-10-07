# C/D mirror A/B's compute size, AZ and root disk. Existing A/B addresses are unchanged.
locals {
  extra_nodes = {
    c = { cidr = "10.30.0.0/16", subnet = "10.30.10.0/24", ip = "10.30.10.212", peer_ip = "10.40.10.155" }
    d = { cidr = "10.40.0.0/16", subnet = "10.40.10.0/24", ip = "10.40.10.155", peer_ip = "10.30.10.212" }
  }
}

resource "aws_vpc" "extra" {
  for_each             = local.extra_nodes
  cidr_block           = each.value.cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "nt531-vpc-${each.key}" }
}

resource "aws_subnet" "extra" {
  for_each                = local.extra_nodes
  vpc_id                  = aws_vpc.extra[each.key].id
  cidr_block              = each.value.subnet
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = false
  tags                    = { Name = "nt531-subnet-${each.key}" }
}

resource "aws_internet_gateway" "extra" {
  for_each = local.extra_nodes
  vpc_id   = aws_vpc.extra[each.key].id
  tags     = { Name = "nt531-igw-${each.key}" }
}

resource "aws_route_table" "extra" {
  for_each = local.extra_nodes
  vpc_id   = aws_vpc.extra[each.key].id
  tags     = { Name = "nt531-rt-${each.key}" }
}

resource "aws_route_table_association" "extra" {
  for_each       = local.extra_nodes
  subnet_id      = aws_subnet.extra[each.key].id
  route_table_id = aws_route_table.extra[each.key].id
}

resource "aws_route" "extra_to_internet" {
  for_each               = local.extra_nodes
  route_table_id         = aws_route_table.extra[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.extra[each.key].id
}

resource "aws_security_group" "extra" {
  for_each    = local.extra_nodes
  name        = "nt531-sg-${each.key}"
  description = "NT531 measurement endpoint ${each.key}"
  vpc_id      = aws_vpc.extra[each.key].id
  tags        = { Name = "nt531-sg-${each.key}" }
}

resource "aws_vpc_security_group_ingress_rule" "extra_ssh" {
  for_each          = local.extra_nodes
  security_group_id = aws_security_group.extra[each.key].id
  cidr_ipv4         = var.ssh_admin_cidr
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}

resource "aws_vpc_security_group_ingress_rule" "extra_icmp" {
  for_each          = local.extra_nodes
  security_group_id = aws_security_group.extra[each.key].id
  cidr_ipv4         = "${each.value.peer_ip}/32"
  ip_protocol       = "icmp"
  from_port         = -1
  to_port           = -1
}

resource "aws_vpc_security_group_ingress_rule" "d_iperf_from_c" {
  security_group_id = aws_security_group.extra["d"].id
  cidr_ipv4         = "${local.extra_nodes.c.ip}/32"
  ip_protocol       = "tcp"
  from_port         = 5201
  to_port           = 5201
}

resource "aws_vpc_security_group_egress_rule" "extra_all_ipv4" {
  for_each          = local.extra_nodes
  security_group_id = aws_security_group.extra[each.key].id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_instance" "extra" {
  iam_instance_profile   = aws_iam_instance_profile.ssm.name
  for_each               = local.extra_nodes
  ami                    = aws_instance.a.ami
  instance_type          = aws_instance.a.instance_type
  subnet_id              = aws_subnet.extra[each.key].id
  private_ip             = each.value.ip
  vpc_security_group_ids = [aws_security_group.extra[each.key].id]
  key_name               = aws_instance.a.key_name
  monitoring             = false

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    http_protocol_ipv6          = "disabled"
    instance_metadata_tags      = "disabled"
  }
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    iops                  = 3000
    throughput            = 125
    encrypted             = false
    delete_on_termination = true
  }
  tags = { Name = "nt531-ec2-${each.key}" }
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_eip" "extra" {
  for_each = local.extra_nodes
  domain   = "vpc"
  tags     = { Name = "nt531-eip-${each.key}" }
}

resource "aws_eip_association" "extra" {
  for_each            = local.extra_nodes
  allocation_id       = aws_eip.extra[each.key].id
  instance_id         = aws_instance.extra[each.key].id
  private_ip_address  = each.value.ip
  allow_reassociation = false
  depends_on          = [aws_internet_gateway.extra]
}

resource "aws_vpc_peering_connection" "cd" {
  vpc_id      = aws_vpc.extra["c"].id
  peer_vpc_id = aws_vpc.extra["d"].id
  auto_accept = true
  requester { allow_remote_vpc_dns_resolution = false }
  accepter { allow_remote_vpc_dns_resolution = false }
  tags = { Name = "nt531-peer-cd" }
}

resource "aws_route" "extra_to_peer" {
  for_each                  = local.extra_nodes
  route_table_id            = aws_route_table.extra[each.key].id
  destination_cidr_block    = each.key == "c" ? local.extra_nodes.d.cidr : local.extra_nodes.c.cidr
  vpc_peering_connection_id = var.routing_mode == "peering" ? aws_vpc_peering_connection.cd.id : null
  transit_gateway_id        = var.routing_mode == "tgw" ? try(aws_ec2_transit_gateway.experiment[0].id, null) : null
  depends_on                = [aws_ec2_transit_gateway_vpc_attachment.experiment]
  lifecycle {
    precondition {
      condition     = var.routing_mode != "tgw" || var.enable_transit_gateway
      error_message = "Enable Transit Gateway before selecting tgw routing."
    }
  }
}
